"""An in-process GitHub for tests: the endpoints the connector uses, with payloads
modelled on docs.github.com response schemas (REST API 2022-11-28).

Mutable, so conformance can remove records, empty listings and inject failures.
Pagination follows GitHub's ``Link`` header with an opaque ``after`` cursor.
"""

import base64
import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from securefabric_cdk.inprocess import VendorRequest, VendorResponse

API = "https://api.github.com"
EPOCH = datetime(2026, 3, 1, tzinfo=UTC)


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _cursor(n: int) -> str:
    return base64.urlsafe_b64encode(f"c:{n}".encode()).decode().rstrip("=")


def _uncursor(c: str) -> int:
    return int(base64.urlsafe_b64decode(c + "=" * (-len(c) % 4)).decode().split(":")[1])


class FakeGitHub:
    def __init__(
        self,
        *,
        org: str = "acme-sec",
        installation_id: int | None = None,
        page_size: int = 4,
        account_type: str = "Organization",
        server_version: str | None = None,
        repository_selection: str = "all",
    ) -> None:
        import random

        # GHES: serve under /api/v3, report the release in /meta, and 404 the endpoints
        # that release does not have (minimums from github/rest-api-description).
        self.server_version = server_version
        self.repository_selection = repository_selection

        self.org = org
        # Unique per instance: a shared App fans deliveries out to every tenant on an installation.
        self.installation_id = installation_id or random.randint(10_000, 10**9)  # noqa: S311
        self.page_size = page_size
        self.account = {
            "login": org,
            "id": 9001,
            "type": account_type,
            "node_id": "O_x",
            "html_url": f"https://github.com/{org}",
        }
        self.permissions = {
            "metadata": "read",
            "administration": "read",
            "security_events": "read",
            "secret_scanning_alerts": "read",
            "vulnerability_alerts": "read",
        }
        self.repos: list[dict[str, Any]] = []
        self.alerts: dict[str, list[dict[str, Any]]] = {
            "code-scanning": [],
            "secret-scanning": [],
            "dependabot": [],
        }
        self.disabled: set[str] = set()  # families switched off org-wide
        self.empty: set[str] = set()  # listings that return nothing
        self.requests: list[str] = []
        self.patches: list[dict[str, Any]] = []
        self.tokens_minted = 0
        self.user_installations: list[int] = [self.installation_id]
        self.now = EPOCH
        self._seed()

    # ------------------------------------------------------------ data

    def _repo(
        self,
        i: int,
        name: str,
        *,
        archived: bool = False,
        private: bool = False,
        fork: bool = False,
        default_branch: str | None = "main",
    ) -> dict[str, Any]:
        rid = 700_000 + i
        return {
            "id": rid,
            "node_id": f"R_{rid}",
            "name": name,
            "full_name": f"{self.org}/{name}",
            "private": private,
            "owner": {"login": self.org, "id": 9001, "type": "Organization"},
            "html_url": f"https://github.com/{self.org}/{name}",
            "description": f"{name} repository",
            "fork": fork,
            "url": f"{API}/repos/{self.org}/{name}",
            "clone_url": f"https://github.com/{self.org}/{name}.git",
            "default_branch": default_branch,
            "visibility": "private" if private else "public",
            "archived": archived,
            "disabled": False,
            "language": ["Python", "JavaScript", "Go", "Java"][i % 4],
            "topics": [f"team-{i % 2}"],
            "pushed_at": iso(EPOCH - timedelta(days=i)),
            "created_at": iso(EPOCH - timedelta(days=300 + i)),
            "updated_at": iso(EPOCH - timedelta(days=i)),
            "security_and_analysis": {
                "advanced_security": {"status": "enabled" if not private else "disabled"},
                "secret_scanning": {"status": "enabled"},
                "secret_scanning_push_protection": {"status": "disabled"},
                "dependabot_security_updates": {"status": "enabled"},
            },
        }

    def _seed(self) -> None:
        names = ["api-server", "web-app", "payments", "infra", "legacy-archive", "empty-repo"]
        for i, repo_name in enumerate(names):
            self.repos.append(
                self._repo(
                    i,
                    repo_name,
                    archived=repo_name == "legacy-archive",
                    fork=repo_name == "infra",
                    default_branch=None if repo_name == "empty-repo" else "main",
                )
            )
        states = [
            ("open", None),
            ("fixed", None),
            ("dismissed", "false positive"),
            ("open", None),
            ("dismissed", "won't fix"),
        ]
        for n in range(1, 11):
            repo = self.repos[n % 5]
            state, reason = states[n % len(states)]
            created = EPOCH - timedelta(days=60 - n)
            self.alerts["code-scanning"].append(
                {
                    "number": n,
                    "created_at": iso(created),
                    "updated_at": iso(created + timedelta(hours=n)),
                    "url": f"{API}/repos/{repo['full_name']}/code-scanning/alerts/{n}",
                    "html_url": f"https://github.com/{repo['full_name']}/security/code-scanning/{n}",
                    "state": state,
                    "fixed_at": iso(created + timedelta(days=1)) if state == "fixed" else None,
                    "dismissed_by": {"login": "octocat", "id": 1} if state == "dismissed" else None,
                    "dismissed_at": iso(created + timedelta(days=2))
                    if state == "dismissed"
                    else None,
                    "dismissed_reason": reason,
                    "dismissed_comment": "triaged" if reason else None,
                    "rule": {
                        "id": f"py/sql-injection-{n % 3}",
                        "severity": ["error", "warning", "note"][n % 3],
                        "description": "Database query built from user-controlled sources"
                        if n % 4
                        else "",
                        "name": f"py/sql-injection-{n % 3}",
                        "tags": ["security", "external/cwe/cwe-089"],
                        "security_severity_level": ["critical", "high", "medium", None][n % 4],
                    },
                    "tool": {
                        "name": "CodeQL" if n % 3 else "Semgrep",
                        "guid": None,
                        "version": "2.20.1",
                    },
                    "most_recent_instance": {
                        "ref": "refs/heads/main",
                        "analysis_key": ".github/workflows/codeql.yml:analyze",
                        "environment": "{}",
                        "category": "/language:python",
                        "state": state,
                        "commit_sha": f"{n:040x}",
                        "message": {"text": f"This query depends on a user-provided value ({n})."},
                        "location": {
                            "path": f"src/db_{n}.py",
                            "start_line": 10 + n,
                            "end_line": 10 + n,
                            "start_column": 5,
                            "end_column": 40,
                        },
                        "classifications": [],
                    },
                    "instances_url": f"{API}/repos/{repo['full_name']}/code-scanning/alerts/{n}/instances",
                    "repository": self._minimal(repo),
                }
            )
        resolutions = [None, "revoked", "false_positive", None, "used_in_tests", "wont_fix"]
        for n in range(1, 9):
            repo = self.repos[n % 4]
            res = resolutions[n % len(resolutions)]
            created = EPOCH - timedelta(days=40 - n)
            self.alerts["secret-scanning"].append(
                {
                    "number": n,
                    "created_at": iso(created),
                    "updated_at": iso(created + timedelta(hours=n)),
                    "url": f"{API}/repos/{repo['full_name']}/secret-scanning/alerts/{n}",
                    "html_url": f"https://github.com/{repo['full_name']}/security/secret-scanning/{n}",
                    "locations_url": f"{API}/repos/{repo['full_name']}/secret-scanning/alerts/{n}/locations",
                    "state": "resolved" if res else "open",
                    "resolution": res,
                    "resolved_at": iso(created + timedelta(days=1)) if res else None,
                    "resolved_by": {"login": "octocat", "id": 1} if res else None,
                    "resolution_comment": None,
                    "secret_type": "github_personal_access_token"
                    if n % 2
                    else "slack_incoming_webhook_url",
                    "secret_type_display_name": "GitHub Personal Access Token"
                    if n % 2
                    else "Slack Incoming Webhook URL",
                    "validity": ["active", "inactive", "unknown"][n % 3],
                    "publicly_leaked": n % 3 == 0,
                    "multi_repo": False,
                    "is_base64_encoded": False,
                    "has_more_locations": n % 2 == 0,
                    "push_protection_bypassed": n == 4,
                    "push_protection_bypassed_by": {"login": "dev", "id": 2} if n == 4 else None,
                    "push_protection_bypassed_at": iso(created) if n == 4 else None,
                    "first_location_detected": {
                        "path": f"config/settings_{n}.py",
                        "start_line": 3,
                        "end_line": 3,
                        "start_column": 10,
                        "end_column": 50,
                        "blob_sha": "af5626b4",
                        "blob_url": f"{API}/repos/{repo['full_name']}/git/blobs/af5626b4",
                        "commit_sha": "f14d7debf9775f957cf4f1e8176da0786431f72b",
                        "commit_url": f"{API}/repos/{repo['full_name']}/git/commits/f14d7deb",
                    },
                    "repository": self._minimal(repo),
                }
            )
        dstates = ["open", "fixed", "dismissed", "auto_dismissed", "open", "open"]
        for n in range(1, 13):
            repo = self.repos[n % 4]
            st = dstates[n % len(dstates)]
            created = EPOCH - timedelta(days=90 - n)
            patched = None if n % 5 == 0 else {"identifier": f"4.17.{20 + n}"}
            cve = f"CVE-2021-{23300 + n}" if n % 4 else None
            self.alerts["dependabot"].append(
                {
                    "number": n,
                    "state": st,
                    "dependency": {
                        "package": {
                            "ecosystem": ["npm", "pip", "maven", "go"][n % 4],
                            "name": f"lib-{n}",
                        },
                        "manifest_path": [
                            "package-lock.json",
                            "requirements.txt",
                            "pom.xml",
                            "go.mod",
                        ][n % 4],
                        "scope": "runtime" if n % 2 else "development",
                        "relationship": "direct",
                    },
                    "security_advisory": {
                        "ghsa_id": f"GHSA-{n:04d}-abcd-efgh",
                        "cve_id": cve,
                        "summary": f"Prototype pollution in lib-{n}",
                        "description": f"Versions of lib-{n} are vulnerable.",
                        "severity": ["critical", "high", "medium", "low"][n % 4],
                        "identifiers": [{"value": f"GHSA-{n:04d}-abcd-efgh", "type": "GHSA"}]
                        + ([{"value": cve, "type": "CVE"}] if cve else []),
                        "references": [
                            {"url": f"https://nvd.nist.gov/vuln/detail/{cve or 'none'}"}
                        ],
                        "published_at": iso(created - timedelta(days=10)),
                        "updated_at": iso(created),
                        "withdrawn_at": None,
                        "vulnerabilities": [],
                        "cvss_severities": {
                            "cvss_v3": {
                                "vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                                "score": 9.8,
                            },
                            "cvss_v4": {"vector_string": None, "score": 0.0},
                        },
                        "epss": {"percentage": 0.00045, "percentile": "0.12"},
                        "cwes": [{"cwe_id": "CWE-1321", "name": "Prototype Pollution"}],
                    },
                    "security_vulnerability": {
                        "package": {
                            "ecosystem": ["npm", "pip", "maven", "go"][n % 4],
                            "name": f"lib-{n}",
                        },
                        "severity": ["critical", "high", "medium", "low"][n % 4],
                        "vulnerable_version_range": "< 4.17.21",
                        "first_patched_version": patched,
                    },
                    "url": f"{API}/repos/{repo['full_name']}/dependabot/alerts/{n}",
                    "html_url": f"https://github.com/{repo['full_name']}/security/dependabot/{n}",
                    "created_at": iso(created),
                    "updated_at": iso(created + timedelta(hours=n)),
                    "dismissed_at": iso(created + timedelta(days=1)) if st == "dismissed" else None,
                    "dismissed_by": {"login": "octocat", "id": 1} if st == "dismissed" else None,
                    "dismissed_reason": "tolerable_risk" if st == "dismissed" else None,
                    "dismissed_comment": None,
                    "fixed_at": iso(created + timedelta(days=2)) if st == "fixed" else None,
                    # Spike S9: verdicts as GitHub's schema defines them, incl. "no verdict".
                    **(
                        {}
                        if n % 6 == 0
                        else {
                            "reachability": {
                                "verdict": [
                                    "reachable",
                                    "unreachable",
                                    "potentially_reachable",
                                    "unavailable",
                                    "disabled",
                                ][n % 5]
                            }
                        }
                    ),
                    "auto_dismissed_at": iso(created + timedelta(days=3))
                    if st == "auto_dismissed"
                    else None,
                    "repository": self._minimal(repo),
                }
            )

    def _minimal(self, repo: dict[str, Any]) -> dict[str, Any]:
        keep = (
            "id",
            "node_id",
            "name",
            "full_name",
            "private",
            "owner",
            "html_url",
            "description",
            "fork",
            "url",
        )
        return {k: repo[k] for k in keep}

    # ------------------------------------------------------------ mutation

    def touch(self, family: str, number: int, **changes: Any) -> dict[str, Any]:
        self.now += timedelta(minutes=1)
        a = next(x for x in self.alerts[family] if x["number"] == number)
        a.update(changes)
        a["updated_at"] = iso(self.now)
        return a

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy({"repos": self.repos, "alerts": self.alerts})

    def restore(self, snap: dict[str, Any]) -> None:
        self.repos, self.alerts = copy.deepcopy(snap["repos"]), copy.deepcopy(snap["alerts"])
        self.empty.clear()
        self.disabled.clear()

    # ------------------------------------------------------------ HTTP

    def _page(
        self,
        items: list[Any],
        req: VendorRequest,
        *,
        base_path: str,
        wrap: str | None = None,
        total: int | None = None,
    ) -> VendorResponse:
        per_page = min(int(req.query.get("per_page", 30)), self.page_size)
        start = _uncursor(req.query["after"]) if "after" in req.query else 0
        chunk = items[start : start + per_page]
        headers = {
            "x-ratelimit-limit": "5000",
            "x-ratelimit-remaining": "4990",
            "x-ratelimit-reset": str(int((self.now + timedelta(hours=1)).timestamp())),
        }
        if start + per_page < len(items):
            q = {k: v for k, v in req.query.items() if k != "after"}
            q["after"] = _cursor(start + per_page)
            qs = "&".join(f"{k}={v}" for k, v in q.items())
            headers["link"] = f'<{API}{base_path}?{qs}>; rel="next"'
        body: Any = (
            {"total_count": total if total is not None else len(items), wrap: chunk}
            if wrap
            else chunk
        )
        return VendorResponse(200, body, headers)

    def _auth(self, req: VendorRequest) -> str | None:
        auth = req.headers.get("authorization", "")
        return auth.split(" ", 1)[1] if " " in auth else None

    def _missing_on_server(self, path: str) -> bool:
        if self.server_version is None:
            return False
        have = tuple(int(x) for x in self.server_version.split(".")[:2])
        rules = [
            ("/orgs/", "/dependabot/alerts", (3, 8)),
            ("/repos/", "/dependabot/alerts", (3, 8)),
            ("/orgs/", "/code-scanning/alerts", (3, 5)),
            ("/orgs/", "/secret-scanning/alerts", (3, 3)),
            ("/repos/", "/locations", (3, 3)),
        ]
        return any(path.startswith(p) and part in path and have < v for p, part, v in rules)

    def __call__(self, req: VendorRequest) -> VendorResponse:
        path = req.path
        if self.server_version is not None:
            path = path.removeprefix("/api/v3")
        self.requests.append(f"{req.method} {path}")
        if path == "/meta":
            meta: dict[str, Any] = {"verifiable_password_authentication": False}
            if self.server_version:
                meta["installed_version"] = f"{self.server_version}.0"
            return VendorResponse(200, meta)
        if self._missing_on_server(path):
            return VendorResponse(404, {"message": "Not Found"})
        token = self._auth(req)
        if (
            path == f"/app/installations/{self.installation_id}/access_tokens"
            and req.method == "POST"
        ):
            if not token or not token.startswith("eyJ"):
                return VendorResponse(401, {"message": "A JSON web token could not be decoded"})
            self.tokens_minted += 1
            return VendorResponse(
                201,
                {
                    "token": f"ghs_fake{self.tokens_minted:032d}",
                    "expires_at": iso(datetime.now(UTC) + timedelta(hours=1)),
                    "permissions": self.permissions,
                    "repository_selection": self.repository_selection,
                },
            )
        if path == f"/app/installations/{self.installation_id}":
            if not token or not token.startswith("eyJ"):
                return VendorResponse(401, {"message": "bad jwt"})
            return VendorResponse(
                200,
                {
                    "id": self.installation_id,
                    "account": self.account,
                    "repository_selection": self.repository_selection,
                    "permissions": self.permissions,
                    "events": ["dependabot_alert"],
                    "suspended_at": None,
                    "app_slug": "securefabric",
                    "target_type": self.account["type"],
                },
            )
        if not token or not token.startswith("ghs_"):
            return VendorResponse(401, {"message": "Bad credentials"})
        if path == "/installation/repositories":
            repos = [] if "repositories" in self.empty else self.repos
            return self._page(repos, req, base_path=path, wrap="repositories")
        if path.startswith("/repositories/"):
            rid = int(path.split("/")[2])
            repo = next((r for r in self.repos if r["id"] == rid), None)
            return (
                VendorResponse(200, repo) if repo else VendorResponse(404, {"message": "Not Found"})
            )
        if path.startswith(f"/orgs/{self.org}/"):
            family = path.split("/")[3]
            if family in self.disabled:
                return VendorResponse(
                    403, {"message": "Advanced Security must be enabled for this organization."}
                )
            items = [] if family in self.empty else list(self.alerts[family])
            items.sort(
                key=lambda a: a[req.query.get("sort", "created") + "_at"],
                reverse=req.query.get("direction") == "desc",
            )
            if family == "secret-scanning" and req.query.get("hide_secret") != "true":
                items = [
                    {**a, "secret": "ghp_shouldneverbestored000000000000000000"} for a in items
                ]
            return self._page(items, req, base_path=path)
        if path.startswith("/repos/"):
            parts = path.split("/")
            full = f"{parts[2]}/{parts[3]}"
            family = parts[4]
            if family == "branches":
                return self._page(
                    [
                        {"name": "main", "protected": True, "commit": {"sha": "abc"}},
                        {"name": "dev", "protected": False, "commit": {"sha": "def"}},
                    ],
                    req,
                    base_path=path,
                )
            if family in self.disabled:
                return VendorResponse(
                    403, {"message": "Advanced Security must be enabled for this repository."}
                )
            alerts = [a for a in self.alerts[family] if a["repository"]["full_name"] == full]
            if len(parts) == 7 and req.method == "PATCH":
                number = int(parts[6])
                body = json.loads(req.body or b"{}")
                self.patches.append({"family": family, "number": number, **body})
                a = self.touch(
                    family,
                    number,
                    state=body.get("state"),
                    dismissed_reason=body.get("dismissed_reason"),
                    resolution=body.get("resolution"),
                )
                return VendorResponse(200, {k: v for k, v in a.items() if k != "repository"})
            if len(parts) == 7:
                number = int(parts[6])
                found: dict[str, Any] | None = next(
                    (x for x in alerts if x["number"] == number), None
                )
                return (
                    VendorResponse(200, {k: v for k, v in found.items() if k != "repository"})
                    if found
                    else VendorResponse(404, {"message": "Not Found"})
                )
            if len(parts) == 8 and parts[7] == "locations":
                return self._page(
                    [
                        {
                            "type": "commit",
                            "details": {
                                "path": f"extra/{i}.env",
                                "start_line": i,
                                "end_line": i,
                                "blob_url": "https://api.github.com/blob",
                            },
                        }
                        for i in (1, 2)
                    ],
                    req,
                    base_path=path,
                )
            items = [{k: v for k, v in a.items() if k != "repository"} for a in alerts]
            items.sort(
                key=lambda a: a[req.query.get("sort", "created") + "_at"],
                reverse=req.query.get("direction") == "desc",
            )
            return self._page(items, req, base_path=path)
        if path == "/rate_limit":
            return VendorResponse(200, {"resources": {"core": {"limit": 5000, "remaining": 4999}}})
        return VendorResponse(404, {"message": "Not Found", "path": path})


class FakeGitHubWeb:
    """github.com (not the API): the OAuth code exchange and /user/installations."""

    def __init__(self, gh: FakeGitHub, *, valid_code: str = "good-code") -> None:
        self.gh = gh
        self.valid_code = valid_code

    def __call__(self, req: VendorRequest) -> VendorResponse:
        if req.path == "/login/oauth/access_token":
            from urllib.parse import parse_qs

            form = {k: v[0] for k, v in parse_qs(req.body.decode()).items()}
            if form.get("code") != self.valid_code:
                return VendorResponse(200, {"error": "bad_verification_code"})
            return VendorResponse(200, {"access_token": "ghu_usertoken", "token_type": "bearer"})
        if req.path == "/user/installations":
            if req.headers.get("authorization") != "Bearer ghu_usertoken":
                return VendorResponse(401, {"message": "Bad credentials"})
            return VendorResponse(
                200,
                {
                    "total_count": len(self.gh.user_installations),
                    "installations": [
                        {
                            "id": i,
                            "account": self.gh.account,
                            "repository_selection": self.gh.repository_selection,
                        }
                        for i in self.gh.user_installations
                    ],
                },
            )
        return self.gh(req)
