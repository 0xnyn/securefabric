from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest
from absurd_sdk import TaskResultSnapshot
from fastapi import FastAPI
from fastapi.testclient import TestClient

from securefabric_api.config import ApiSettings
from securefabric_api.dependencies import get_absurd, get_pool
from securefabric_api.main import create_app


class FakeAbsurd:
    """In-memory stand-in for ``AsyncAbsurd`` covering what the API uses."""

    def __init__(self) -> None:
        self.spawned: list[dict[str, Any]] = []
        self.snapshots: dict[str, TaskResultSnapshot] = {}
        self.cancelled: list[str] = []

    async def spawn(self, task_name: str, params: Any, **kwargs: Any) -> dict[str, Any]:
        # Like the real SDK (psycopg), IDs come back as uuid.UUID, not str.
        task_id: UUID = uuid4()
        self.spawned.append({"task_name": task_name, "params": params, **kwargs})
        self.snapshots[str(task_id)] = TaskResultSnapshot(state="pending")
        return {"task_id": task_id, "run_id": uuid4(), "attempt": 1}

    async def fetch_task_result(
        self, task_id: str, queue_name: str | None = None
    ) -> TaskResultSnapshot | None:
        return self.snapshots.get(task_id)

    async def cancel_task(self, task_id: str, queue_name: str | None = None) -> None:
        self.cancelled.append(task_id)
        self.snapshots[task_id] = TaskResultSnapshot(state="cancelled")


class FakePool:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy

    @asynccontextmanager
    async def connection(self) -> AsyncIterator["FakePool"]:
        if not self.healthy:
            raise OSError("connection refused")
        yield self

    async def execute(self, *_: Any) -> None:
        return None


@pytest.fixture
def fake_absurd() -> FakeAbsurd:
    return FakeAbsurd()


@pytest.fixture
def fake_pool() -> FakePool:
    return FakePool()


@pytest.fixture
def app(fake_absurd: FakeAbsurd, fake_pool: FakePool) -> FastAPI:
    settings = ApiSettings(_env_file=None, environment="test")
    application = create_app(settings=settings)
    application.dependency_overrides[get_absurd] = lambda: fake_absurd
    application.dependency_overrides[get_pool] = lambda: fake_pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    # Not entering the context manager skips the lifespan, so no real pool is opened.
    return TestClient(app)
