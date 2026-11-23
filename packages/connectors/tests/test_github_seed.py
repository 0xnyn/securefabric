"""tools/github_seed.py: preflight explains what is missing; seeding is idempotent."""

import sys
from pathlib import Path
from typing import Any

import httpx2

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from github_seed import REPOS, Seeder


class FakeOrg:
    """Just enough of GitHub's REST API for the seeder, recording every write."""

    def __init__(self, *, member: bool = True) -> None:
        self.member = member
        self.repos: dict[str, dict[str, Any]] = {}
        self.files: set[tuple[str, str]] = set()
        self.writes: list[str] = []

    def __call__(self, method: str, path: str, **kw: Any) -> httpx2.Response:
        def resp(status: int, body: Any = None) -> httpx2.Response:
            return httpx2.Response(status, json=body if body is not None else {})

        if method != "GET":
            self.writes.append(f"{method} {path}")
        if path == "/user":
            return resp(200, {"login": "seeder"})
        if method == "POST" and path == "/orgs/acme/repos" and not kw["json"]["name"]:
            # GitHub's answer to a blank name: 422 if the token may create repos, else 403
            self.writes.pop()
            return resp(422) if self.member else resp(403)
        if method == "POST" and path == "/orgs/acme/repos":
            self.repos[kw["json"]["name"]] = {"archived": False}
            return resp(201)
        parts = path.split("/")
        name = parts[3] if len(parts) > 3 else ""
        if path == f"/repos/acme/{name}":
            if method == "GET":
                return resp(200, self.repos[name]) if name in self.repos else resp(404)
            if kw.get("json", {}).get("archived"):
                self.repos[name]["archived"] = True
            return resp(200)
        if "/contents/" in path:
            key = (name, path.split("/contents/", 1)[1])
            if method == "GET":
                return resp(200) if key in self.files else resp(404)
            self.files.add(key)
            return resp(201)
        if path.endswith("/commits/HEAD"):
            has_commit = any(f[0] == name for f in self.files)
            return resp(200, {"sha": "abc123"}) if has_commit else resp(409)
        return resp(201)


def test_preflight_names_what_is_missing() -> None:
    out = Seeder(FakeOrg(member=False), "acme").run()
    assert out["preflight"]["ok"] is False
    assert "cannot create repositories in acme" in out["preflight"]["problem"]
    assert "repos" not in out  # nothing is written without the access


def test_seeding_is_idempotent_and_complete() -> None:
    org = FakeOrg()
    first = Seeder(org, "acme").run()
    assert first["preflight"]["ok"]
    assert set(first["repos"]) == {r.name for r in REPOS} == set(org.repos)
    assert org.repos["sf-archived"]["archived"] is True
    assert ("sf-vuln-node", "package-lock.json") in org.files
    assert any(w.endswith("/code-scanning/sarifs") for w in org.writes)
    assert "PUT /repos/acme/sf-vuln-python/vulnerability-alerts" in org.writes
    creates = [w for w in org.writes if w == "POST /orgs/acme/repos"]
    contents = [w for w in org.writes if "/contents/" in w]
    assert len(creates) == len(REPOS)
    assert len(contents) == sum(len(r.files) for r in REPOS)
    org.writes.clear()
    Seeder(org, "acme").run()  # a second run creates no repositories and no files
    assert not [w for w in org.writes if w == "POST /orgs/acme/repos" or "/contents/" in w]
