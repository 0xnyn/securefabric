"""Alerts and their runbooks (OPS-02, OPS-06). Every alert has a runbook,
written in the same change that adds the alert (docs/runbooks/)."""

RUNBOOK_BASE = "docs/runbooks"

RUNBOOKS = {
    name: f"{RUNBOOK_BASE}/{name}.md"
    for name in (
        "freshness_breach",
        "admission_lag",
        "connector_failure_rate",
        "sweep_aborted",
        "quarantine_spike",
        "outbox_lag",
        "dead_deliveries",
        "refresh_failures",
        "internal_error",
        "ingress_signature_failures",
        "partition_manager_behind",
        "raw_archive_failing",
        "payload_unreadable",
    )
}

HEALTH_RUNBOOKS = {
    code: f"{RUNBOOK_BASE}/health/{code.lower()}.md"
    for code in (
        "INITIALIZING",
        "UNAUTHORIZED",
        "RATE_LIMIT_EXCEEDED",
        "VENDOR_CLIENT_ERROR",
        "VENDOR_SERVER_ERROR",
        "EXECUTION_TIMEOUT",
        "CONFIGURATION_ERROR",
        "REAUTHORIZATION_REQUIRED",
        "INTERNAL_ERROR",
    )
}
