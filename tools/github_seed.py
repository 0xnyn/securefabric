"""Seed the GitHub test organization (plan part 6; `tools/github-seed`).

Creates what the GitHub connector must see live, idempotently:

- `sf-vuln-node`: package-lock.json with known-vulnerable npm packages (Dependabot alerts)
- `sf-vuln-python`: requirements.txt with known-vulnerable Python packages (Dependabot alerts)
- `sf-code-scanning`: a SARIF upload with findings at several severities (code scanning alerts)
- `sf-secrets`: a file holding a provider-format test credential (secret scanning alerts)
- `sf-archived`: an archived repository; `sf-empty`: a repository with no commits

Each repository gets vulnerability alerts, Dependabot alerts and secret scanning enabled.

    uv run python tools/github_seed.py --check       # preflight only: what the token can do
    uv run python tools/github_seed.py               # seed (re-running changes nothing)

Reads GITHUB_SEED_TOKEN and GITHUB_TEST_ORG. The token's user must be an owner of the org
(fine-grained: org Administration and repository Administration, Contents, Code scanning
alerts, Secret scanning alerts and Dependabot alerts with write access).
"""

import argparse
import base64
import gzip
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx2

API = "https://api.github.com"
H = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

NODE_LOCK = {
    "name": "sf-vuln-node",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {
        "": {"name": "sf-vuln-node", "dependencies": {"lodash": "4.17.15", "minimist": "1.2.0"}},
        "node_modules/lodash": {
            "version": "4.17.15",
            "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.15.tgz",
        },
        "node_modules/minimist": {
            "version": "1.2.0",
            "resolved": "https://registry.npmjs.org/minimist/-/minimist-1.2.0.tgz",
        },
    },
}
PY_REQUIREMENTS = "django==2.2.0\nrequests==2.19.0\npyyaml==5.3\n"
# A Slack incoming-webhook URL in the documented format: secret scanning reports it; it
# points nowhere real. Built at runtime so this file itself holds no secret pattern.
SLACK_TEST = "https://hooks.slack.com/services/" + "/".join(
    ["T00000000", "B00000000", "XXXXXXXXXXXXXXXXXXXXXXXX"]
)


def sarif() -> dict[str, Any]:
    results = [
        ("js/sql-injection", "error", "9.8", "src/db.js", 12),
        ("js/xss", "warning", "6.1", "src/view.js", 40),
        ("js/unused-variable", "note", None, "src/util.js", 3),
    ]
    rules = [
        {
            "id": r,
            "shortDescription": {"text": r},
            "properties": {"security-severity": s} if s else {},
        }
        for r, _, s, _, _ in results
    ]
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {"name": "securefabric-seed", "version": "1.0.0", "rules": rules}
                },
                "results": [
                    {
                        "ruleId": r,
                        "level": lvl,
                        "message": {"text": f"seeded {r}"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": path},
                                    "region": {"startLine": line},
                                }
                            }
                        ],
                    }
                    for r, lvl, _, path, line in results
                ],
            }
        ],
    }


@dataclass
class Repo:
    name: str
    files: dict[str, str] = field(default_factory=dict)
    archived: bool = False
    sarif: bool = False
    # Code scanning and secret scanning are free only on public repositories (private ones
    # need GitHub Code Security); these hold synthetic files only.
    public: bool = False


NODE_PACKAGE = {"name": "sf-vuln-node", "dependencies": {"lodash": "4.17.15", "minimist": "1.2.0"}}
SEEDED_JS = dict.fromkeys(("src/db.js", "src/view.js", "src/util.js"), "// seeded\n")
REPOS = [
    Repo(
        "sf-vuln-node",
        {
            "package-lock.json": json.dumps(NODE_LOCK, indent=2),
            "package.json": json.dumps(NODE_PACKAGE),
        },
    ),
    Repo("sf-vuln-python", {"requirements.txt": PY_REQUIREMENTS}),
    Repo("sf-code-scanning", SEEDED_JS, sarif=True, public=True),
    Repo("sf-secrets", {"config/notify.env": f"SLACK_WEBHOOK={SLACK_TEST}\n"}, public=True),
    Repo("sf-archived", {"README.md": "# archived fixture\n"}, archived=True),
    Repo("sf-empty"),
]


