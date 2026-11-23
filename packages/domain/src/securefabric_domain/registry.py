"""The connector registry: code and manifests, loaded at deploy (CAT-01).

``sync_catalog`` writes each manifest into ``control.connector`` so the catalogue
endpoints, integrations and connections all reference a versioned manifest.
"""

import json
from collections.abc import Iterable

from securefabric_cdk.connector import Connector
from securefabric_cdk.manifest import Manifest
from securefabric_core import NotFoundError
from securefabric_db import AsyncPool, system_tx


class ConnectorRegistry:
    def __init__(self, connectors: Iterable[Connector]) -> None:
        self._by_id = {c.manifest.id: c for c in connectors}

    def get(self, connector_id: str) -> Connector:
        try:
            return self._by_id[connector_id.upper()]
        except KeyError:
            raise NotFoundError(
                f"Unknown connector {connector_id!r}", code="connector_not_found"
            ) from None

    def manifest(self, connector_id: str) -> Manifest:
        return self.get(connector_id).manifest

    def __contains__(self, connector_id: str) -> bool:
        return connector_id.upper() in self._by_id

    def all(self) -> list[Connector]:
        return sorted(self._by_id.values(), key=lambda c: c.manifest.id)


def default_registry() -> ConnectorRegistry:
    from securefabric_connectors import all_connectors

    return ConnectorRegistry(cls() for cls in all_connectors())


async def sync_catalog(pool: AsyncPool, registry: ConnectorRegistry) -> list[str]:
    """Upsert every manifest as the current version of its connector. Idempotent."""
    loaded: list[str] = []
    async with system_tx(pool) as conn:
        for connector in registry.all():
            m = connector.manifest
            await conn.execute(
                "update control.connector set is_current = false where id = %s and version <> %s",
                (m.id, m.version),
            )
            await conn.execute(
                """
                insert into control.connector (id, version, manifest, status, is_current,
                                               deprecated_at)
                values (%s, %s, %s, %s, true, case when %s = 'deprecated' then now() end)
                on conflict (id, version) do update
                   set manifest = excluded.manifest, status = excluded.status,
                       is_current = true, loaded_at = now()
                """,
                (m.id, m.version, json.dumps(m.model_dump(mode="json")), m.status, m.status),
            )
            loaded.append(f"{m.id}@{m.version}")
    return loaded
