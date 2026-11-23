"""The SANDBOX connector (docs/plan/05-connector-sdk.md, section 6)."""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from securefabric_cdk import (
    Action,
    ActionResult,
    Checkpoint,
    ConfigInvalid,
    Connector,
    Context,
    ExportStream,
    FeatureNotEnabled,
    GoneMarker,
    Grant,
    IngressDelivery,
    MarkDirty,
    NormalizeContext,
    Page,
    PermissionMissing,
    RawItem,
    Skip,
    Stream,
    Tombstone,
    TriggerStream,
    VendorRejected,
    VerifyResult,
    WebhookEffect,
    load_manifest,
    offset_pages,
    page_token_pages,
)
from securefabric_cdk.inprocess import InProcessTransport
from securefabric_cdk.manifest import Manifest
from securefabric_connectors.sandbox import mapping
from securefabric_connectors.sandbox.vendor import SandboxVendor
from securefabric_schema import (
    AffectedCode,
    AffectedPackage,
    Analytic,
    CvssScore,
    FindingRecord,
    GrantStatus,
    Group,
    Mode,
    Product,
    ResourceRecord,
    ResourceRef,
    ResourceRelated,
    ResourceState,
    ResourceType,
    Severity,
    Tag,
    VendorAttributes,
    Vulnerability,
)

MANIFEST = load_manifest(Path(__file__).with_name("manifest.yaml"))


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


# ---------------------------------------------------------------- hosts (offset pagination, full + sweep)


class HostsStream(Stream):
    name = "hosts"

    async def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]:
        offset = int((checkpoint or {}).get("offset") or 0)
        async for page in offset_pages(
            ctx.http, "/v1/hosts", offset=offset, limit=int(ctx.options.get("page_size", 50))
        ):
            total = page.response.json().get("total")
            yield Page(
                items=page.items,
                checkpoint={"offset": page.resume} if page.resume is not None else {},
                vendor_total=total,
            )

    async def read_one(self, ctx: Context, key: str) -> RawItem | GoneMarker:
        resp = await ctx.http.request("GET", f"/v1/hosts/{key}", allow=(404,))
        if resp.status_code == 404:
            return GoneMarker(key)
        item: RawItem = resp.json()
        return item

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> ResourceRecord:
        cloud = raw.get("cloud")
        return ResourceRecord(
            natural_key=f"host:{raw['id']}",
            type=ResourceType.HOST,
            state=mapping.HOST_STATE.get(raw.get("status", ""), ResourceState.UNKNOWN),
            name=raw.get("hostname"),
            url=None,
            groups=[Group(uid=raw["labels"]["team"], name=raw["labels"]["team"])]
            if raw.get("labels", {}).get("team")
            else [],
            tags=[
                Tag(key=k, value=v, source="sandbox")
                for k, v in sorted((raw.get("labels") or {}).items())
            ],
            data={
                "hostnames": [raw["hostname"]] if raw.get("hostname") else [],
                "fqdns": [raw["fqdn"]] if raw.get("fqdn") else [],
                "ipv4s": raw.get("ipv4") or [],
                "ipv6s": raw.get("ipv6") or [],
                "mac_addresses": raw.get("mac") or [],
                "os_version": raw.get("os"),
                "platform": raw.get("platform"),
                "agents": [
                    {
                        "vendor": "SecureFabric",
                        "product": "Sandbox Agent",
                        "version": (raw.get("agent") or {}).get("version"),
                    }
                ]
                if raw.get("agent")
                else [],
            },
            cloud_metadata={
                "cloud_provider": cloud.get("provider"),
                "account_id": cloud.get("account"),
                "region": cloud.get("region"),
                "instance_id": cloud.get("instance_id"),
            }
            if cloud
            else None,
            vendor_id=raw["id"],
            vendor_attributes_data={"vendor": "SANDBOX", "created_at": raw.get("created_at")},
            vendor_data=raw,
        )


# ---------------------------------------------------------------- images (page-token pagination, full + sweep)


