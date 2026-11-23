"""The GitHub Advanced Security connector (docs/plan/06-github-connector.md)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

from securefabric_cdk import (
    Action,
    ActionResult,
    AuthRejected,
    Checkpoint,
    ConfigInvalid,
    ConnectionRestored,
    ConnectionRevoked,
    Connector,
    Context,
    FeatureNotEnabled,
    GoneMarker,
    Grant,
    Ignore,
    IngressDelivery,
    MarkDirty,
    NormalizeContext,
    Page,
    PermissionMissing,
    RawItem,
    ReprobeGrants,
    Skip,
    Stream,
    TriggerStream,
    UpdateConfig,
    VendorRejected,
    VerifyResult,
    WebhookEffect,
    link_header_pages,
    load_manifest,
)
from securefabric_cdk.auth import github_app_jwt
from securefabric_cdk.manifest import version_at_least
from securefabric_cdk.tokens import CachedToken
from securefabric_cdk.types import AuthPlan
from securefabric_connectors.github import mapping
from securefabric_connectors.github.normalize import (
    NORMALIZERS,
    normalize_branch,
    normalize_repository,
)
from securefabric_schema import FindingRecord, GrantStatus, Mode, ResourceRecord

MANIFEST = load_manifest(Path(__file__).with_name("manifest.yaml"))

PER_PAGE = 100

# Oldest GHES release with each organization-level alert listing; older releases are
# listed repository by repository (verified against github/rest-api-description).
ORG_LISTING_MIN_GHES = {"code_scanning": "3.5", "secret_scanning": "3.3", "dependabot": "3.8"}
LOCATIONS_MIN_GHES = "3.3"


def listing_mode_for(options: dict[str, Any], config: dict[str, Any], family: str) -> str:
    chosen = options.get("listing_mode", "auto")
    if chosen in ("org", "per_repo"):
        mode = str(chosen)
    else:
        mode = str(
            config.get("listing_mode")
            or (
                "org"
                if config.get("account_type") == "Organization"
                and config.get("repository_selection") != "selected"
                else "per_repo"
            )
        )
    if mode == "org" and not version_at_least(
        config.get("server_version"), ORG_LISTING_MIN_GHES.get(family)
    ):
        return "per_repo"
    return mode


OVERLAP = timedelta(minutes=5)  # incremental walks re-read a little (part 6, section 5)

# GitHub's wording for "the feature is off here" versus "you lack the permission".
_NOT_ENABLED_MARKERS = (
    "advanced security must be enabled",
    "secret scanning is disabled",
    "code scanning is not enabled",
    "dependabot alerts are disabled",
    "dependabot alerts are not available",
    "no analysis found",
    "not enabled",
    "is disabled",
)
_NO_PERMISSION_MARKERS = ("resource not accessible by integration",)


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _classify_403_404(exc: VendorRejected, stream: str, scope: str) -> Exception:
    body = (exc.body or "").lower()
    if exc.status == 404 or any(m in body for m in _NOT_ENABLED_MARKERS):
        return FeatureNotEnabled(stream, scope, message=exc.body[:300])
    if any(m in body for m in _NO_PERMISSION_MARKERS):
        return PermissionMissing(stream, exc.endpoint, message=exc.body[:300])
    return exc


def _minimal_repo(repo: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id",
        "node_id",
        "name",
        "full_name",
        "html_url",
        "private",
        "archived",
        "default_branch",
        "fork",
    )
    out = {k: repo.get(k) for k in keep if k in repo}
    owner = repo.get("owner") or {}
    out["owner"] = {"login": owner.get("login"), "id": owner.get("id"), "type": owner.get("type")}
    return out


async def _repositories(
    ctx: Context, resume_url: str | None = None
) -> AsyncIterator[tuple[list[dict[str, Any]], str | None, int | None]]:
    """``GET /installation/repositories``: exactly what the installation can see."""
    async for page in link_header_pages(
        ctx.http,
        "/installation/repositories",
        params={"per_page": PER_PAGE},
        resume_url=resume_url,
        items_key="repositories",
    ):
        total = page.response.json().get("total_count")
        yield page.items, page.resume, total


# ---------------------------------------------------------------- repositories


class RepositoriesStream(Stream):
    name = "repositories"

    async def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]:
        resume = (checkpoint or {}).get("next")
        async for items, nxt, total in _repositories(ctx, resume):
            yield Page(items=items, checkpoint={"next": nxt} if nxt else {}, vendor_total=total)

    async def read_one(self, ctx: Context, key: str) -> RawItem | GoneMarker:
        repo_id = key.removeprefix("repo:")
        resp = await ctx.http.request("GET", f"/repositories/{repo_id}", allow=(404, 403))
        if resp.status_code in (403, 404):
            return GoneMarker(key)
        item: RawItem = resp.json()
        return item

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> ResourceRecord:
        return normalize_repository(raw, nctx)


# ---------------------------------------------------------------- branches


class BranchesStream(Stream):
    name = "branches"

    async def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]:
        scope = ctx.options.get("branch_scope", "default")
        resume = (checkpoint or {}).get("next")
        async for repos, nxt, total in _repositories(ctx, resume):
            items: list[RawItem] = []
            for repo in repos:
                ctx.check()
                minimal = _minimal_repo(repo)
                if scope == "default":
                    if repo.get("default_branch"):
                        items.append(
                            {
                                "repository": minimal,
                                "branch": {"name": repo["default_branch"], "protected": None},
                            }
                        )
                    continue
                params: dict[str, Any] = {"per_page": PER_PAGE}
                if scope == "protected":
                    params["protected"] = "true"
                async for bpage in link_header_pages(
                    ctx.http,
                    f"/repos/{repo['full_name']}/branches",
                    params=params,
                    allow=(404, 409),
                ):
                    for b in bpage.items:
                        items.append(
                            {
                                "repository": minimal,
                                "branch": {
                                    "name": b["name"],
                                    "protected": b.get("protected"),
                                    "commit": {"sha": (b.get("commit") or {}).get("sha")},
                                },
                            }
                        )
            yield Page(
                items=items,
                checkpoint={"next": nxt} if nxt else {},
                vendor_total=total if scope == "default" else None,
            )

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> ResourceRecord | Skip:
        return normalize_branch(raw, nctx)


# ---------------------------------------------------------------- alerts (shared)


class AlertStream(Stream):
    family: ClassVar[str]

    def _listing_mode(self, ctx: Context) -> str:
        return listing_mode_for(ctx.options, ctx.config, self.family)

    def _params(self, *, incremental: bool) -> dict[str, Any]:
        params: dict[str, Any] = {
            "per_page": PER_PAGE,
            "sort": "updated" if incremental else "created",
            "direction": "desc" if incremental else "asc",
        }
        if self.family == "secret_scanning":
            params["hide_secret"] = "true"  # the secret itself is never fetched  # noqa: S105
        return params

    async def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]:
        ckpt = dict(checkpoint or {})
        watermark: str | None = ckpt.get("watermark")
        full = mode in (Mode.FULL, Mode.BACKFILL) or watermark is None
        walk = ckpt.get("walk")
        if not walk or bool(walk.get("full")) != full:
            walk = {
                "full": full,
                "target": watermark,
                "cursor": None,
                "max_seen": watermark,
                "repo_page": None,
                "repo_index": 0,
            }
        cutoff = None
        if not full and walk["target"]:
            cutoff = (_parse_ts(walk["target"]) - OVERLAP).isoformat()

        if self._listing_mode(ctx) == "org":
            org = ctx.config.get("account_login")
            if not org:
                raise ConfigInvalid("connection has no account_login")
            path = f"/orgs/{org}/{mapping.FAMILY_PATH[self.family]}"
            async for page in self._walk(ctx, path, walk, cutoff, repo=None):
                yield page
        else:
            async for page in self._walk_per_repo(ctx, walk, cutoff):
                yield page
        # The walk completed: commit the new watermark (only now, part 6, section 5).
        yield Page(items=[], checkpoint={"watermark": walk["max_seen"], "walk": None})

    async def _walk(
        self,
        ctx: Context,
        path: str,
        walk: dict[str, Any],
        cutoff: str | None,
        repo: dict[str, Any] | None,
    ) -> AsyncIterator[Page]:
        params = self._params(incremental=not walk["full"])
        resume = walk.get("cursor")
        restarted = False
        while True:
            try:
                async for page in link_header_pages(
                    ctx.http, path, params=params, resume_url=resume
                ):
                    ctx.check()
                    items = []
                    stop = False
                    for item in page.items:
                        if repo is not None:
                            item["repository"] = repo
                        updated = item.get("updated_at") or item.get("created_at")
                        if updated and (walk["max_seen"] is None or updated > walk["max_seen"]):
                            walk["max_seen"] = updated
                        if cutoff and updated and _parse_ts(updated) < _parse_ts(cutoff):
                            stop = True
                            break
                        items.append(item)
                    await self._enrich(ctx, items)
                    walk["cursor"] = None if stop else page.resume
                    yield Page(
                        items=items,
                        checkpoint={
                            "watermark": walk["target"] if not walk["full"] else None,
                            "walk": dict(walk),
                        },
                    )
                    if stop:
                        return
                return
            except VendorRejected as exc:
                if resume and not restarted and exc.status in (400, 404, 410, 422):
                    # S4: a stored cursor GitHub no longer accepts. Restart the pass.
                    ctx.log.warning(
                        "stored pagination cursor rejected; restarting the listing",
                        status=exc.status,
                    )
                    resume, restarted, walk["cursor"] = None, True, None
                    continue
                if exc.status in (403, 404):
                    raise _classify_403_404(exc, self.name, path) from exc
                raise

    async def _walk_per_repo(
        self, ctx: Context, walk: dict[str, Any], cutoff: str | None
    ) -> AsyncIterator[Page]:
        repo_page_url: str | None = walk.get("repo_page")
        index = int(walk.get("repo_index") or 0)
        async for repos, nxt, _ in _repositories(ctx, repo_page_url):
            for i in range(index, len(repos)):
                repo = repos[i]
                walk["repo_index"] = i
                if repo.get("archived") and ctx.options.get("include_archived", True) is False:
                    continue
                path = f"/repos/{repo['full_name']}/{mapping.FAMILY_PATH[self.family]}"
                try:
                    async for page in self._walk(ctx, path, walk, cutoff, repo=_minimal_repo(repo)):
                        yield page
                except FeatureNotEnabled:
                    ctx.log.info(
                        "feature not enabled for repository",
                        repository=repo["full_name"],
                        stream=self.name,
                    )
                except PermissionMissing:
                    raise
                walk["cursor"] = None
                walk["repo_index"] = i + 1
                yield Page(
                    items=[],
                    checkpoint={
                        "watermark": walk["target"] if not walk["full"] else None,
                        "walk": dict(walk),
                    },
                )
            index = 0
            walk["repo_page"], walk["repo_index"] = nxt, 0
            if nxt is None:
                return

    async def _enrich(self, ctx: Context, items: list[dict[str, Any]]) -> None:
        return None

    async def read_one(self, ctx: Context, key: str) -> RawItem | GoneMarker:
        _family, repo_id, number = key.split(":")
        resp = await ctx.http.request("GET", f"/repositories/{repo_id}", allow=(403, 404))
        if resp.status_code in (403, 404):
            return GoneMarker(key)
        repo = resp.json()
        params = {"hide_secret": "true"} if self.family == "secret_scanning" else None
        alert_resp = await ctx.http.request(
            "GET",
            f"/repos/{repo['full_name']}/{mapping.FAMILY_PATH[self.family]}/{number}",
            params=params,
            allow=(403, 404),
        )
        if alert_resp.status_code in (403, 404):
            return GoneMarker(key)
        alert: RawItem = alert_resp.json()
        alert["repository"] = _minimal_repo(repo)
        await self._enrich(ctx, [alert])
        return alert

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> FindingRecord | Skip:
        return NORMALIZERS[self.family](raw, nctx)


class CodeScanningStream(AlertStream):
    name = "code_scanning_alerts"
    family = "code_scanning"


class SecretScanningStream(AlertStream):
    name = "secret_scanning_alerts"
    family = "secret_scanning"

    async def _enrich(self, ctx: Context, items: list[dict[str, Any]]) -> None:
        if ctx.options.get("secret_locations", "first") != "all":
            return
        if not version_at_least(ctx.config.get("server_version"), LOCATIONS_MIN_GHES):
            return  # the locations endpoint is newer than this GHES release
        for item in items:
            if not item.get("has_more_locations"):
                continue
            repo = item["repository"]["full_name"]
            locations: list[dict[str, Any]] = []
            async for page in link_header_pages(
                ctx.http,
                f"/repos/{repo}/secret-scanning/alerts/{item['number']}/locations",
                params={"per_page": PER_PAGE},
            ):
                locations.extend(page.items)
            item["_locations"] = locations


class DependabotStream(AlertStream):
    name = "dependabot_alerts"
    family = "dependabot"


# ---------------------------------------------------------------- the connector


class GitHubConnector(Connector):
    manifest = MANIFEST
    stream_classes = (
        RepositoriesStream,
        BranchesStream,
        CodeScanningStream,
        SecretScanningStream,
        DependabotStream,
    )

    def base_url(self, config: dict[str, Any], vendor_app: dict[str, Any] | None) -> str:
        api = ((vendor_app or {}).get("config") or {}).get("api_base_url")
        return str(api or "https://api.github.com").rstrip("/")

    def auth_scheme_for(self, purpose: str) -> str:
        return "app" if purpose in ("verify", "installation") else "default"

    def auth_plan(
        self,
        *,
        credentials: dict[str, Any],
        vendor_secrets: dict[str, Any],
        vendor_config: dict[str, Any],
        config: dict[str, Any],
        http: Any,
    ) -> AuthPlan:
        app_id = vendor_config.get("app_id")
        private_key = vendor_secrets.get("private_key")
        if not app_id or not private_key:
            raise ConfigInvalid("the GitHub App registration is missing its app id or private key")
        installation_id = config.get("installation_id")

        async def app_token(_current: CachedToken | None) -> CachedToken:
            token, exp = github_app_jwt(str(app_id), str(private_key))
            return CachedToken(access_token=token, expires_at=datetime.fromtimestamp(exp, UTC))

        async def installation_token(_current: CachedToken | None) -> CachedToken:
            if not installation_id:
                raise ConfigInvalid("the connection has no installation_id yet")
            try:
                resp = await http.request(
                    "POST",
                    f"/app/installations/{installation_id}/access_tokens",
                    auth_scheme="app",
                    capture=False,
                )
            except VendorRejected as exc:
                if exc.status in (401, 403, 404):
                    raise AuthRejected(
                        f"GitHub refused an installation token ({exc.status}): the app may be "
                        "uninstalled or suspended"
                    ) from exc
                raise
            body = resp.json()
            return CachedToken(
                access_token=body["token"],
                expires_at=_parse_ts(body["expires_at"]),
                extra={
                    "permissions": body.get("permissions"),
                    "repository_selection": body.get("repository_selection"),
                },
            )

        return AuthPlan(
            exchanges={"app": app_token, "default": installation_token},
            margins_s={"app": 60, "default": self.manifest.auth.token_refresh_margin_s},
        )

    async def _server_version(self, ctx: Context) -> str | None:
        """GHES reports its release in ``GET /meta`` (``installed_version``); github.com
        and GHE.com do not, and are never version-gated."""
        if ctx.http.base_url.rstrip("/") == "https://api.github.com":
            return None
        resp = await ctx.http.request("GET", "/meta", auth_scheme="app", allow=(404,))
        if resp.status_code != 200:
            return None
        version = (resp.json() or {}).get("installed_version")
        return str(version) if version else None

    async def verify(self, ctx: Context) -> VerifyResult:
        iid = ctx.config.get("installation_id")
        if not iid:
            raise ConfigInvalid("the connection has no installation_id yet")
        resp = await ctx.http.request(
            "GET", f"/app/installations/{iid}", auth_scheme="app", allow=(404,)
        )
        if resp.status_code == 404:
            raise AuthRejected("the GitHub App installation no longer exists (uninstalled)")
        inst = resp.json()
        if inst.get("suspended_at"):
            raise AuthRejected("the GitHub App installation is suspended")
        account = inst.get("account") or {}
        option_mode = ctx.options.get("listing_mode", "auto")
        # Spike S2 fallback: an installation limited to selected repositories lists per
        # repository, so nothing depends on how org-level listings treat the selection.
        listing_mode = (
            option_mode
            if option_mode in ("org", "per_repo")
            else (
                "org"
                if account.get("type") == "Organization"
                and inst.get("repository_selection") != "selected"
                else "per_repo"
            )
        )
        server_version = await self._server_version(ctx)
        return VerifyResult(
            tenant_identity=str(account.get("id")),
            display_name=account.get("login"),
            config_updates={
                **({"server_version": server_version} if server_version else {}),
                "installation_id": int(iid),
                "account_login": account.get("login"),
                "account_id": account.get("id"),
                "account_type": account.get("type"),
                "repository_selection": inst.get("repository_selection"),
                "listing_mode": listing_mode,
                "permissions": inst.get("permissions") or {},
                "events": inst.get("events") or [],
            },
            vendor_tenant_ref=str(iid),
            detail={"app_slug": inst.get("app_slug"), "target_type": inst.get("target_type")},
        )

    async def probe(self, ctx: Context, stream: str) -> Grant:
        perms: dict[str, str] = ctx.config.get("permissions") or {}
        needed = mapping.STREAM_PERMISSION[stream]
        if stream in ("repositories", "branches"):
            endpoint = "GET /installation/repositories"
            await ctx.http.request("GET", "/installation/repositories", params={"per_page": 1})
            return Grant(GrantStatus.GRANTED, endpoint)
        family = mapping.STREAM_FAMILY[stream]
        listing = listing_mode_for(ctx.options, ctx.config, family)
        org = ctx.config.get("account_login")
        endpoint = (
            f"GET /orgs/{{org}}/{mapping.FAMILY_PATH[family]}"
            if listing == "org"
            else f"GET /repos/{{owner}}/{{repo}}/{mapping.FAMILY_PATH[family]}"
        )
        if perms.get(needed) not in ("read", "write"):
            return Grant(
                GrantStatus.UNAUTHORIZED,
                endpoint,
                f"the GitHub App was not granted '{needed}' access",
            )
        if listing != "org":
            return Grant(
                GrantStatus.GRANTED,
                endpoint,
                "per-repository listing; enablement is checked per repository",
            )
        params: dict[str, Any] = {"per_page": 1}
        if family == "secret_scanning":
            params["hide_secret"] = "true"  # noqa: S105
        try:
            await ctx.http.request(
                "GET", f"/orgs/{org}/{mapping.FAMILY_PATH[family]}", params=params
            )
        except VendorRejected as exc:
            if exc.status in (403, 404):
                classified = _classify_403_404(exc, stream, f"org {org}")
                if isinstance(classified, FeatureNotEnabled):
                    return Grant(GrantStatus.NOT_ENABLED, endpoint, "feature_not_enabled")
                if isinstance(classified, PermissionMissing):
                    return Grant(GrantStatus.UNAUTHORIZED, endpoint, "permission_missing")
            raise
        return Grant(GrantStatus.GRANTED, endpoint)

    def handle_webhook(
        self, delivery: IngressDelivery, *, config: dict[str, Any], options: dict[str, Any]
    ) -> list[WebhookEffect]:
        p, event, action = delivery.payload, delivery.event, delivery.action
        repo = p.get("repository") or {}
        alert = p.get("alert") or {}
        if event in ("code_scanning_alert", "secret_scanning_alert", "dependabot_alert"):
            family = event.removesuffix("_alert")
            if not repo.get("id") or alert.get("number") is None:
                return [Ignore("payload without repository or alert number")]
            return [
                MarkDirty(
                    mapping.FAMILY_STREAM[family],
                    f"{family}:{repo['id']}:{alert['number']}",
                    reason=f"{event}.{action}",
                )
            ]
        if event == "secret_scanning_alert_location":
            if options.get("secret_locations", "first") != "all":
                return [Ignore("secret_locations=first")]
            return [
                MarkDirty(
                    "secret_scanning_alerts",
                    f"secret_scanning:{repo['id']}:{alert['number']}",
                    reason="secret_scanning_alert_location.created",
                )
            ]
        if event == "repository":
            if action == "deleted":
                return [
                    TriggerStream("repositories", reason="repository.deleted"),
                    TriggerStream("branches", reason="repository.deleted"),
                ]
            return [
                TriggerStream("repositories", reason=f"repository.{action}"),
                TriggerStream("branches", reason=f"repository.{action}"),
            ]
        if event == "security_and_analysis":
            return (
                [
                    MarkDirty("repositories", f"repo:{repo['id']}", reason="security_and_analysis"),
                    ReprobeGrants("security_and_analysis changed"),
                ]
                if repo.get("id")
                else [ReprobeGrants("security_and_analysis")]
            )
        if event == "installation_repositories":
            effects: list[WebhookEffect] = [
                TriggerStream("repositories", reason=f"installation_repositories.{action}"),
                TriggerStream("branches", reason=f"installation_repositories.{action}"),
            ]
            if action == "added":
                # Alerts on newly visible repositories are older than the watermark: full passes.
                effects += [
                    TriggerStream(s, reason="repositories added", full=True)
                    for s in mapping.FAMILY_STREAM.values()
                ]
            return effects
        if event == "installation":
            if action == "deleted":
                return [ConnectionRevoked("the GitHub App was uninstalled")]
            if action == "suspend":
                return [
                    ConnectionRevoked("the GitHub App installation was suspended", suspended=True)
                ]
            if action == "unsuspend":
                return [ConnectionRestored("the GitHub App installation was unsuspended")]
            if action == "new_permissions_accepted":
                return [ReprobeGrants("new permissions accepted")]
            return [Ignore(f"installation.{action}")]
        if event == "installation_target" and action == "renamed":
            login = (p.get("account") or {}).get("login")
            return (
                [UpdateConfig({"account_login": login})]
                if login
                else [Ignore("rename without login")]
            )
        return [Ignore(f"unhandled event {event}")]

    async def perform(self, ctx: Context, action: Action) -> ActionResult:
        if action.name != "finding.set_state":
            raise ConfigInvalid(f"unknown action {action.name}")
        natural_key: str = action.record["natural_key"]
        family, repo_id, number = natural_key.split(":")
        state = action.params["state"]
        reason = action.params.get("reason") if state != "OPEN" else None
        body = dict(mapping.WRITE_BACK[family].get((state, reason)) or {})
        if not body:
            raise ConfigInvalid(f"GitHub {family} cannot express {state} with reason {reason}")
        comment = action.params.get("comment")
        truncated = False
        if comment and state != "OPEN":
            if len(comment) > mapping.COMMENT_MAX:
                comment, truncated = comment[: mapping.COMMENT_MAX], True
            body[mapping.COMMENT_FIELD[family]] = comment
        repo = (await ctx.http.request("GET", f"/repositories/{repo_id}")).json()
        resp = await ctx.http.request(
            "PATCH",
            f"/repos/{repo['full_name']}/{mapping.FAMILY_PATH[family]}/{number}",
            json_body=body,
        )
        result = resp.json()
        result.pop("secret", None)
        return ActionResult(
            status="SUCCEEDED",
            vendor_response={
                "state": result.get("state"),
                "number": result.get("number"),
                "comment_truncated": truncated,
            },
            refetch=[MarkDirty(mapping.FAMILY_STREAM[family], natural_key, reason="write-back")],
            message="comment truncated to 280 characters" if truncated else None,
        )

    def sweep_confirmed(
        self, stream: str, *, would_delete: int, live: int, vendor_total: int | None
    ) -> bool:
        # The installation's repository list really did shrink: confirmed by its own count.
        # An empty listing never confirms (the classic failure mode); that needs an operator.
        if stream in ("repositories", "branches") and vendor_total:
            return live - would_delete == vendor_total
        return False
