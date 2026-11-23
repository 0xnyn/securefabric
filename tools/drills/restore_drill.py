"""Backup restore drill (NFR-08; docs/runbooks/restore_drill.md).

Dumps the database (`pg_dump -Fc` inside the compose Postgres), restores it into a
fresh scratch database, proves the restore is usable, then drops the scratch copy:

1. every migration is applied with a matching checksum (the runner refuses otherwise),
2. row counts of the core tables equal the source,
3. row-level security is still enabled with its policies,
4. a sealed credential opens with the vault (the wrapped keys came back intact).

The source database is only read. Usage:

    uv run python tools/drills/restore_drill.py            # dev database
"""

import asyncio
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
TABLES = (
    "control.account",
    "control.environment",
    "control.organization",
    "control.connection",
    "control.credential",
    "data.resource",
    "data.vulnerability_finding",
    "events.outbox_event",
    "obs.audit_event",
)


def compose(*args: str, stdin: bytes | None = None) -> bytes:
    out = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["docker", "compose", "exec", "-T", "postgres", *args],  # noqa: S607
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        check=True,
    )
    return out.stdout


async def counts(url: str) -> dict[str, int]:
    out: dict[str, int] = {}
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as c:
        for t in TABLES:
            try:
                cur = await c.execute(f"select count(*) from {t}")  # noqa: S608 - fixed names
                row = await cur.fetchone()
                out[t] = int(row[0]) if row else 0
            except psycopg.errors.UndefinedTable:
                continue
    return out


async def main() -> int:
    from securefabric_db import DatabaseSettings
    from securefabric_db.migrate import status

    source_url = DatabaseSettings().url
    info = psycopg.conninfo.conninfo_to_dict(source_url)
    source_db = str(info.get("dbname"))
    scratch = f"restore_drill_{uuid.uuid4().hex[:8]}"
    scratch_url = psycopg.conninfo.make_conninfo(source_url, dbname=scratch)
    report: dict[str, object] = {"source": source_db, "scratch": scratch}

    t0 = time.perf_counter()
    dump = compose("pg_dump", "-U", str(info.get("user")), "-Fc", source_db)
    report["dump_mb"] = round(len(dump) / 1e6, 2)
    report["dump_s"] = round(time.perf_counter() - t0, 2)
    before = await counts(source_url)
    admin_url = psycopg.conninfo.make_conninfo(source_url, dbname="postgres")
    async with await psycopg.AsyncConnection.connect(admin_url, autocommit=True) as c:
        await c.execute(f'create database "{scratch}"')
    try:
        t0 = time.perf_counter()
        compose(
            "pg_restore", "-U", str(info.get("user")), "-d", scratch, "--no-owner",
            "--exit-on-error", stdin=dump,
        )  # fmt: skip
        report["restore_s"] = round(time.perf_counter() - t0, 2)

        # 1. Migrations: all applied, checksums match the files on disk.
        st = status(scratch_url, ROOT / "db" / "migrations")
        report["migrations_pending"] = [m for m, applied in st if not applied]
        # 2. Row counts.
        after = await counts(scratch_url)
        report["counts_match"] = after == before
        report["rows"] = sum(after.values())
        # 3. RLS still on, policies present.
        async with await psycopg.AsyncConnection.connect(scratch_url, autocommit=True) as c:
            cur = await c.execute(
                "select count(*) filter (where c.relrowsecurity), "
                "(select count(*) from pg_policies where schemaname in "
                "('control','sync','data','events','obs')) "
                "from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                "where n.nspname in ('control','sync','data','events','obs') and c.relkind in ('r','p')"
            )
            row = await cur.fetchone()
            report["rls_tables"], report["policies"] = row or (0, 0)
        # 4. The vault opens a sealed credential from the restored copy.
        report["credential_opened"] = await open_one_credential(scratch_url)
    finally:
        async with await psycopg.AsyncConnection.connect(admin_url, autocommit=True) as c:
            await c.execute(f'drop database if exists "{scratch}" with (force)')
    ok = (
        not report["migrations_pending"]
        and report["counts_match"]
        and int(str(report["policies"])) > 0
        and report["credential_opened"] is not False
    )
    report["ok"] = ok
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


async def open_one_credential(url: str) -> bool | None:
    """True if a sealed credential opens, None if the database holds none."""
    from securefabric_db import DatabaseSettings
    from securefabric_domain.runtime import build_platform
    from securefabric_domain.sync.credentials import open_credentials

    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as c:
        cur = await c.execute(
            "select environment_id, connection_id from control.credential "
            "where sealed is not null limit 1"
        )
        row = await cur.fetchone()
    if row is None:
        return None
    platform = build_platform("control", db=DatabaseSettings(url=url))
    await platform.open()
    try:
        creds = await open_credentials(platform, row[0], row[1])
        return bool(creds)
    finally:
        await platform.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