class ImagesStream(Stream):
    name = "images"

    async def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]:
        token = (checkpoint or {}).get("page_token")
        async for page in page_token_pages(
            ctx.http,
            "/v1/images",
            page_token=token,
            params={"pageSize": int(ctx.options.get("page_size", 50))},
        ):
            yield Page(
                items=page.items, checkpoint={"page_token": page.resume} if page.resume else {}
            )

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> ResourceRecord:
        is_container = raw.get("kind") == "container"
        algo, _, value = (raw.get("digest") or ":").partition(":")
        data: dict[str, Any] = (
            {"hostnames": [], "image": f"{raw['name']}:{raw['tag']}"}
            if is_container
            else {
                "hash": {"algorithm": algo or None, "value": value or None},
                "labels": raw.get("labels") or [],
            }
        )
        return ResourceRecord(
            natural_key=f"{'container' if is_container else 'image'}:{raw['id']}",
            type=ResourceType.CONTAINER if is_container else ResourceType.IMAGE,
            state=ResourceState.ACTIVE,
            name=f"{raw['name']}:{raw['tag']}",
            data=data,
            vendor_id=raw["id"],
            vendor_attributes_data={"vendor": "SANDBOX", "host_id": raw.get("host_id")},
            vendor_data=raw,
        )


# ---------------------------------------------------------------- findings (since-filter incremental)


def normalize_finding(raw: RawItem, nctx: NormalizeContext) -> FindingRecord | Tombstone:
    key = f"finding:{raw['id']}"
    if raw.get("removed"):
        return Tombstone("vulnerability_finding", key)
    kind = raw["kind"]
    severity = mapping.SEVERITY.get(raw.get("risk", ""), Severity.UNKNOWN)
    pkg = raw.get("package")
    loc = raw.get("location")
    cvss = raw.get("cvss")
    related = ResourceRelated(
        affected_code=AffectedCode(
            file_path=loc["path"],
            start_line_number=loc["line"],
            end_line_number=loc["line"],
            url=loc.get("url"),
        )
        if loc
        else None,
        affected_package=AffectedPackage(
            name=pkg["name"],
            version=pkg.get("installed"),
            package_manager=pkg.get("ecosystem"),
            reachability=mapping.REACHABILITY.get(raw.get("reachable") or ""),
            fixed_version=pkg.get("fixed"),
        )
        if pkg
        else None,
        port=raw.get("port"),
        protocol=raw.get("protocol"),
        service=raw.get("domain"),
    )
    asset = raw.get("asset")
    resources = []
    if asset:
        rtype = mapping.ASSET_TYPE[asset["type"]]
        resources.append(
            ResourceRef(
                natural_key=f"{asset['type']}:{asset['id']}",
                type=rtype,
                role="primary",
                name=asset["id"],
                stream="hosts" if rtype is ResourceType.HOST else "images",
            )
        )
    vulns = [
        Vulnerability(
            uid=cve,
            cvss_scores=[
                CvssScore(
                    version=cvss["version"], score=float(cvss["score"]), vector=cvss["vector"]
                )
            ]
            if cvss
            else [],
            weaknesses=list(raw.get("cwe") or []),
        )
        for cve in raw.get("cves") or []
    ]
    status = raw.get("status", "")
    return FindingRecord(
        natural_key=key,
        type=mapping.FINDING_TYPE.get(kind, mapping.FINDING_TYPE["misc"]),
        title=raw.get("title"),
        description=raw.get("summary"),
        severity=severity,
        state=mapping.STATE[status],
        state_changed_at=_dt(raw.get("resolved_at")) if status != "open" else None,
        has_fix=raw.get("fix_available"),
        exploitable=raw.get("exploit_known"),
        reachability=mapping.REACHABILITY.get(raw.get("reachable") or ""),
        remediation=f"Upgrade {pkg['name']} to {pkg['fixed']} or later."
        if pkg and pkg.get("fixed")
        else None,
        analytic=Analytic(
            uid=raw["rule"]["id"], name=raw["rule"]["name"], type=raw["rule"]["category"]
        )
        if raw.get("rule")
        else None,
        product=Product(name="Sandbox Scanner", vendor_name="SecureFabric"),
        resource_related=[related] if related != ResourceRelated() else [],
        vulnerabilities=vulns,
        cve_ids=list(raw.get("cves") or []),
        vendor=VendorAttributes(
            id=raw["id"],
            url=raw.get("url"),
            severity=raw.get("risk"),
            state=status,
            created_at=_dt(raw.get("created_at")),
            updated_at=_dt(raw.get("updated_at")),
            data={
                "vendor": "SANDBOX",
                "rule_category": (raw.get("rule") or {}).get("category"),
                "comment": raw.get("comment"),
            },
        ),
        resources=resources,
        vendor_data=raw,
    )


