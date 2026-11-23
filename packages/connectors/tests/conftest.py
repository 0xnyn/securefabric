import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # test helpers (fake_github)

from collections.abc import AsyncIterator

import pytest

from securefabric_connectors.sandbox.vendor import reset_registry
from securefabric_domain.runtime import Platform
from securefabric_domain.testing import Tenant, build_test_platform, make_tenant, reset_queues


@pytest.fixture
async def platform(database_url: str) -> AsyncIterator[Platform]:
    p = build_test_platform(database_url)
    await p.open()
    await reset_queues(p)
    try:
        yield p
    finally:
        await p.close()


@pytest.fixture
async def tenant(platform: Platform) -> Tenant:
    return await make_tenant(platform)


@pytest.fixture(autouse=True)
def _fresh_sandbox_vendor() -> None:
    reset_registry()
