"""OPS-03: the metric set is emitted, with low-cardinality attributes only."""

import re
from collections.abc import Iterator
from typing import Any

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from securefabric_core import telemetry
from securefabric_domain.sync.scheduler import Scheduler
from securefabric_domain.testing import EngineDriver, run_control

pytestmark = pytest.mark.integration

UUIDISH = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-")


@pytest.fixture
def reader(monkeypatch: pytest.MonkeyPatch) -> Iterator[InMemoryMetricReader]:
    r = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[r])
    monkeypatch.setattr(
        telemetry, "_instruments", telemetry.Instruments(provider.get_meter("securefabric"))
    )
    yield r
    provider.shutdown()


def collected(reader: InMemoryMetricReader) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    data = reader.get_metrics_data()
    for rm in data.resource_metrics if data else []:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                out.setdefault(m.name, []).extend(
                    dict(p.attributes or {}) for p in m.data.data_points
                )
    return out


async def test_sync_api_and_vault_emit_the_ops_03_metrics(api, reader) -> None:
    org = (await api.post("/v1/organizations", {"identifier": "otel", "name": "O"})).json()["id"]
    c = await api.post(
        f"/v1/organizations/{org}/connections",
        {
            "vendor": "SANDBOX",
            "credentials": {"api_key": "sbx_otel_1"},
            "options": {"finding_count": 9},
        },
    )
    assert c.status_code == 201, c.text
    await run_control(api.worker)
    await EngineDriver(api.worker).drain()
    await Scheduler(api.worker).record_gauges()

    got = collected(reader)
    for name in (
        "securefabric.api.request.duration",
        "securefabric.vendor.requests",
        "securefabric.vendor.request.duration",
        "securefabric.run.duration",
        "securefabric.run.vendor_requests",
        "securefabric.records.written",
        "securefabric.store.batch_write.duration",
        "securefabric.vault.opens",
        "securefabric.scheduler.admission_lag",
        "securefabric.events.outbox_lag",
    ):
        assert name in got, f"{name} not emitted; got {sorted(got)}"

    assert {"connector": "SANDBOX", "status_class": "2xx"} in got["securefabric.vendor.requests"]
    routes = {a["route"] for a in got["securefabric.api.request.duration"]}
    assert "/v1/organizations/{organization_id}/connections" in routes  # templates, not paths
    assert any(a.get("change") == "added" for a in got["securefabric.records.written"])
    assert {"role": "test", "purpose": "credential"} in got["securefabric.vault.opens"]

    # The cardinality rule: no attribute value is a tenant, connection or run id.
    for name, points in got.items():
        for attrs in points:
            for v in attrs.values():
                assert not UUIDISH.search(str(v)), f"{name} carries an id: {attrs}"


def test_status_class_keeps_429_apart() -> None:
    assert telemetry.status_class(200) == "2xx" and telemetry.status_class(503) == "5xx"
    assert telemetry.status_class(429) == "429" and telemetry.status_class(None) == "error"


def test_without_an_endpoint_export_stays_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setattr(telemetry, "_configured", False)
    assert telemetry.configure_telemetry("t") is False