class FindingsStream(Stream):
    name = "findings"

    async def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]:
        ckpt = dict(checkpoint or {})
        walk = ckpt.get("walk")
        watermark: str | None = ckpt.get("watermark")
        if mode in (Mode.FULL, Mode.BACKFILL) and not (walk and walk.get("full")):
            since = None
            if mode is Mode.BACKFILL and ctx.options.get("initial_lookback_days"):
                since = (
                    ctx.now() - timedelta(days=int(ctx.options["initial_lookback_days"]))
                ).isoformat()
            walk = {"since": since, "token": None, "max_seen": watermark, "full": True}
        elif not walk:
            walk = {"since": watermark, "token": None, "max_seen": watermark, "full": False}
        params: dict[str, Any] = {"pageSize": int(ctx.options.get("page_size", 50))}
        if walk["since"]:
            params["since"] = walk["since"]
        async for page in page_token_pages(
            ctx.http, "/v1/findings", params=params, page_token=walk["token"]
        ):
            for item in page.items:
                if walk["max_seen"] is None or item["updated_at"] > walk["max_seen"]:
                    walk["max_seen"] = item["updated_at"]
            if page.resume:
                walk = {**walk, "token": page.resume}
                yield Page(items=page.items, checkpoint={"watermark": watermark, "walk": walk})
            else:
                yield Page(
                    items=page.items,
                    checkpoint={"watermark": walk["max_seen"], "walk": None},
                    vendor_total=page.response.json().get("total"),
                )

    async def read_one(self, ctx: Context, key: str) -> RawItem | GoneMarker:
        vendor_id = key.removeprefix("finding:")
        resp = await ctx.http.request("GET", f"/v1/findings/{vendor_id}", allow=(404,))
        if resp.status_code == 404:
            return GoneMarker(key)
        item: RawItem = resp.json()
        return item

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> FindingRecord | Tombstone:
        return normalize_finding(raw, nctx)


class FindingExportsStream(ExportStream):
    """Bulk findings through the vendor's async export (SYNC-16)."""

    name = "finding_exports"

    async def request_export(self, ctx: Context, since: str | None) -> str:
        resp = await ctx.http.request(
            "POST", "/v1/exports", json_body={"since": since, "chunk_size": 500}
        )
        export_id: str = resp.json()["export_id"]
        return export_id

    async def poll(self, ctx: Context, export_id: str) -> dict[str, Any]:
        resp = await ctx.http.request("GET", f"/v1/exports/{export_id}", allow=(404,))
        if resp.status_code == 404:
            return {"status": "expired"}
        body: dict[str, Any] = resp.json()
        return body

    async def read_chunk(self, ctx: Context, export_id: str, chunk: Any) -> list[RawItem]:
        resp = await ctx.http.request("GET", f"/v1/exports/{export_id}/chunks/{chunk}")
        items: list[RawItem] = resp.json()["items"]
        return items

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> FindingRecord | Tombstone | Skip:
        return normalize_finding(raw, nctx)


# ---------------------------------------------------------------- the connector


class SandboxConnector(Connector):
    manifest = MANIFEST
    stream_classes = (HostsStream, ImagesStream, FindingsStream, FindingExportsStream)

    def base_url(self, config: dict[str, Any], vendor_app: dict[str, Any] | None) -> str:
        region = config.get("region") or "us"
        for r in self.manifest.regions:
            if r.id == region:
                return r.api_base
        raise ConfigInvalid(f"unknown sandbox region {region!r}")

    def local_transport(self, config: dict[str, Any], options: dict[str, Any]) -> Any:
        return InProcessTransport(SandboxVendor(options))

    async def verify(self, ctx: Context) -> VerifyResult:
        me = await ctx.http.get_json("/v1/me")
        return VerifyResult(
            tenant_identity=me["tenant_id"],
            display_name=me["name"],
            config_updates={
                "tenant_id": me["tenant_id"],
                "tenant_name": me["name"],
                "region": ctx.options.get("region", "us"),
            },
            vendor_tenant_ref=me["tenant_id"],
        )

    async def probe(self, ctx: Context, stream: str) -> Grant:
        path = {
            "hosts": "/v1/hosts",
            "images": "/v1/images",
            "findings": "/v1/findings",
            "finding_exports": "/v1/findings",
        }[stream]
        endpoint = f"GET {path}"
        try:
            resp = await ctx.http.request(
                "GET", path, params={"limit": 1, "pageSize": 1}, allow=(403, 404)
            )
        except (PermissionMissing, FeatureNotEnabled, VendorRejected) as exc:
            return Grant(GrantStatus.UNKNOWN, endpoint, str(exc))
        if resp.status_code == 403:
            return Grant(GrantStatus.UNAUTHORIZED, endpoint, "missing scope")
        if resp.status_code == 404:
            return Grant(GrantStatus.NOT_ENABLED, endpoint, "feature not enabled for this tenant")
        return Grant(GrantStatus.GRANTED, endpoint)

    def handle_webhook(
        self, delivery: IngressDelivery, *, config: dict[str, Any], options: dict[str, Any]
    ) -> list[WebhookEffect]:
        if delivery.event == "finding":
            fid = (delivery.payload.get("finding") or {}).get("id")
            return (
                [MarkDirty("findings", f"finding:{fid}", reason=delivery.action or "")]
                if fid
                else []
            )
        if delivery.event == "asset":
            return [TriggerStream("hosts", reason="asset changed")]
        return []

    async def perform(self, ctx: Context, action: Action) -> ActionResult:
        if action.name != "finding.set_state":
            raise ConfigInvalid(f"unknown action {action.name}")
        state = action.params["state"]
        reason = action.params.get("reason") if state == "IGNORED" else None
        status = mapping.SET_STATE.get((state, reason))
        if status is None:
            raise ConfigInvalid(f"cannot set {state} with reason {reason}")
        vendor_id = action.record["vendor_id"]
        resp = await ctx.http.request(
            "POST",
            f"/v1/findings/{vendor_id}/state",
            json_body={"status": status, "comment": action.params.get("comment")},
        )
        return ActionResult(
            status="SUCCEEDED",
            vendor_response=resp.json(),
            refetch=[MarkDirty("findings", f"finding:{vendor_id}", reason="write-back")],
        )


