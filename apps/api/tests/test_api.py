from typing import Any
from uuid import UUID

from absurd_sdk import TaskResultSnapshot
from fastapi.testclient import TestClient

# Fixture fakes live in conftest.py (FakeAbsurd, FakePool); typed as Any here because
# test dirs are not importable packages under --import-mode=importlib.

T1 = "0192f4a8-0000-7000-8000-000000000001"
MISSING = "0192f4a8-0000-7000-8000-00000000ffff"
VALID_BODY = {"tenant_id": "acme", "admin_email": "ops@acme.io", "plan": "pro"}


# --- health -----------------------------------------------------------------


def test_liveness(client: TestClient) -> None:
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "securefabric-api", "environment": "test"}


def test_readiness_ok(client: TestClient) -> None:
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "checks": {"database": True}}


def test_readiness_degraded_when_db_down(client: TestClient, fake_pool: Any) -> None:
    fake_pool.healthy = False
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["checks"] == {"database": False}


# --- request context ----------------------------------------------------------


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/health/live").headers["x-request-id"]
    assert len(generated) == 32
    echoed = client.get("/health/live", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"


# --- tenants ------------------------------------------------------------------


def test_provision_tenant_enqueues_task(client: TestClient, fake_absurd: Any) -> None:
    resp = client.post("/api/v1/tenants", json=VALID_BODY, headers={"X-Request-ID": "req-1"})
    assert resp.status_code == 202
    body = resp.json()
    task_id = body["task_id"]
    assert str(UUID(task_id)) == task_id
    assert body["task_name"] == "provision-tenant"
    assert body["status_url"].endswith(f"/api/v1/tasks/{task_id}?queue=default")
    assert client.get(body["status_url"]).json()["state"] == "pending"

    [call] = fake_absurd.spawned
    assert call["params"]["tenant_id"] == "acme"
    assert call["idempotency_key"] == "provision-tenant:acme"
    assert call["headers"] == {"request_id": "req-1"}


def test_provision_tenant_honours_idempotency_key(client: TestClient, fake_absurd: Any) -> None:
    client.post("/api/v1/tenants", json=VALID_BODY, headers={"Idempotency-Key": "custom"})
    assert fake_absurd.spawned[0]["idempotency_key"] == "custom"


def test_provision_tenant_validation_envelope(client: TestClient) -> None:
    resp = client.post("/api/v1/tenants", json={"tenant_id": "Bad Id!"})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_failed"
    fields = {tuple(e["loc"]) for e in error["details"]["errors"]}
    assert ("body", "tenant_id") in fields
    assert ("body", "admin_email") in fields


# --- tasks --------------------------------------------------------------------


def test_get_task_states(client: TestClient, fake_absurd: Any) -> None:
    fake_absurd.snapshots[T1] = TaskResultSnapshot(state="completed", result={"ok": True})
    resp = client.get(f"/api/v1/tasks/{T1}")
    assert resp.status_code == 200
    assert resp.json() == {
        "task_id": T1,
        "queue": "default",
        "state": "completed",
        "result": {"ok": True},
        "failure": None,
    }


def test_get_unknown_task_is_404_envelope(client: TestClient) -> None:
    resp = client.get(f"/api/v1/tasks/{MISSING}")
    assert resp.status_code == 404
    assert resp.json()["error"] == {
        "code": "not_found",
        "message": "Task not found",
        "details": {"task_id": MISSING, "queue": "default"},
    }


def test_get_task_rejects_malformed_id(client: TestClient) -> None:
    resp = client.get("/api/v1/tasks/not-a-uuid")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


def test_get_task_rejects_unknown_queue(client: TestClient) -> None:
    assert client.get(f"/api/v1/tasks/{T1}", params={"queue": "evil"}).status_code == 422


def test_cancel_task(client: TestClient, fake_absurd: Any) -> None:
    fake_absurd.snapshots[T1] = TaskResultSnapshot(state="sleeping")
    assert client.post(f"/api/v1/tasks/{T1}/cancel").status_code == 204
    assert fake_absurd.cancelled == [T1]
    assert client.post(f"/api/v1/tasks/{MISSING}/cancel").status_code == 404


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_openapi_schema_lists_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/v1/tenants", "/api/v1/tasks/{task_id}", "/health/ready"} <= set(paths)


def test_status_reports_database_down(client: TestClient, fake_pool: Any) -> None:
    fake_pool.healthy = False
    body = client.get("/api/v1/status").json()
    assert body["status"] == "down"
    assert body["database"]["reachable"] is False
    assert body["components"][0]["summary"].startswith("Postgres is unreachable")
