"""Metrics through OpenTelemetry (OPS-03; docs/plan/09-operations-security-quality.md).

Every instrument is defined here, once, with its unit and description, so the set
an engineer on call can chart is one file. Services call ``configure_telemetry``
at start: with ``OTEL_EXPORTER_OTLP_ENDPOINT`` set, metrics export over OTLP/HTTP
every ``OTEL_METRIC_EXPORT_INTERVAL`` ms (the standard variables); without it the
API's no-op meter makes every call free. Tests install an in-memory reader.

Attributes are low-cardinality by rule: connector, stream, route template, status
class, outcome, role. Never ids of tenants, connections or runs.
"""

import os
from typing import Any

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, Meter, _Gauge

_METER_NAME = "securefabric"
_configured = False


class Instruments:
    """The OPS-03 metric set."""

    def __init__(self, meter: Meter) -> None:
        # Per connector
        self.vendor_request_duration: Histogram = meter.create_histogram(
            "securefabric.vendor.request.duration",
            unit="s",
            description="Vendor HTTP request latency (attrs: connector, status_class)",
        )
        self.vendor_requests: Counter = meter.create_counter(
            "securefabric.vendor.requests",
            description="Vendor HTTP requests (attrs: connector, status_class; 429 and 5xx rates)",
        )
        self.run_duration: Histogram = meter.create_histogram(
            "securefabric.run.duration",
            unit="s",
            description="Stream run slice duration (attrs: connector, stream, outcome)",
        )
        self.run_requests: Histogram = meter.create_histogram(
            "securefabric.run.vendor_requests",
            description="Vendor requests per run slice (attrs: connector, stream)",
        )
        self.records_written: Counter = meter.create_counter(
            "securefabric.records.written",
            description="Records written (attrs: connector, stream, change: added|updated|deleted)",
        )
        self.records_quarantined: Counter = meter.create_counter(
            "securefabric.records.quarantined",
            description="Records quarantined by canonical validation (attrs: connector, stream)",
        )
        # Scheduler
        self.admission_lag: _Gauge = meter.create_gauge(
            "securefabric.scheduler.admission_lag",
            unit="s",
            description="Age of the oldest admissible stream run",
        )
        self.runs_by_state: _Gauge = meter.create_gauge(
            "securefabric.scheduler.runs",
            description="Active stream runs (attrs: state, priority)",
        )
        self.schedule_lateness: _Gauge = meter.create_gauge(
            "securefabric.scheduler.schedule_lateness",
            unit="s",
            description="How far the most overdue started schedule is past next_run_at",
        )
        # Store
        self.batch_write_duration: Histogram = meter.create_histogram(
            "securefabric.store.batch_write.duration",
            unit="s",
            description="records.apply_batch latency incl. lock wait (attrs: object_type)",
        )
        # API
        self.api_request_duration: Histogram = meter.create_histogram(
            "securefabric.api.request.duration",
            unit="s",
            description="API latency (attrs: route, method, status_class)",
        )
        self.api_rate_limited: Counter = meter.create_counter(
            "securefabric.api.rate_limited",
            description="Requests rejected by the per-environment rate limit",
        )
        # Events
        self.outbox_lag: _Gauge = meter.create_gauge(
            "securefabric.events.outbox_lag",
            unit="s",
            description="Age of the oldest undispatched outbox event (0 when drained)",
        )
        self.webhook_deliveries: Counter = meter.create_counter(
            "securefabric.events.webhook_deliveries",
            description="Webhook delivery attempts (attrs: outcome: delivered|retry|dead|permanent)",
        )
        # Vault
        self.vault_opens: Counter = meter.create_counter(
            "securefabric.vault.opens",
            description="Sealed envelopes opened (attrs: role, purpose). A rise is a security signal",
        )


_instruments: Instruments | None = None


def instruments() -> Instruments:
    """The process's instruments (bound to whatever meter provider is current)."""
    global _instruments
    if _instruments is None:
        _instruments = Instruments(metrics.get_meter(_METER_NAME))
    return _instruments


def reset_instruments() -> None:
    """Re-bind after a test installs its own meter provider."""
    global _instruments
    _instruments = None


def configure_telemetry(service_name: str, *, environment: str | None = None) -> bool:
    """Install the OTLP exporter when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.
    Returns whether export is on. Safe to call more than once."""
    global _configured
    if _configured or not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return _configured
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    attrs: dict[str, Any] = {"service.name": service_name}
    if environment:
        attrs["deployment.environment"] = environment
    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    metrics.set_meter_provider(
        MeterProvider(resource=Resource.create(attrs), metric_readers=[reader])
    )
    reset_instruments()
    _configured = True
    return True


def status_class(status: int | None) -> str:
    """``2xx``, ``4xx``, ``5xx``; 429 kept apart (rate limiting is its own signal);
    ``error`` when no response arrived."""
    if status is None:
        return "error"
    return "429" if status == 429 else f"{status // 100}xx"
