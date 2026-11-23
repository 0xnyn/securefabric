# Leen V2 and WorkOS facts used by the build

Collected 2026-11-23 from docs.leen.dev (OpenAPI `openapi_v2.json`, copied to
`packages/schema/tests/leen/openapi_v2.json` and used as a contract test) and
workos.com/docs. Where the plan (docs/plan) assumed otherwise, the build follows
these facts and the difference is noted.

## Leen V2 (PD-9 wire compatibility)

- Data endpoints: `GET /v2/vulnerability_findings[/{id}]`, `GET /v2/resources[/{id}]`.
  Headers `X-API-KEY` and `X-CONNECTION-ID`. **Leen has no `X-ORGANIZATION-ID`**:
  ours is additive (TEN-12).
- Envelope `{items, next_cursor, previous_cursor}`; `limit` 1–500, default 100.
  Leen returns 422 for `cursor` + `updatedSince`; we accept a matching filter set
  (part 7, section 4).
- Finding filters: `sort` (`severity|updated_at|state_updated_at[:asc|:desc]`),
  `severity`, `state`, `has_fix`, `reachability`, `exploitable`, `firstSeenSince`,
  `lastSeenSince`, `stateUpdatedSince`, `resourceId`, `ids` (≤100), `updatedSince`.
  `null` for tri-state filters is 422. Leen has no `type`/`cveId` filter: ours are additive.
- Resource filters: `updatedSince`, `name`, `vendor`, `state`, `type`.
- Finding shape: `remediation` and `analytic_output` are strings; `resource_related` is a
  **list** of `{affected_code{file_path,start_line_number,end_line_number,url},
  affected_package{name,version,package_manager,reachability}, affected_image,
  affected_os, affected_platform, port, protocol, service}`; `vulnerabilities[]` is
  `{uid, description, published, last_modified, created_at, updated_at,
  source_identifier, status, weaknesses:[string], cvss_scores:[{version,score,vector,severity}],
  references:[{url,source,tags}]}`; `vendor_attributes{id,url,severity,state,created_at,
  updated_at,vulnerability_identifiers:[{type,value}],data:{vendor:"GITHUB",...}}`;
  timestamps `first_seen`, `last_seen`, `state_updated_at`.
- GitHub `vendor_attributes.data` keys: `analysis_key, bypassed, bypassed_comment,
  classifications, commit_sha, dismissed_comment, dismissed_reason, environment,
  has_more_locations, is_base64_encoded, multi_repo, publicly_leaked, ref, resolution, validity`.
- Resource shape: required `id, name, type, state, vendor, vendor_attributes{id,data}`;
  `groups[{name,uid}]`, `tags[{key,value,source}]`, `data` is a flat union
  (branch `{code_repo, repo_branch_name}`, host, container, image). Leen has no
  repository data shape: ours (`repo_url`, `default_branch`, `security_features`, ...) is additive.
- Health: `{name, status, description, resolution_owner, details[{data_export_type, endpoint}]}`.
  Leen's owner `LEEN` is our `PLATFORM`; Leen's `CONNECTION_RECONFIGURATION_REQUIRED`
  is split into our `CONFIGURATION_ERROR` and `REAUTHORIZATION_REQUIRED` (part 3, section 7).
- Webhooks: Leen signs `X-Leen-Signature: v0=sha256=<hex>` over `{timestamp}.{body}`;
  ours is `SecureFabric-Signature: v1=<hex>` over the same message (HOOK-03).
- S11 (secret severity): Leen does not document it. Our `UNKNOWN` default stands.

## WorkOS AuthKit

- Access tokens are RS256 JWTs verified against `GET https://api.workos.com/sso/jwks/{client_id}`.
  Claims: `sub` (user id), `sid`, `org_id` and `role` (only when an org is selected),
  `iss`, `exp`, `iat`, `client_id`. No `aud` by default. `iss` is documented as
  `https://api.workos.com` (also seen with a trailing slash), so verification accepts
  either plus `https://api.workos.com/user_management/{client_id}`.
- Hosted login: `GET /user_management/authorize?response_type=code&client_id&redirect_uri&provider=authkit`,
  then `POST /user_management/authenticate` `{client_id, client_secret, grant_type: authorization_code, code}`
  → `{user, organization_id, access_token, refresh_token}`. Refresh tokens rotate on use.
- `GET /user_management/users/{id}`, `POST /organizations`,
  `POST /user_management/organization_memberships`, `POST /user_management/invitations`.
