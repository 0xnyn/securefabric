"""Task handler registry.

Every handler module exposes ``register(client, pool)``; add new modules to ``_MODULES``.
"""

from absurd_sdk import AsyncAbsurd

from securefabric_db import AsyncPool
from securefabric_worker.handlers import connections, tenants

_MODULES = (tenants, connections)


def register_all(client: AsyncAbsurd, pool: AsyncPool) -> None:
    for module in _MODULES:
        module.register(client, pool)
