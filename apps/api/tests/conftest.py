from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx2
import pytest

from securefabric_api.config import ApiSettings
from securefabric_api.main import create_app
from securefabric_connectors.sandbox.vendor import reset_registry
from securefabric_domain import tenancy
from securefabric_domain.runtime import Platform
from securefabric_domain.testing import (
    Tenant,
    build_test_platform,
    build_test_settings,
    make_tenant,
    reset_queues,
)


@dataclass
class Api:
    client: httpx2.AsyncClient
    platform: Platform
    worker: Platform
    tenant: Tenant
    key: str
    other_key: str

    def h(self, key: str | None = None, **extra: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {key or self.key}", **extra}

    async def get(self, path: str, key: str | None = None, **kw: Any) -> httpx2.Response:
        return await self.client.get(path, headers=self.h(key, **kw.pop("headers", {})), **kw)

    async def post(
        self, path: str, json: Any = None, key: str | None = None, **kw: Any
    ) -> httpx2.Response:
        return await self.client.post(
            path, json=json, headers=self.h(key, **kw.pop("headers", {})), **kw
        )

    async def patch(
        self, path: str, json: Any = None, key: str | None = None, **kw: Any
    ) -> httpx2.Response:
        return await self.client.patch(
            path, json=json, headers=self.h(key, **kw.pop("headers", {})), **kw
        )

    async def delete(self, path: str, key: str | None = None) -> httpx2.Response:
        return await self.client.delete(path, headers=self.h(key))


async def make_key(
    platform: Platform, environment_id: Any, account_id: Any, scopes: list[str] | None = None
) -> str:
    principal = tenancy.system_principal(environment_id, account_id)
    _, key = await tenancy.create_api_key(platform, principal, name="test", scopes=scopes)
    return key


@pytest.fixture
async def api(database_url: str) -> AsyncIterator[Api]:
    reset_registry()
    platform = build_test_platform(database_url, role="api", settings=build_test_settings())
    worker = build_test_platform(database_url, role="test")
    await worker.open()
    await reset_queues(worker)
    app = create_app(
        settings=ApiSettings(_env_file=None, environment="test", log_level="WARNING"),
        platform=platform,
        rate_limit_per_minute=100000,
    )
    async with app.router.lifespan_context(app):
        tenant = await make_tenant(worker)
        key = await make_key(worker, tenant.environment_id, tenant.account_id)
        other = await make_key(worker, tenant.other_environment_id, tenant.account_id)
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://api.test") as client:
            yield Api(client, platform, worker, tenant, key, other)
    await worker.close()
    await platform.close()
