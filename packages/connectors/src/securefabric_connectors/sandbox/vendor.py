"""The SANDBOX vendor: a deterministic synthetic security API, served in-process.

Given a seed it presents hosts, images, containers and findings with pagination,
rate limits, auth and failures, behind the CDK's in-process transport, so the connector
goes through the real CDK HTTP client and never touches the network.

The vendor deliberately uses its *own* shapes and vocabulary (``risk``,
``status: suppressed``, ``reachable: maybe``) so the connector's mapping is real
work, as it would be for Tenable or Qualys.

State is kept per tenant in a process-wide registry, so a connection's vendor
survives across slices, and tests can mutate it between syncs (``tick``,
``close_finding``, ``delete_host``) or inject failures.
"""

import hashlib
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from securefabric_cdk.inprocess import VendorRequest, VendorResponse
from securefabric_connectors.sandbox.oauth import OAuthServer, access_token_tenant

EPOCH = datetime(2026, 1, 1, tzinfo=UTC)

KINDS = ["host_vuln", "container_vuln", "package", "code", "secret", "iac", "domain", "misc"]
RISKS = ["critical", "high", "medium", "low", "info", "none"]
STATUSES = ["open", "resolved", "suppressed"]
TRISTATE: list[bool | None] = [True, False, None]
REACH = ["yes", "maybe", "no", "unknown", None]
PLATFORMS = ["LINUX", "WINDOWS", "MAC", "UNKNOWN"]
ECOSYSTEMS = ["npm", "pip", "maven", "go", "nuget", "cargo"]


def _iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def tenant_for_key(api_key: str) -> str:
    return "t_" + hashlib.sha256(api_key.encode()).hexdigest()[:12]


@dataclass
class Faults:
    scenario: str = "none"
    fired: dict[str, int] = field(default_factory=dict)
    requests: int = 0

    def once(self, name: str) -> bool:
        if self.fired.get(name):
            return False
        self.fired[name] = 1
        return True


