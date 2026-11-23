"""The control-plane API against real Postgres + Absurd: what the dash calls."""

import psycopg
import pytest
from fastapi.testclient import TestClient

from securefabric_api.config import ApiSettings
from securefabric_api.main import create_app
from securefabric_db import DatabaseSettings
from securefabric_tasks import Queue

pytestmark = pytest.mark.integration


@pytest.fixture
def live(database_url: str) -> TestClient:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("select absurd.create_queue(%s)", (str(Queue.DEFAULT),))
    app = create_app(
        settings=ApiSettings(_env_file=None, environment="test"),
        db_settings=DatabaseSettings(url=database_url, pool_min_size=0, pool_max_size=4),
    )
    return TestClient(app)


def test_dash_flow(live: TestClient) -> None:
    with live as client:
        ws = client.post("/api/v1/workspace/reset").json()
        assert [e["slug"] for e in ws["environments"]] == ["dev", "prod"]
        assert ws["team"]["name"] == "Acme Security"

        # Connect a customer: a RUNNING job plus a durable task to finish it.
        resp = client.post(
            "/api/v1/environments/prod/connections",
            json={
                "integrationId": "crowdstrike",
                "customer": {
                    "email": "soc@contoso.com",
                    "endUserId": "org_c",
                    "orgName": "Contoso",
                },
                "credentials": {"client_id": "abc", "client_secret": "supersecret99"},
            },
        )
        assert resp.status_code == 201, resp.text
        started = resp.json()
        assert started["taskId"]

        task = client.get(f"/api/v1/tasks/{started['taskId']}").json()
        assert task["state"] in {"pending", "running", "sleeping"}

        again = client.post(f"/api/v1/environments/prod/connections/{started['connectionId']}/sync")
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "conflict"

        prod = client.get("/api/v1/workspace").json()["environments"][1]
        conn = next(c for c in prod["connections"] if c["id"] == started["connectionId"])
        assert conn["health"] == "SYNCING"
        assert conn["jobs"][0]["id"] == started["jobId"]

        # Keys: the secret is shown once.
        key = client.post(
            "/api/v1/environments/prod/keys", json={"name": "CI", "scopes": ["data:read"]}
        ).json()
        assert key["secret"].startswith("sk_live_")
        assert key["key"]["preview"].endswith(key["secret"][-4:])

        # Validation and not-found use the error envelope.
        bad = client.post("/api/v1/environments/prod/keys", json={"name": "x", "scopes": []})
        assert bad.status_code == 422
        missing = client.patch("/api/v1/environments/nope", json={"name": "x"})
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"


def test_status_endpoint(live: TestClient) -> None:
    with live as client:
        body = client.get("/api/v1/status").json()
        assert body["database"]["reachable"] is True
        names = {c["name"] for c in body["components"]}
        assert {"database", "migrations", "worker", "queue", "workspace"} <= names
        assert body["status"] in {"ok", "degraded", "down"}
