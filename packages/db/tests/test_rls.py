"""Row-level security fails closed (M0 exit criterion, SEC-05).

Seeds rows as the owner (which bypasses RLS), then reads every RLS-protected
table as ``sf_api``: with no tenant setting every table returns zero rows, with
the other tenant's setting it returns zero rows, and with the right setting the
seeded rows are visible.
"""

import uuid

import psycopg
import pytest

pytestmark = pytest.mark.integration

TENANT_SCHEMAS = ("control", "sync", "data", "events", "obs")
# Tables with an environment_id that are deliberately not tenant-scoped.
# api_rate_counter: internal limiter counters, synced across environments in one
# statement and never returned by any endpoint.
NOT_TENANT_SCOPED: set[str] = {"obs.api_rate_counter"}


def _rls_tables(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute(
        """
        select n.nspname || '.' || c.relname
          from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = any(%s) and c.relkind in ('r', 'p') and c.relrowsecurity
           and not c.relispartition
         order by 1
        """,
        (list(TENANT_SCHEMAS),),
    ).fetchall()
    return [r[0] for r in rows]


def _seed(conn: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
    account = conn.execute(
        "insert into control.account (name, slug) values ('A', %s) returning id",
        (f"a-{uuid.uuid4().hex[:8]}",),
    ).fetchone()[0]  # type: ignore[index]
    envs = []
    for slug in ("dev", "prod"):
        envs.append(
            conn.execute(
                "insert into control.environment (account_id, slug, name, vault_public_key,"
                " vault_private_key_wrapped) values (%s, %s, %s, '\\x00', '\\x01') returning id",
                (account, slug, slug),
            ).fetchone()[0]  # type: ignore[index]
        )
    env = envs[0]
    org = conn.execute(
        "insert into control.organization (environment_id, identifier, name)"
        " values (%s, 'acme', 'Acme') returning id",
        (env,),
    ).fetchone()[0]  # type: ignore[index]
    integ = conn.execute(
        "insert into control.integration (environment_id, connector_id, key, display_name,"
        " enabled_streams) values (%s, 'SANDBOX', 'sandbox', 'Sandbox', '{}') returning id",
        (env,),
    ).fetchone()[0]  # type: ignore[index]
    connection = conn.execute(
        "insert into control.connection (environment_id, organization_id, integration_id,"
        " connector_id, connector_version) values (%s, %s, %s, 'SANDBOX', '1.0.0') returning id",
        (env, org, integ),
    ).fetchone()[0]  # type: ignore[index]
    conn.execute(
        "insert into data.resource (id, environment_id, organization_id, connection_id, stream,"
        " natural_key, type, state, first_seen_at, last_seen_at, created_at, updated_at)"
        " values (gen_random_uuid(), %s, %s, %s, 'hosts', 'h1', 'HOST', 'ACTIVE', now(), now(),"
        " now(), now())",
        (env, org, connection),
    )
    conn.execute(
        "insert into obs.operation (environment_id, kind, action, status) values (%s, 'sync',"
        " 'x', 'success')",
        (env,),
    )
    conn.execute(
        "insert into events.outbox_event (environment_id, type, payload) values (%s, 'x', '{}')",
        (env,),
    )
    return env, envs[1]


def test_every_tenant_table_has_rls(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        rows = conn.execute(
            """
            select n.nspname || '.' || c.relname, c.relrowsecurity
              from pg_class c
              join pg_namespace n on n.oid = c.relnamespace
              join pg_attribute a on a.attrelid = c.oid and a.attname = 'environment_id'
             where n.nspname = any(%s) and c.relkind in ('r', 'p') and not c.relispartition
            """,
            (list(TENANT_SCHEMAS),),
        ).fetchall()
    missing = [name for name, rls in rows if not rls and name not in NOT_TENANT_SCOPED]
    assert not missing, f"tenant tables without RLS: {missing}"


def test_no_tenant_setting_reads_zero_rows(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        env, other_env = _seed(conn)
        tables = _rls_tables(conn)
        assert len(tables) >= 30

        conn.execute("set role sf_api")
        for table in tables:
            with conn.transaction():
                # Platform-owned vendor apps (environment_id null) are shared with every
                # tenant by design (PD-10); only tenant-owned rows must stay invisible.
                extra = " where environment_id is not null" if table == "control.vendor_app" else ""
                count = conn.execute(f"select count(*) from {table}{extra}").fetchone()[0]  # type: ignore[index]  # noqa: S608
                assert count == 0, f"{table} leaked {count} rows with no tenant setting"
            with conn.transaction():
                conn.execute("select set_config('app.environment_id', %s, true)", (str(other_env),))
                if table == "control.environment":
                    continue  # the other environment can see itself
                count = conn.execute(
                    f"select count(*) from {table} where environment_id = %s",  # noqa: S608
                    (env,),
                ).fetchone()[0]  # type: ignore[index]
                assert count == 0, f"{table} leaked rows across environments"

        with conn.transaction():
            conn.execute("select set_config('app.environment_id', %s, true)", (str(env),))
            for table in (
                "control.organization",
                "control.connection",
                "data.resource",
                "obs.operation",
                "events.outbox_event",
            ):
                n = conn.execute(f"select count(*) from {table}").fetchone()[0]  # type: ignore[index]  # noqa: S608
                assert n >= 1, table
        conn.execute("reset role")


def test_rls_rejects_writes_into_another_tenant(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        env, other_env = _seed(conn)
        conn.execute("set role sf_api")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("select set_config('app.environment_id', %s, true)", (str(other_env),))
            conn.execute(
                "insert into control.organization (environment_id, identifier, name)"
                " values (%s, 'x', 'x')",
                (env,),
            )
        conn.execute("reset role")


def test_api_role_cannot_read_wrapped_private_keys(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        env, _ = _seed(conn)
        conn.execute("set role sf_api")
        with conn.transaction():
            conn.execute("select set_config('app.environment_id', %s, true)", (str(env),))
            assert conn.execute("select vault_public_key from control.environment").fetchone()
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("select set_config('app.environment_id', %s, true)", (str(env),))
            conn.execute("select vault_private_key_wrapped from control.environment")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("select private_key_wrapped from control.platform_key")
        conn.execute("reset role")
        conn.execute("set role sf_worker")
        with conn.transaction():
            conn.execute("select set_config('app.environment_id', %s, true)", (str(env),))
            assert conn.execute(
                "select vault_private_key_wrapped from control.environment"
            ).fetchone()
        conn.execute("reset role")


def test_audit_log_is_append_only(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("set role sf_worker")
        conn.execute("insert into obs.audit_event (actor_kind, action) values ('system', 'test')")
        for stmt in ("update obs.audit_event set action = 'x'", "delete from obs.audit_event"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute(stmt)
        conn.execute("reset role")
