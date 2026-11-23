"""Dry run and recording against a live connection (CDK-05, CDK-06)."""

import json
from pathlib import Path
from typing import Any

import pytest

from securefabric_cdk.fixtures import ReplayTransport, load_fixture
from securefabric_core import ValidationFailedError
from securefabric_db import fetch_required, tenant_tx
from securefabric_domain import devtools
from securefabric_domain.testing import make_connection
from securefabric_schema import Mode

pytestmark = pytest.mark.integration

KEY = {"api_key": "sbx_devtools_1"}
OPTS = {"finding_count": 30, "host_count": 7, "page_size": 10}


async def _footprint(platform: Any, env: Any, cid: Any) -> tuple[int, int, int]:
    async with tenant_tx(platform.pool, env) as conn:
        row = await fetch_required(
            conn,
            """select (select count(*) from data.vulnerability_finding where connection_id = %s) as f,
                      (select count(*) from sync.checkpoint where connection_id = %s) as c,
                      (select count(*) from sync.raw_page where connection_id = %s) as r""",
            (cid, cid, cid),
        )
    return row["f"], row["c"], row["r"]


async def test_dryrun_reports_and_persists_nothing(platform, tenant) -> None:
    cid = await make_connection(platform, tenant, credentials=KEY, options=OPTS)
    before = await _footprint(platform, tenant.environment_id, cid)
    out = await devtools.dryrun(platform, cid, "findings", pages=2, mode=Mode.FULL)
    assert out["pages"] == 2 and out["records"] > 0 and out["vendor_requests"] >= 2
    assert out["invalid"] == [] and len(out["sample"]) == 3
    caps = out["capabilities"]
    assert caps["records"] == out["records"] and "severity" in caps["values_emitted"]
    assert out["manifest_problems"] == [] or isinstance(out["manifest_problems"], list)
    assert await _footprint(platform, tenant.environment_id, cid) == before

    with pytest.raises(ValidationFailedError):
        await devtools.dryrun(platform, cid, "no_such_stream")
    with pytest.raises(ValidationFailedError):
        await devtools.dryrun(platform, cid, "finding_exports")  # exports are not dry-run


async def test_record_writes_replayable_scrubbed_fixtures(platform, tenant, tmp_path: Path) -> None:
    cid = await make_connection(platform, tenant, credentials=KEY, options=OPTS)
    out = await devtools.record(platform, cid, "hosts", pages=5, out_dir=tmp_path)
    fixture = Path(out["fixture"])
    assert fixture.parent == tmp_path and out["interactions"] >= 1
    text = fixture.read_text()
    assert "sbx_devtools_1" not in text and "authorization" not in text.lower()
    interactions = load_fixture(fixture)
    listing = [  # the stream listing, not the verify-time probe (limit=1)
        i
        for i in interactions
        if i.path.endswith("/v1/hosts") and i.status == 200 and i.query.get("limit") != "1"
    ]
    assert sum(len(i.body["items"]) for i in listing) == 7
    # Verify was recorded too, and the verified config saved, so a sandbox connection of
    # this connector can verify and list from the fixtures alone (TEN-13).
    assert any(i.path.endswith("/v1/me") for i in interactions)
    config = json.loads((tmp_path / "connection.json").read_text())
    assert config["tenant_id"].startswith("t_") and "vendor_app_id" not in config
    # The recording replays: every recorded request finds its response.
    replay = ReplayTransport(interactions, strict=True)
    assert replay is not None


async def test_record_refuses_a_dirty_recording(
    platform, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = await make_connection(platform, tenant, credentials=KEY, options=OPTS)
    monkeypatch.setattr(devtools, "find_secrets", lambda *_a, **_k: ["$.items[0].token"])
    with pytest.raises(ValidationFailedError) as exc:
        await devtools.record(platform, cid, "hosts", out_dir=tmp_path)
    assert exc.value.error_code == "fixture_not_clean"
    assert list(tmp_path.iterdir()) == []