class Seeder:
    def __init__(self, request: Callable[..., httpx2.Response], org: str) -> None:
        self.req = request
        self.org = org
        self.log: list[str] = []

    def preflight(self) -> dict[str, Any]:
        me = self.req("GET", "/user")
        if me.status_code != 200:
            return {"ok": False, "problem": f"token rejected ({me.status_code})"}
        login = me.json()["login"]
        # Probe the one capability seeding needs without creating anything: a blank repo
        # name is refused with 422 when the token may create repositories in the org, and
        # 403/404 when it may not. (Reading the org membership would need the extra
        # "Members" permission, which seeding does not.)
        probe = self.req("POST", f"/orgs/{self.org}/repos", json={"name": ""})
        if probe.status_code == 422:
            return {"ok": True, "user": login, "can_create_repos": True}
        return {
            "ok": False,
            "user": login,
            "problem": f"this token cannot create repositories in {self.org} "
            f"({probe.status_code}). Use a fine-grained token with resource owner {self.org} "
            "(repository permissions: Administration, Contents, Code scanning alerts, "
            "Secret scanning alerts, Dependabot alerts: read and write), or a classic "
            "token with the repo and admin:org scopes.",
        }

    def ensure_repo(self, repo: Repo) -> str:
        r = self.req("GET", f"/repos/{self.org}/{repo.name}")
        if r.status_code == 200:
            existing = r.json()
            if existing.get("archived"):
                return "exists (archived)"
        else:
            c = self.req(
                "POST",
                f"/orgs/{self.org}/repos",
                json={"name": repo.name, "private": True, "auto_init": False},
            )
            if c.status_code not in (201, 422):
                raise RuntimeError(f"create {repo.name}: {c.status_code} {c.text[:200]}")
        for path, text in repo.files.items():
            have = self.req("GET", f"/repos/{self.org}/{repo.name}/contents/{path}")
            if have.status_code == 200:
                continue
            put = self.req(
                "PUT",
                f"/repos/{self.org}/{repo.name}/contents/{path}",
                json={
                    "message": f"seed: {path}",
                    "content": base64.b64encode(text.encode()).decode(),
                },
            )
            if put.status_code not in (200, 201):
                raise RuntimeError(f"put {repo.name}/{path}: {put.status_code} {put.text[:200]}")
        if repo.public:
            current = self.req("GET", f"/repos/{self.org}/{repo.name}")
            if current.status_code == 200 and current.json().get("private", True):
                self.req("PATCH", f"/repos/{self.org}/{repo.name}", json={"visibility": "public"})
        if repo.files:
            self.req("PUT", f"/repos/{self.org}/{repo.name}/vulnerability-alerts")
            self.req(
                "PATCH",
                f"/repos/{self.org}/{repo.name}",
                json={
                    "security_and_analysis": {
                        "secret_scanning": {"status": "enabled"},
                        "dependabot_security_updates": {"status": "disabled"},
                    }
                },
            )
        if repo.sarif:
            head = self.req("GET", f"/repos/{self.org}/{repo.name}/commits/HEAD")
            if head.status_code == 200:
                payload = base64.b64encode(gzip.compress(json.dumps(sarif()).encode())).decode()
                up = self.req(
                    "POST",
                    f"/repos/{self.org}/{repo.name}/code-scanning/sarifs",
                    json={
                        "commit_sha": head.json()["sha"],
                        "ref": "refs/heads/main",
                        "sarif": payload,
                    },
                )
                if up.status_code not in (200, 201, 202):
                    raise RuntimeError(
                        f"SARIF upload to {repo.name}: {up.status_code} {up.text[:200]}"
                    )
        if repo.archived:
            self.req("PATCH", f"/repos/{self.org}/{repo.name}", json={"archived": True})
        return "ready"

    def run(self) -> dict[str, Any]:
        pre = self.preflight()
        if not pre["ok"]:
            return {"preflight": pre}
        return {"preflight": pre, "repos": {r.name: self.ensure_repo(r) for r in REPOS}}


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed the GitHub test organization")
    ap.add_argument("--check", action="store_true", help="preflight only")
    args = ap.parse_args()
    token, org = os.environ.get("GITHUB_SEED_TOKEN"), os.environ.get("GITHUB_TEST_ORG")
    if not token or not org:
        sys.exit("set GITHUB_SEED_TOKEN and GITHUB_TEST_ORG")
    with httpx2.Client(
        base_url=API, headers={**H, "Authorization": f"Bearer {token}"}, timeout=30
    ) as c:
        seeder = Seeder(lambda m, p, **kw: c.request(m, p, **kw), org)
        out = {"preflight": seeder.preflight()} if args.check else seeder.run()
    print(json.dumps(out, indent=2))
    return 0 if out["preflight"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
