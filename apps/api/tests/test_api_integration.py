"""API against a real Postgres + Absurd (no fakes): catches SDK/driver type mismatches."""

import psycopg
import pytest
from fastapi.testclient import TestClient

from securefabric_api.config import ApiSettings
from securefabric_api.main import create_app
from securefabric_db import DatabaseSettings
from securefabric_tasks import Queue

pytestmark = pytest.mark.integration


@pytest.fixture
def live_client(database_url: str) -> TestClient:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("select absurd.create_queue(%s)", (str(Queue.DEFAULT),))
    app = create_app(
        settings=ApiSettings(_env_file=None, environment="test"),
        db_settings=DatabaseSettings(url=database_url, pool_min_size=0, pool_max_size=2),
    )
    return TestClient(app)


def test_spawn_poll_and_cancel_through_real_stack(live_client: TestClient) -> None:
    with live_client as client:  # runs lifespan -> real pool
        assert client.get("/health/ready").json()["checks"] == {"database": True}

        resp = client.post(
            "/api/v1/tenants",
            json={"tenant_id": "live-api", "admin_email": "a@b.co", "activation_delay_seconds": 60},
            headers={"Idempotency-Key": "live-api-test"},
        )
        assert resp.status_code == 202, resp.text
        accepted = resp.json()

        again = client.post(
            "/api/v1/tenants",
            json={"tenant_id": "live-api", "admin_email": "a@b.co"},
            headers={"Idempotency-Key": "live-api-test"},
        )
        assert again.json()["task_id"] == accepted["task_id"]

        status = client.get(accepted["status_url"])
        assert status.status_code == 200
        assert status.json()["state"] in {"pending", "running", "sleeping", "cancelled"}

        cancel = client.post(f"/api/v1/tasks/{accepted['task_id']}/cancel")
        assert cancel.status_code == 204
        assert client.get(accepted["status_url"]).json()["state"] == "cancelled"