@dataclass
class VendorState:
    tenant_id: str
    seed: int
    hosts: dict[str, dict[str, Any]] = field(default_factory=dict)
    images: dict[str, dict[str, Any]] = field(default_factory=dict)
    findings: dict[str, dict[str, Any]] = field(default_factory=dict)
    now: datetime = EPOCH
    exports: dict[str, dict[str, Any]] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)
    faults: Faults = field(default_factory=Faults)
    _rng: random.Random = field(default_factory=random.Random)
    _next_finding: int = 0

    # ------------------------------------------------------------ generation

    @classmethod
    def generate(
        cls, tenant_id: str, *, seed: int, hosts: int, images: int, findings: int
    ) -> "VendorState":
        st = cls(tenant_id=tenant_id, seed=seed)
        st._rng = random.Random(f"{seed}:{tenant_id}")  # noqa: S311 - synthetic data
        for i in range(hosts):
            st._add_host(i)
        for i in range(images):
            st._add_image(i)
        for _ in range(findings):
            st.add_finding()
        return st

    def _ts(self, offset_s: int) -> datetime:
        return EPOCH + timedelta(seconds=offset_s)

    def _add_host(self, i: int) -> None:
        hid = f"h-{i:05d}"
        platform = PLATFORMS[i % len(PLATFORMS)]
        self.hosts[hid] = {
            "id": hid,
            "hostname": f"host-{i:05d}",
            "fqdn": f"host-{i:05d}.corp.example",
            "ipv4": [f"10.{(i >> 16) & 255}.{(i >> 8) & 255}.{i & 255}"],
            "ipv6": [],
            "mac": [f"02:00:00:{(i >> 16) & 255:02x}:{(i >> 8) & 255:02x}:{i & 255:02x}"],
            "os": {
                "LINUX": "Ubuntu 22.04",
                "WINDOWS": "Windows Server 2022",
                "MAC": "macOS 15",
                "UNKNOWN": None,
            }[platform],
            "platform": platform,
            "agent": {"version": f"7.{i % 10}.0"},
            "cloud": {
                "provider": "aws",
                "account": "123456789012",
                "region": ["us-east-1", "eu-west-1"][i % 2],
                "instance_id": f"i-{i:017x}",
            }
            if i % 3
            else None,
            "labels": {"env": ["prod", "staging", "dev"][i % 3], "team": f"team-{i % 4}"},
            "status": "retired" if i % 17 == 16 else "active",
            "created_at": _iso(self._ts(i)),
            "updated_at": _iso(self._ts(i)),
        }

    def _add_image(self, i: int) -> None:
        iid = f"i-{i:05d}"
        kind = "container" if i % 2 else "image"
        self.images[iid] = {
            "id": iid,
            "kind": kind,
            "name": f"registry.example/app-{i % 5}",
            "tag": f"1.{i}.0",
            "digest": "sha256:" + hashlib.sha256(iid.encode()).hexdigest(),
            "labels": [f"svc=app-{i % 5}"],
            "host_id": f"h-{i % max(1, len(self.hosts)):05d}"
            if kind == "container" and self.hosts
            else None,
            "created_at": _iso(self._ts(i)),
            "updated_at": _iso(self._ts(i)),
        }

    def add_finding(self, **overrides: Any) -> dict[str, Any]:
        n = self._next_finding
        self._next_finding += 1
        fid = f"f-{n:07d}"
        kind = KINDS[n % len(KINDS)]
        risk = RISKS[(n // len(KINDS)) % len(RISKS)]
        status = STATUSES[(n // 3) % len(STATUSES)]
        asset: dict[str, Any] | None
        if kind in ("container_vuln",) and self.images:
            img = list(self.images)[n % len(self.images)]
            asset = {"type": self.images[img]["kind"], "id": img}
        elif self.hosts:
            asset = {"type": "host", "id": list(self.hosts)[n % len(self.hosts)]}
        else:
            asset = None
        cve = f"CVE-20{20 + n % 6}-{1000 + n % 9000}"
        created = self.now - timedelta(days=(n % 400))
        f: dict[str, Any] = {
            "id": fid,
            "kind": kind,
            "title": f"{kind.replace('_', ' ').title()} issue #{n}",
            "summary": f"Synthetic {kind} finding {n} for testing.",
            "risk": risk,
            "status": status,
            "fix_available": TRISTATE[n % 3],
            "exploit_known": TRISTATE[(n // 3) % 3],
            "reachable": REACH[n % len(REACH)],
            "cves": [cve] if kind in ("host_vuln", "container_vuln", "package") else [],
            "cvss": {
                "version": "3.1",
                "score": round(1.0 + (n % 90) / 10, 1),
                "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            }
            if kind != "misc"
            else None,
            "cwe": [f"CWE-{79 + n % 20}"] if kind in ("code", "iac") else [],
            "asset": asset,
            "package": {
                "name": f"lib{n % 50}",
                "ecosystem": ECOSYSTEMS[n % len(ECOSYSTEMS)],
                "installed": f"1.{n % 9}.0",
                "fixed": f"1.{n % 9}.1" if TRISTATE[n % 3] else None,
            }
            if kind in ("package", "container_vuln")
            else None,
            "location": {
                "path": f"src/module_{n % 30}.py",
                "line": 10 + n % 200,
                "url": f"https://code.example/{fid}",
            }
            if kind in ("code", "secret", "iac")
            else None,
            "port": 443 if kind in ("host_vuln", "domain") else None,
            "protocol": "tcp" if kind in ("host_vuln", "domain") else None,
            "domain": f"svc{n % 7}.example.com" if kind == "domain" else None,
            "rule": {
                "id": f"SBX-{kind.upper()}-{n % 40}",
                "name": f"rule-{n % 40}",
                "category": kind,
            },
            "url": f"https://sandbox.securefabric.dev/findings/{fid}",
            "created_at": _iso(created),
            "updated_at": _iso(self.now - timedelta(seconds=1_000_000 - n)),
            "resolved_at": _iso(self.now) if status != "open" else None,
            "removed": False,
            "comment": None,
        }
        f.update(overrides)
        self.findings[fid] = f
        return f

    # ------------------------------------------------------------ mutation (tests, demos)

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)

    def touch(self, fid: str, **changes: Any) -> dict[str, Any]:
        self.advance(1)
        f = self.findings[fid]
        f.update(changes)
        f["updated_at"] = _iso(self.now)
        return f

    def close_finding(self, fid: str) -> dict[str, Any]:
        return self.touch(fid, status="resolved", resolved_at=_iso(self.now + timedelta(seconds=1)))

    def reopen_finding(self, fid: str) -> dict[str, Any]:
        return self.touch(fid, status="open", resolved_at=None)

    def remove_finding(self, fid: str) -> dict[str, Any]:
        """Vendor-reported deletion: the item stays in the feed with ``removed``."""
        return self.touch(fid, removed=True)

    def purge_finding(self, fid: str) -> None:
        """Gone without trace (only a reconcile sweep can notice)."""
        self.findings.pop(fid, None)

    def delete_host(self, hid: str) -> None:
        self.hosts.pop(hid, None)

    def tick(self) -> dict[str, list[str]]:
        """A deterministic batch of vendor changes, as a nightly vendor scan would make."""
        self.advance(3600)
        ids = sorted(self.findings)
        changed: dict[str, list[str]] = {"closed": [], "reopened": [], "new": []}
        for fid in ids[:: max(1, len(ids) // 5 or 1)][:3]:
            f = self.findings[fid]
            if f["status"] == "open":
                self.close_finding(fid)
                changed["closed"].append(fid)
            else:
                self.reopen_finding(fid)
                changed["reopened"].append(fid)
        self.advance(1)
        changed["new"].append(self.add_finding(updated_at=_iso(self.now))["id"])
        return changed


_REGISTRY: dict[tuple[str, int, int, int, int], VendorState] = {}


def vendor_for(api_key: str, options: dict[str, Any]) -> VendorState:
    tenant = tenant_for_key(api_key)
    key = (
        tenant,
        int(options.get("seed", 42)),
        int(options.get("host_count", 25)),
        int(options.get("image_count", 10)),
        int(options.get("finding_count", 120)),
    )
    st = _REGISTRY.get(key)
    if st is None:
        st = VendorState.generate(tenant, seed=key[1], hosts=key[2], images=key[3], findings=key[4])
        _REGISTRY[key] = st
    st.faults.scenario = str(options.get("scenario", "none"))
    return st


def reset_registry() -> None:
    _REGISTRY.clear()


# ---------------------------------------------------------------- the HTTP surface


def _json(status: int, body: Any, headers: dict[str, str] | None = None) -> VendorResponse:
    return VendorResponse(status, body, headers or {})


class SandboxVendor:
    """Routes ``https://sandbox.securefabric.dev/<region>/api/...`` to a VendorState."""

    def __init__(self, options: dict[str, Any], *, page_size: int | None = None) -> None:
        self._options = options
        self._page_size = page_size or int(options.get("page_size", 50))

    def __call__(self, request: VendorRequest) -> VendorResponse:
        path = request.path
        marker = "/api/"
        route = path[path.index(marker) + len(marker) - 1 :] if marker in path else path
        query = request.query
        oauth = OAuthServer(self._options).handle(route, request)
        if oauth is not None:
            return oauth
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer sbxat_"):
            # An OAuth access token (SANDBOX_OAUTH / SANDBOX_CC): the tenant it was issued for.
            tenant = access_token_tenant(auth.removeprefix("Bearer "))
            if tenant is None:
                return _json(401, {"error": "invalid_token"})
            api_key = f"sbx_oauth_{tenant}"
        elif auth.startswith("Bearer sbx_"):
            api_key = auth.removeprefix("Bearer ")
            if api_key.startswith("sbx_revoked"):
                return _json(401, {"error": "revoked"})
        else:
            return _json(401, {"error": "invalid_api_key"})
        st = vendor_for(api_key, self._options)
        st.faults.requests += 1

        injected = self._inject(st, route, request)
        if injected is not None:
            return injected
        limit_headers = {"x-ratelimit-limit": "100000", "x-ratelimit-remaining": "99999"}

        if route == "/v1/me":
            return _json(
                200,
                {
                    "tenant_id": st.tenant_id,
                    "name": f"Sandbox tenant {st.tenant_id[2:8]}",
                    "plan": "enterprise",
                },
                limit_headers,
            )
        if route == "/v1/hosts":
            items = sorted(st.hosts.values(), key=lambda h: h["id"])
            if st.faults.scenario == "empty_listing":
                items = []
            off = int(query.get("offset", 0))
            lim = min(int(query.get("limit", self._page_size)), 1000)
            return _json(200, {"items": items[off : off + lim], "total": len(items)}, limit_headers)
        if route.startswith("/v1/hosts/"):
            h = st.hosts.get(route.rsplit("/", 1)[1])
            return _json(200, h) if h else _json(404, {"error": "not_found"})
        if route == "/v1/images":
            items = sorted(st.images.values(), key=lambda h: h["id"])
            if st.faults.scenario == "empty_listing":
                items = []
            start = int(query.get("pageToken") or 0)
            size = min(int(query.get("pageSize", self._page_size)), 1000)
            nxt = start + size
            return _json(
                200,
                {
                    "items": items[start:nxt],
                    "nextPageToken": str(nxt) if nxt < len(items) else None,
                },
                limit_headers,
            )
        if route == "/v1/findings":
            since = query.get("since")
            items = sorted(st.findings.values(), key=lambda f: (f["updated_at"], f["id"]))
            if since:
                items = [f for f in items if f["updated_at"] > since]
            if st.faults.scenario == "empty_listing":
                items = []
            start = int(query.get("pageToken") or 0)
            size = min(int(query.get("pageSize", self._page_size)), 1000)
            nxt = start + size
            return _json(
                200,
                {
                    "items": items[start:nxt],
                    "nextPageToken": str(nxt) if nxt < len(items) else None,
                    "total": len(items),
                },
                limit_headers,
            )
        if (
            route.startswith("/v1/findings/")
            and route.endswith("/state")
            and request.method == "POST"
        ):
            fid = route.split("/")[3]
            f = st.findings.get(fid)
            if f is None:
                return _json(404, {"error": "not_found"})
            body = request.json() or {}
            st.actions.append({"finding": fid, **body})
            status = body.get("status")
            if status not in ("open", "suppressed", "resolved"):
                return _json(422, {"error": "invalid_status"})
            st.touch(
                fid,
                status=status,
                comment=body.get("comment"),
                resolved_at=None if status == "open" else _iso(st.now),
            )
            return _json(200, st.findings[fid])
        if route.startswith("/v1/findings/"):
            f = st.findings.get(route.rsplit("/", 1)[1])
            if f is None or f.get("removed"):
                return _json(404, {"error": "not_found"})
            return _json(200, f)
        if route == "/v1/exports" and request.method == "POST":
            body = request.json() or {}
            eid = f"exp-{len(st.exports) + 1:04d}"
            items = sorted(st.findings.values(), key=lambda f: f["id"])
            since = body.get("since")
            if since:
                items = [f for f in items if f["updated_at"] > since]
            chunk = int(body.get("chunk_size", 500))
            chunks = [items[i : i + chunk] for i in range(0, len(items), chunk)] or [[]]
            st.exports[eid] = {"id": eid, "polls": 0, "chunks": chunks, "expired": False}
            return _json(202, {"export_id": eid})
        if route.startswith("/v1/exports/"):
            parts = route.split("/")
            exp = st.exports.get(parts[3])
            if exp is None or exp["expired"]:
                return _json(404, {"error": "export_not_found"})
            if len(parts) == 4:
                exp["polls"] += 1
                if exp["polls"] < 2:
                    return _json(200, {"status": "processing", "retry_after": 30})
                if st.faults.scenario == "expire_export" and st.faults.once("expire_export"):
                    exp["expired"] = True
                    return _json(200, {"status": "expired"})
                return _json(200, {"status": "ready", "chunks": list(range(len(exp["chunks"])))})
            idx = int(parts[5])
            return _json(200, {"items": exp["chunks"][idx]})
        return _json(404, {"error": "no_route", "path": route})

    def _inject(self, st: VendorState, route: str, request: VendorRequest) -> VendorResponse | None:
        sc = st.faults.scenario
        listing = route in ("/v1/findings", "/v1/hosts", "/v1/images")
        if sc == "server_errors" and route != "/v1/me":
            return _json(503, {"error": "unavailable"})
        if sc == "forbidden" and route.startswith("/v1/findings"):
            return _json(403, {"error": "forbidden", "message": "missing scope findings:read"})
        if sc == "not_found" and route.startswith("/v1/findings"):
            return _json(404, {"error": "not_found"})
        if sc == "fail_every_3rd_page" and listing and st.faults.requests % 3 == 0:
            return _json(500, {"error": "internal"})
        if (
            sc == "rate_limit_20m"
            and route == "/v1/findings"
            and "pageToken" in request.query
            and st.faults.once("rate_limit_20m")
        ):
            return _json(429, {"error": "rate_limited"}, {"retry-after": "1200"})
        if sc == "rate_limit_short" and listing and st.faults.once("rate_limit_short"):
            return _json(429, {"error": "rate_limited"}, {"retry-after": "2"})
        if sc == "revoke_mid_run" and route != "/v1/me" and st.faults.requests > 3:
            return _json(401, {"error": "revoked"})
        return None
