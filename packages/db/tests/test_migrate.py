from pathlib import Path

import psycopg
import pytest

from securefabric_db.migrate import Migration, MigrationError, discover, migrate, status


def test_discover_orders_lexically_and_checksums(tmp_path: Path) -> None:
    (tmp_path / "0002_b.sql").write_text("select 2;")
    (tmp_path / "0001_a.sql").write_text("select 1;")
    (tmp_path / "notes.txt").write_text("ignored")
    found = discover(tmp_path)
    assert [m.version for m in found] == ["0001_a", "0002_b"]
    assert found[0] == Migration.from_path(tmp_path / "0001_a.sql")


def test_discover_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(MigrationError):
        discover(tmp_path / "nope")


@pytest.mark.integration
def test_migrate_is_idempotent_and_detects_edits(database_url: str, tmp_path: Path) -> None:
    table = f"mig_test_{tmp_path.name[-8:]}".replace("-", "_").lower()
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    migration = mig_dir / f"9000_{table}.sql"
    migration.write_text(f"create table {table} (id int);")

    try:
        assert migrate(database_url, mig_dir, log=False) == [f"9000_{table}"]
        assert migrate(database_url, mig_dir, log=False) == []
        assert status(database_url, mig_dir) == [(f"9000_{table}", True)]

        migration.write_text(f"create table {table} (id bigint);")
        with pytest.raises(MigrationError, match="checksum mismatch"):
            migrate(database_url, mig_dir, log=False)
    finally:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(f"drop table if exists {table}")
            conn.execute(
                "delete from public.schema_migrations where version = %s", (f"9000_{table}",)
            )


@pytest.mark.integration
def test_absurd_schema_is_installed(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        row = conn.execute("select absurd.get_schema_version()").fetchone()
    assert row is not None
    assert row[0] == "0.5.1"
