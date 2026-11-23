# Runbooks

Every operator alert links here (`obs.alert.runbook`), and every connection health code has a
page customers and support can follow. Alerts: list with `GET /v1/admin/alerts` (operators),
close with `POST /v1/admin/alerts/{id}/resolve`.

## Alerts

| Alert | Severity | Page |
|---|---|---|
| `freshness_breach` | ticket | [freshness_breach](freshness_breach.md) |
| `admission_lag` | page | [admission_lag](admission_lag.md) |
| `connector_failure_rate` | page | [connector_failure_rate](connector_failure_rate.md) |
| `sweep_aborted` | page | [sweep_aborted](sweep_aborted.md) |
| `quarantine_spike` | ticket | [quarantine_spike](quarantine_spike.md) |
| `outbox_lag` | page | [outbox_lag](outbox_lag.md) |
| `dead_deliveries` | ticket | [dead_deliveries](dead_deliveries.md) |
| `refresh_failures` | page | [refresh_failures](refresh_failures.md) |
| `internal_error` | page | [internal_error](internal_error.md) |
| `ingress_signature_failures` | ticket | [ingress_signature_failures](ingress_signature_failures.md) |
| `partition_manager_behind` | page | [partition_manager_behind](partition_manager_behind.md) |
| `raw_archive_failing` | ticket | [raw_archive_failing](raw_archive_failing.md) |
| `payload_unreadable` | ticket | [payload_unreadable](payload_unreadable.md) |

## Connection health codes

| Code | Owner | Page |
|---|---|---|
| `INITIALIZING` | PLATFORM | [initializing](health/initializing.md) |
| `UNAUTHORIZED` | CUSTOMER | [unauthorized](health/unauthorized.md) |
| `RATE_LIMIT_EXCEEDED` | VENDOR | [rate_limit_exceeded](health/rate_limit_exceeded.md) |
| `VENDOR_CLIENT_ERROR` | CUSTOMER | [vendor_client_error](health/vendor_client_error.md) |
| `VENDOR_SERVER_ERROR` | VENDOR | [vendor_server_error](health/vendor_server_error.md) |
| `EXECUTION_TIMEOUT` | PLATFORM | [execution_timeout](health/execution_timeout.md) |
| `CONFIGURATION_ERROR` | CUSTOMER | [configuration_error](health/configuration_error.md) |
| `REAUTHORIZATION_REQUIRED` | CUSTOMER | [reauthorization_required](health/reauthorization_required.md) |
| `INTERNAL_ERROR` | PLATFORM | [internal_error](health/internal_error.md) |

## Drills

- [Backup restore drill](restore_drill.md) (`make drill-restore`)
