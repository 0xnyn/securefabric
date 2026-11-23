# Migrating from Leen V2

SecureFabric's data API is wire-compatible with Leen V2 (PD-9): the same resources and
vulnerability findings, the same field names and shapes, the same filters and pagination
envelope. Our responses validate against Leen's published OpenAPI document; CI checks that
on every change (`apps/api/tests/test_data.py`, the Leen contract test). A Leen client needs
the changes below, nothing else.

## Required changes

1. **Base URL and version.** Replace `https://api.leen.dev/v2` with your SecureFabric API
   URL and `/v1`: `GET /v2/vulnerability_findings` becomes `GET /v1/vulnerability_findings`,
   `GET /v2/resources` becomes `GET /v1/resources`, and so on.
2. **API key.** Create a key in the dashboard (Keys) or with `POST /v1/api_keys`. Keys start with
   `sfk_`, are shown once and are bound to one environment and region. Send it exactly as
   before in `X-API-KEY` (or as `Authorization: Bearer sfk_…`).
3. **Connection ids.** Connections are created again through SecureFabric's connect flow, so
   their ids are new. `X-CONNECTION-ID` works as in Leen with the new ids.
4. **Webhook verification.** Leen signs `X-Leen-Signature: v0=sha256=<hex>`; SecureFabric signs
   `SecureFabric-Signature: v1=<hex>` with `SecureFabric-Timestamp`. The signed message is the
   same (`"{timestamp}.{raw body}"`, HMAC-SHA256), so only the header names and the `v1=`
   prefix change. See [Receiving webhooks](webhooks.md).
5. **Health codes.** Leen's resolution owner `LEEN` is `PLATFORM` here, and Leen's
   `CONNECTION_RECONFIGURATION_REQUIRED` is split into `CONFIGURATION_ERROR` (options or base
   URL wrong) and `REAUTHORIZATION_REQUIRED` (token refresh keeps failing). Map both if your
   code switches on the old value.

## Behaviour that differs (compatible, but worth knowing)

- **Cursors with filters.** Leen returns 422 for `cursor` together with `updatedSince`. We
  accept a cursor with the same filters it was issued for (cursors are signed and carry the
  filter set) and return 400 naming the filter if they differ. Code that never combined
  them is unaffected.
- **Unsupported filters.** A filter a connector cannot evaluate is reported in the
  `X-Unsupported-Filters` response header instead of being silently ignored.
- **Errors** are RFC 9457 `application/problem+json` with a stable `code`, `request_id` and,
  for validation errors, `errors[].field`.
- **Organization scope.** Leen has no `X-ORGANIZATION-ID`; we accept it to query every
  connection of one organization at once. Without it, nothing changes.

## Additions you can adopt later

- Finding filters `type` and `cveId` (matches through GHSA/OSV aliases), sorts
  `first_seen` and `last_seen`, `changeType=added,updated,deleted` for a change feed that
  includes deletions, and `include=resources`.
- `GET /v1/vulnerability_findings/{id}/history` (state history),
  `GET /v1/vulnerability_findings/summary`, `GET /v1/enrichments/cves/{cve_id}` (NVD, KEV,
  EPSS), and `enrichment` on findings.
- A `_meta` block on every record (`stream`, `natural_key`, `derived` fields), repository
  resources with `data.repo_url`, `default_branch` and `security_features`, and write-back
  (`POST /v1/vulnerability_findings/{id}/actions`).
- Webhook events beyond Leen's `connection.sync.*`: `sync.completed`,
  `connection.health.changed`, lifecycle and action events, plus the `GET /v1/events` feed.

## Checklist

- [ ] Base URL and `/v1` prefix changed
- [ ] New API key in `X-API-KEY`
- [ ] Connections re-created; stored connection ids updated
- [ ] Webhook verifier switched to `SecureFabric-Signature` / `SecureFabric-Timestamp`
- [ ] Health-code handling covers `PLATFORM`, `CONFIGURATION_ERROR`, `REAUTHORIZATION_REQUIRED`