# ---------------------------------------------------------------- OAuth variants
#
# Same vendor, streams and normalisers; only how a connection authenticates differs.
# They exercise what GitHub never needs (part 5, section 6): OAuth2 authorization
# code with PKCE and single-use refresh tokens, and client credentials.


def _variant(**changes: Any) -> Manifest:
    data = MANIFEST.model_dump(mode="json", exclude_none=True)
    data.update(changes)
    return Manifest.model_validate(data)


OAUTH_MANIFEST = _variant(
    id="SANDBOX_OAUTH",
    display_name="SecureFabric Sandbox (OAuth)",
    description=(
        "The sandbox vendor behind an OAuth2 authorization-code flow with PKCE and "
        "single-use refresh tokens. Connects through a redirect, like a real OAuth vendor."
    ),
    auth={
        "mode": "OAUTH2",
        "vendor_app": "required",
        "connect": "redirect",
        "oauth2": {
            "authorize_url": "local:/oauth/authorize",
            "token_url": "/oauth/token",
            "scopes": ["read"],
            "pkce": True,
            "single_use_refresh_tokens": True,
        },
        "token_refresh_margin_s": 300,
    },
    credentials={
        "type": "object",
        "properties": {
            "refresh_token": {
                "title": "Refresh token",
                "description": "Set by the authorization flow, never entered by hand.",
                "type": "string",
                "x-secret": True,
                "readOnly": True,
            }
        },
        "additionalProperties": False,
    },
)

CC_MANIFEST = _variant(
    id="SANDBOX_CC",
    display_name="SecureFabric Sandbox (client credentials)",
    description="The sandbox vendor behind OAuth2 client credentials: tokens are minted and cached.",
    auth={
        "mode": "OAUTH2_CC",
        "connect": "form",
        "oauth2": {"token_url": "/oauth/token", "scopes": ["read"]},
        "token_refresh_margin_s": 300,
    },
    credentials={
        "type": "object",
        "required": ["client_id", "client_secret"],
        "properties": {
            "client_id": {
                "title": "Client ID",
                "description": "Any value starting with sbxc_ (sbxc_revoked* is refused).",
                "type": "string",
                "pattern": "^sbxc_[A-Za-z0-9_]{4,}$",
                "x-order": 1,
            },
            "client_secret": {
                "title": "Client secret",
                "description": "For a sandbox client: GET /v1/connectors/SANDBOX_CC shows how to derive it.",
                "type": "string",
                "x-secret": True,
                "x-order": 2,
            },
        },
        "additionalProperties": False,
    },
)

PLATFORM_OAUTH_CLIENT = "sbxc_platform_oauth"


class SandboxOAuthConnector(SandboxConnector):
    manifest = OAUTH_MANIFEST

    def platform_app(self) -> dict[str, Any] | None:
        from securefabric_connectors.sandbox.oauth import client_secret_for

        return {
            "name": "SecureFabric Sandbox OAuth client",
            "base_url": self.manifest.regions[0].api_base,
            "config": {"client_id": PLATFORM_OAUTH_CLIENT},
            "secrets": {"client_secret": client_secret_for(PLATFORM_OAUTH_CLIENT)},
        }


class SandboxClientCredentialsConnector(SandboxConnector):
    manifest = CC_MANIFEST
