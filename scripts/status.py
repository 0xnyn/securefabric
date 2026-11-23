"""`make status`: what state is this checkout and its stack in, and what to do next.

Sections, top to bottom: toolchain, dependencies, services (Docker, Postgres,
migrations), running processes (API, dash, worker), the workspace and task
queues, generated-code drift, and git. Database facts come from the same
``securefabric_domain.status.collect`` that serves ``GET /v1/status``, so the
terminal and the dash's Status page always agree.

    make status                # the report
    make status ARGS=--json    # machine-readable
    make status ARGS=--fast    # skip the slower drift checks
    make status ARGS=--strict  # exit 1 when anything is down (CI, scripts)
"""

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parent.parent
Level = Literal["ok", "warn", "down", "info"]
_RANK = {"info": 0, "ok": 0, "warn": 1, "down": 2}


@dataclass
class Check:
    name: str
    level: Level
    detail: str
    hint: str | None = None


@dataclass
class Section:
    title: str
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, level: Level, detail: str, hint: str | None = None) -> None:
        self.checks.append(Check(name, level, detail, hint))


def sh(*cmd: str, timeout: float = 20, cwd: Path = ROOT) -> tuple[int, str]:
    """Run a command; (exit code, combined output). Missing binaries give 127."""
    if shutil.which(cmd[0]) is None:
        return 127, f"{cmd[0]}: not found"
    try:
        proc = subprocess.run(  # noqa: S603 (fixed argv, no shell)
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""


def version_of(text: str) -> str:
    match = re.search(r"\d+\.\d+(?:\.\d+)?", text)
    return match.group(0) if match else text


def http_get(url: str, timeout: float = 1.5) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (localhost)
            return resp.status, resp.read(2000).decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(2000).decode(errors="replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        return None, str(getattr(exc, "reason", exc))


def env_value(key: str, default: str) -> str:
    """From the environment, else .env, else the default (no python-dotenv needed)."""
    if key in os.environ:
        return os.environ[key]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                return line.split("=", 1)[1].split("#", 1)[0].strip().strip("'\"")
    return default


# --- Sections ---------------------------------------------------------------------


def toolchain() -> Section:
    s = Section("Toolchain")
    want_py = (ROOT / ".python-version").read_text().strip()
    want_node = (ROOT / ".nvmrc").read_text().strip().lstrip("v")
    pkg = json.loads((ROOT / "package.json").read_text())
    want_pnpm = str(pkg.get("packageManager", "pnpm@?")).split("@", 1)[1]

    checks: list[tuple[str, tuple[str, ...], str | None, str]] = [
        ("uv", ("uv", "--version"), None, "curl -LsSf https://astral.sh/uv/install.sh | sh"),
        ("python", ("uv", "run", "--frozen", "python", "--version"), want_py, "uv python install"),
        ("node", ("node", "--version"), want_node, f"nvm install {want_node}"),
        ("pnpm", ("pnpm", "--version"), want_pnpm, "corepack enable"),
        ("docker", ("docker", "--version"), None, "install Docker Desktop or OrbStack"),
    ]
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(lambda c: sh(*c[1]), checks))
    for (name, _, want, hint), (code, out) in zip(checks, results, strict=True):
        if code != 0:
            s.add(name, "down", "not installed", hint)
            continue
        have = version_of(first_line(out))
        if want and not have.startswith(want.split(".")[0] + ".") and have != want:
            s.add(name, "warn", f"{have} (expected {want})", hint)
        elif want and not have.startswith(want):
            s.add(name, "warn", f"{have} (pinned {want})", hint)
        else:
            s.add(name, "ok", have)
    return s


def dependencies() -> Section:
    s = Section("Dependencies")
    code, out = sh("uv", "lock", "--check")
    s.add(
        "uv.lock",
        "ok" if code == 0 else "warn",
        "in sync with pyproject.toml" if code == 0 else first_line(out),
        None if code == 0 else "make lock",
    )
    venv = ROOT / ".venv"
    if not venv.exists():
        s.add(".venv", "down", "missing", "make install")
    else:
        code, out = sh("uv", "sync", "--frozen", "--all-packages", "--dry-run")
        stale = code != 0 or "Would install" in out or "Would uninstall" in out
        s.add(
            ".venv",
            "warn" if stale else "ok",
            "packages out of date" if stale else "synced",
            "make sync" if stale else None,
        )
    modules = ROOT / "node_modules" / ".modules.yaml"
    lock = ROOT / "pnpm-lock.yaml"
    if not modules.exists():
        s.add("node_modules", "down", "missing", "make install")
    elif modules.stat().st_mtime + 1 < lock.stat().st_mtime:
        s.add("node_modules", "warn", "older than pnpm-lock.yaml", "pnpm install")
    else:
        s.add("node_modules", "ok", "installed")
    hooks = sh("git", "config", "core.hooksPath")[1]
    s.add(
        "git hooks",
        "ok" if hooks.endswith(".husky/_") else "warn",
        "husky installed" if hooks.endswith(".husky/_") else "not installed",
        None if hooks.endswith(".husky/_") else "make hooks",
    )
    return s


def services() -> Section:
    s = Section("Services")
    code, out = sh("docker", "compose", "ps", "--all", "--format", "json", timeout=10)
    if code == 127:
        s.add("docker", "warn", "docker not installed; using an external Postgres?")
        return s
    if code != 0:
        s.add("docker", "down", "daemon not running", "start Docker")
        return s
    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("["):
            rows.extend(json.loads(line))
        elif line.startswith("{"):
            rows.append(json.loads(line))
    if not rows:
        s.add("compose", "info", "no containers", "make db-up (or make stack)")
    for row in rows:
        state = row.get("State", "?")
        health = row.get("Health") or ""
        level: Level = (
            "ok"
            if state == "running" and health in ("", "healthy")
            else "warn"
            if state == "running"
            else "down"
        )
        detail = f"{state}{f' ({health})' if health else ''}"
        ports = row.get("Publishers") or []
        published = sorted({p["PublishedPort"] for p in ports if p.get("PublishedPort")})
        if published:
            detail += f" · :{', :'.join(map(str, published))}"
        s.add(row.get("Service", row.get("Name", "?")), level, detail)
    return s


async def database_facts() -> tuple[dict[str, Any] | None, str | None]:
    """The operator view of ``GET /v1/status``, computed locally, plus workspace counts."""
    try:
        import psycopg

        from securefabric_db import DatabaseSettings, fetch_all
        from securefabric_domain.status import collect
    except ImportError as exc:
        return None, f"Python deps missing ({exc.name}); run make install"
    url = DatabaseSettings().url
    try:
        async with await psycopg.AsyncConnection.connect(
            url, autocommit=True, connect_timeout=3
        ) as conn:
            facts = await collect(conn, version="local", migrations_dir=ROOT / "db" / "migrations")
            # Local only (this runs as the database owner): per-environment counts.
            facts["environments"] = await fetch_all(
                conn,
                """select e.slug,
                          (select count(*) from control.organization o
                            where o.environment_id = e.id and o.deleted_at is null) as organizations,
                          count(c.id) as connections,
                          count(c.id) filter (where c.health_status = 'HEALTHY') as healthy,
                          count(c.id) filter (where c.health_status = 'UNHEALTHY') as attention,
                          count(c.id) filter (where c.health_status = 'INITIALIZING') as initializing
                     from control.environment e
                     left join control.connection c
                       on c.environment_id = e.id and c.deleted_at is null
                    where e.deleted_at is null
                    group by e.id, e.slug order by e.slug""",
            )
            return facts, None
    except psycopg.errors.UndefinedFunction:
        return None, "obs.system_status() is missing: migrations pending"
    except psycopg.OperationalError as exc:
        return None, first_line(str(exc)) or type(exc).__name__


def database(facts: dict[str, Any] | None, error: str | None) -> Section:
    s = Section("Database")
    if facts is None:
        hint = "make db-migrate" if error and "migrations" in error else "make db-up"
        s.add("postgres", "down", error or "unreachable", hint)
        return s
    db = facts["database"]
    s.add(
        "postgres",
        "ok",
        f"{db['server_version']} · {db['database']} · {db['latency_ms']} ms · "
        f"{(db['size_bytes'] or 0) / 1024 / 1024:.0f} MB",
    )
    m = facts["migrations"]
    if m["pending"]:
        s.add(
            "migrations",
            "warn",
            f"{len(m['pending'])} pending: {', '.join(m['pending'])}",
            "make db-migrate",
        )
    else:
        s.add("migrations", "ok", f"{len(m['applied'])} applied, latest {m['applied'][-1]}")
    if m["unknown"]:
        s.add("migrations", "warn", f"applied but not on disk: {', '.join(m['unknown'])}")
    return s


def processes(facts: dict[str, Any] | None) -> Section:
    s = Section("Processes")
    api_port = env_value("API_PORT", "8000")
    dash_port = env_value("DASH_PORT", "3000")
    code, body = http_get(f"http://localhost:{api_port}/health/ready")
    if code is None:
        s.add("api", "down", f"nothing on :{api_port}", "make dev (or make dev-api)")
    else:
        try:
            ready = json.loads(body).get("status")
        except json.JSONDecodeError:
            ready = None
        s.add(
            "api",
            "ok" if code == 200 else "warn",
            f"http://localhost:{api_port} · ready={ready or code}",
            None if code == 200 else "check the API logs",
        )
    code, _ = http_get(f"http://localhost:{dash_port}/", timeout=3)
    s.add(
        "dash",
        "ok" if code is not None and code < 500 else "down",
        f"http://localhost:{dash_port}" if code is not None else f"nothing on :{dash_port}",
        None if code is not None else "make dev (or make dev-dash)",
    )
    if facts is None:
        s.add("worker", "info", "unknown (database unreachable)")
        return s
    workers = facts.get("workers", [])
    online = [w for w in workers if w["online"]]
    if not online:
        stale = f" · {len(workers)} stale heartbeat(s)" if workers else ""
        s.add("worker", "down", f"none online{stale}", "make dev (or make dev-worker)")
        return s
    s.add(
        "worker",
        "ok",
        ", ".join(
            f"{w['role']} ({','.join(w['queues']) or '-'}, x{w['concurrency']})" for w in online
        ),
    )
    roles = {w["role"] for w in online}
    missing = {"scheduler", "sync", "control", "delivery", "maintenance"} - roles
    if missing and "all" not in roles:
        s.add("roles", "warn", f"no worker for: {', '.join(sorted(missing))}", "make dev-worker")
    return s


def workspace(facts: dict[str, Any] | None) -> Section:
    s = Section("Workspace & queues")
    if facts is None:
        s.add("workspace", "info", "unknown (database unreachable)")
        return s
    envs = facts.get("environments") or []
    if not envs:
        s.add("workspace", "info", "no environments yet", "make seed")
    # Connection health is customer data, so it is reported, not counted against the system.
    for env in envs:
        s.add(
            f"  {env['slug']}",
            "info",
            f"{env['organizations']} organizations · {env['connections']} connections "
            f"({env['healthy']} healthy, {env['attention']} need attention, "
            f"{env['initializing']} initializing)",
        )
    runs = facts.get("runs") or {}
    active = ", ".join(f"{n} {state.lower()}" for state, n in sorted(runs.items())) or "none"
    if facts.get("stuck_runs"):
        s.add(
            "syncs",
            "warn",
            f"{facts['stuck_runs']} RUNNING > 15 min · active: {active}",
            "check the sync workers: make dev-worker",
        )
    else:
        s.add("syncs", "ok", f"active: {active} · {facts['failed_runs_last_day']} failed in 24h")
    for severity, n in sorted((facts.get("alert_counts") or {}).items()):
        s.add(
            f"alerts ({severity})",
            "warn" if severity == "page" else "info",
            f"{n} open",
            "GET /v1/admin/alerts (operators); resolve with POST /v1/admin/alerts/{id}/resolve",
        )
    queues = facts.get("queues") or []
    if not queues:
        s.add("queues", "info", "none yet (make db-migrate creates them)")
    for q in queues:
        oldest = q.get("oldest_pending_seconds")
        level: Level = "warn" if (oldest or 0) > 60 else "ok"
        s.add(
            f"queue {q['name']}",
            level,
            f"{q['pending']} pending · {q['running']} running · {q['sleeping']} sleeping · "
            f"{q['completed']} done · {q['failed']} failed"
            + (f" · oldest pending {oldest:.0f}s" if oldest else ""),
        )
    return s


def drift(fast: bool) -> Section:
    s = Section("Generated code")
    if fast:
        s.add("drift", "info", "skipped (--fast)")
        return s
    checks = {
        "client (v1.ts)": (("pnpm", "-s", "-F", "@securefabric/client", "check-generated"),
                           "make generate"),
        "tokens": (("pnpm", "-s", "-F", "@securefabric/tokens", "check-tokens"),
                   "pnpm -F @securefabric/tokens generate"),
    }  # fmt: skip
    with ThreadPoolExecutor() as pool:
        outputs = pool.map(lambda c: sh(*c[0], timeout=60), checks.values())
        results = dict(zip(checks, outputs, strict=True))
    for name, (code, out) in results.items():
        hint = checks[name][1]
        if code == 0:
            s.add(name, "ok", "up to date")
        elif code == 127:
            s.add(name, "warn", "pnpm not found", "make install")
        else:
            s.add(name, "warn", "stale" if out else f"check failed ({code})", hint)
    return s


def git() -> Section:
    s = Section("Git")
    code, branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD")
    if code != 0:
        s.add("repo", "info", "no commits yet" if "HEAD" in branch else "not a git repo")
        return s
    _, porcelain = sh("git", "status", "--porcelain")
    dirty = [line for line in porcelain.splitlines() if line]
    untracked = sum(1 for line in dirty if line.startswith("??"))
    s.add(
        "branch",
        "warn" if branch in ("main", "master") and dirty else "info",
        branch + (" (hooks block commits here)" if branch in ("main", "master") else ""),
    )
    s.add(
        "worktree",
        "info",
        "clean" if not dirty else f"{len(dirty) - untracked} changed · {untracked} untracked",
    )
    code, ab = sh("git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if code == 0:
        behind, ahead = ab.split()
        s.add("upstream", "warn" if int(behind) else "info", f"{ahead} ahead · {behind} behind")
    _, last = sh("git", "log", "-1", "--format=%h %s (%cr)")
    if last:
        s.add("last commit", "info", last)
    return s


# --- Output -----------------------------------------------------------------------

_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
_STYLE = {"ok": "32", "warn": "33", "down": "31", "info": "2"}
_ICON = {"ok": "✔", "warn": "!", "down": "✖", "info": "·"}


def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def render(sections: list[Section], elapsed: float) -> str:
    width = max(len(c.name) for sec in sections for c in sec.checks) + 2
    lines = [paint("SecureFabric status", "1")]
    hints: list[str] = []
    for sec in sections:
        lines.append("")
        lines.append(paint(sec.title, "1;4"))
        for c in sec.checks:
            icon = paint(_ICON[c.level], _STYLE[c.level])
            lines.append(f"  {icon} {c.name.ljust(width)}{c.detail}")
            if c.hint and c.level in ("warn", "down"):
                hints.append(f"{c.name.strip()}: {c.hint}")
    worst = max((c.level for sec in sections for c in sec.checks), key=_RANK.__getitem__)
    lines.append("")
    summary = {
        "ok": "All good.",
        "info": "All good.",
        "warn": "Needs attention.",
        "down": "Something is down.",
    }[worst]
    lines.append(f"{paint(summary, _STYLE[worst] + ';1')} {paint(f'({elapsed:.1f}s)', '2')}")
    if hints:
        lines.append(paint("Next steps:", "1"))
        lines.extend(f"  → {h}" for h in dict.fromkeys(hints))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report the state of the checkout and stack.")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--fast", action="store_true", help="skip generated-code drift checks")
    parser.add_argument("--strict", action="store_true", help="exit 1 if anything is down")
    args = parser.parse_args()

    os.chdir(ROOT)
    started = time.monotonic()
    with ThreadPoolExecutor() as pool:
        f_tools = pool.submit(toolchain)
        f_deps = pool.submit(dependencies)
        f_services = pool.submit(services)
        f_drift = pool.submit(drift, args.fast)
        f_git = pool.submit(git)
        facts, error = asyncio.run(database_facts())
        sections = [
            f_tools.result(),
            f_deps.result(),
            f_services.result(),
            database(facts, error),
            processes(facts),
            workspace(facts),
            f_drift.result(),
            f_git.result(),
        ]
    elapsed = time.monotonic() - started

    if args.json:
        print(json.dumps({"sections": [asdict(s) for s in sections], "system": facts}, indent=2))
    else:
        print(render(sections, elapsed))
    down = any(c.level == "down" for s in sections for c in s.checks)
    return 1 if args.strict and down else 0


if __name__ == "__main__":
    sys.exit(main())
