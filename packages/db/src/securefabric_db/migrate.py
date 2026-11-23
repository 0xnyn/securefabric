"""Tiny forward-only SQL migration runner.

Applies ``*.sql`` files from a directory in lexical order, each in its own
transaction, recording what ran in ``public.schema_migrations`` together with a
checksum so edits to already-applied files are detected.

Usage::

    securefabric-migrate            # apply pending migrations
    securefabric-migrate --status   # show applied / pending
    securefabric-migrate --dir path/to/migrations
"""

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from securefabric_db.settings import DatabaseSettings

DEFAULT_MIGRATIONS_DIR = "db/migrations"
# Arbitrary constant: serialises concurrent runners (e.g. several replicas booting).
_ADVISORY_LOCK_ID = 727_401_001

_BOOTSTRAP_SQL = """
create table if not exists public.schema_migrations (
    version     text primary key,
    checksum    text not null,
    applied_at  timestamptz not null default now()
)
"""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    checksum: str

    @classmethod
    def from_path(cls, path: Path) -> "Migration":
        return cls(
            version=path.stem,
            path=path,
            checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
        )


class MigrationError(RuntimeError):
    pass


def discover(directory: Path) -> list[Migration]:
    if not directory.is_dir():
        raise MigrationError(f"migrations directory not found: {directory}")
    return [Migration.from_path(p) for p in sorted(directory.glob("*.sql"))]


def _applied(conn: psycopg.Connection) -> dict[str, str]:
    rows = conn.execute("select version, checksum from public.schema_migrations").fetchall()
    return {str(version): str(checksum) for version, checksum in rows}


def pending(conn: psycopg.Connection, migrations: list[Migration]) -> list[Migration]:
    applied = _applied(conn)
    out: list[Migration] = []
    for m in migrations:
        recorded = applied.get(m.version)
        if recorded is None:
            out.append(m)
        elif recorded != m.checksum:
            raise MigrationError(
                f"checksum mismatch for already-applied migration {m.version!r}; "
                "never edit an applied migration, add a new one instead"
            )
    return out


def migrate(url: str, directory: Path, *, log: bool = True) -> list[str]:
    """Apply pending migrations. Returns the versions applied."""
    migrations = discover(directory)
    applied_now: list[str] = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(_BOOTSTRAP_SQL)
        conn.execute("select pg_advisory_lock(%s)", (_ADVISORY_LOCK_ID,))
        try:
            for m in pending(conn, migrations):
                if log:
                    print(f"  applying {m.version} ...", flush=True)
                with conn.transaction():
                    # Migration files are trusted, repo-controlled SQL.
                    conn.execute(m.path.read_text(encoding="utf-8"))
                    conn.execute(
                        "insert into public.schema_migrations (version, checksum) values (%s, %s)",
                        (m.version, m.checksum),
                    )
                applied_now.append(m.version)
        finally:
            conn.execute("select pg_advisory_unlock(%s)", (_ADVISORY_LOCK_ID,))
    return applied_now


def status(url: str, directory: Path) -> list[tuple[str, bool]]:
    migrations = discover(directory)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(_BOOTSTRAP_SQL)
        todo = {m.version for m in pending(conn, migrations)}
    return [(m.version, m.version not in todo) for m in migrations]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="securefabric-migrate", description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(os.environ.get("MIGRATIONS_DIR", DEFAULT_MIGRATIONS_DIR)),
        help="directory containing *.sql migrations (env: MIGRATIONS_DIR)",
    )
    parser.add_argument("--url", default=None, help="database URL (env: DATABASE_URL)")
    parser.add_argument("--status", action="store_true", help="show status and exit")
    args = parser.parse_args(argv)

    url = args.url or DatabaseSettings().url
    try:
        if args.status:
            for version, done in status(url, args.dir):
                print(f"  [{'x' if done else ' '}] {version}")
            return 0
        applied = migrate(url, args.dir)
    except (MigrationError, psycopg.Error) as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1

    print(f"applied {len(applied)} migration(s)" if applied else "database is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
