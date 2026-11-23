"""Repo-wide pytest fixtures.

Integration tests (``@pytest.mark.integration``) need a real Postgres. They use
``TEST_DATABASE_URL`` (default: the ``securefabric_test`` DB on localhost, created
on demand) and are *skipped* when it
is unreachable, so ``make test`` works with no services running. Start Postgres
with ``make db-up`` and run ``make test-integration`` to exercise them.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from securefabric_db.migrate import migrate

REPO_ROOT = Path(__file__).parent
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
DEFAULT_TEST_URL = "postgresql://securefabric:securefabric@localhost:5432/securefabric_test"


_MEMBERS = (
    "apps/api",
    "apps/worker",
    "packages/cdk",
    "packages/connectors",
    "packages/core",
    "packages/db",
    "packages/domain",
    "packages/schema",
    "packages/tasks",
)
_db_suffix = ""


def pytest_configure(config: pytest.Config) -> None:
    """Give each workspace member's run its own database.

    Turbo runs the members' test suites in parallel, and several of them reset the
    control-plane tables or drain the shared Absurd queue. Separate databases
    (``securefabric_test_domain``, ``…_api``) keep them from interfering. A
    whole-repo ``pytest`` run is sequential and uses the base database.
    """
    global _db_suffix
    targets = {
        member
        for arg in config.args
        for member in _MEMBERS
        if Path(arg).resolve().is_relative_to(REPO_ROOT / member)
    }
    if len(targets) == 1:
        _db_suffix = "_" + targets.pop().rsplit("/", 1)[1]


def _test_database_url() -> str:
    # Deliberately NOT falling back to DATABASE_URL: tests must never touch the dev DB.
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    if not _db_suffix:
        return url
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"{parts.path.rstrip('/')}{_db_suffix}"))


def _ensure_database(url: str) -> None:
    """Create the target database if missing (connects to the ``postgres`` maintenance DB)."""
    info = psycopg.conninfo.conninfo_to_dict(url)
    dbname = str(info.get("dbname", ""))
    admin_url = psycopg.conninfo.make_conninfo(url, dbname="postgres")
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as conn:
        exists = conn.execute("select 1 from pg_database where datname = %s", (dbname,)).fetchone()
        if not exists:
            conn.execute(
                psycopg.sql.SQL("create database {}").format(psycopg.sql.Identifier(dbname))
            )


@pytest.fixture(scope="session")
def database_url() -> str:
    url = _test_database_url()
    try:
        _ensure_database(url)
        migrate(url, MIGRATIONS_DIR, log=False)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable for integration tests ({exc.__class__.__name__})")
    return url


@pytest.fixture
def unique_queue() -> Iterator[str]:
    """A throwaway Absurd queue name; dropped after the test."""
    name = f"t_{uuid.uuid4().hex[:12]}"
    yield name
    url = _test_database_url()
    try:
        with psycopg.connect(url, autocommit=True, connect_timeout=3) as conn:
            exists = conn.execute(
                "select 1 from absurd.queues where queue_name = %s", (name,)
            ).fetchone()
            if exists:
                conn.execute("select absurd.drop_queue(%s)", (name,))
    except psycopg.Error:
        pass
