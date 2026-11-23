"""Maintenance (docs/plan/09-operations-security-quality.md, section 3; STORE-12, OPS-02).

One ``maintenance`` queue; each job is idempotent and audited. The scheduler
spawns them on their cadence (``SCHEDULE``), one task per job per window.

=====================  ==============================================  ===========
job                    does                                            every
=====================  ==============================================  ===========
partitions             create range partitions a week/2 months ahead   1 h
retention              drop old partitions, delete expired rows        1 h
purge                  hard-delete connections past purge_after        1 h
abandoned              PENDING for 7 days → DELETED                    1 h
token_refresh          refresh credentials untouched for 24 h          1 h
alerts                 freshness, outbox lag, connector failure rate   1 min
github_redelivery      redeliver failed GitHub App deliveries          15 min
usage_rollup           obs.usage_daily from events and counts          1 h
payload_reencrypt      seal plaintext / old-key vendor payloads        10 min
=====================  ==============================================  ===========
"""

import json
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx2

from securefabric_core import get_logger
from securefabric_db import Conn, fetch_all, fetch_one, system_tx, tenant_tx
from securefabric_domain.runtime import Platform
from securefabric_domain.sync.scheduler import raise_alert
from securefabric_domain.tenancy import SYSTEM, audit

log = get_logger(__name__)

SCHEDULE: dict[str, int] = {
    "partitions": 3600,
    "retention": 3600,
    "purge": 3600,
    "abandoned": 3600,
    "token_refresh": 3600,
    "alerts": 60,
    "github_redelivery": 900,
    "usage_rollup": 3600,
    "enrichment": 86400,
    "nvd_incremental": 7200,
    "payload_reencrypt": 600,
}

DAILY = ("sync.raw_page", "obs.operation", "obs.operation_event")
MONTHLY = (
    "control.connection_health_event",
    "data.state_history",
    "events.outbox_event",
    "obs.audit_event",
    "obs.usage_event",
)
PARTITION_RETENTION_DAYS = {
    "sync.raw_page": 7,
    "obs.operation": 30,
    "obs.operation_event": 30,
    "control.connection_health_event": 400,
    "data.state_history": 400,
    "events.outbox_event": 90,
    "obs.audit_event": 366,
    "obs.usage_event": 400,
}
ROW_RETENTION = [
    ("sync.job", "created_at", "90 days", "status not in ('QUEUED', 'RUNNING')"),
    ("data.quarantine", "created_at", "30 days", "true"),
    ("control.idempotency_key", "created_at", "24 hours", "true"),
    ("control.oauth_state", "created_at", "2 days", "true"),
    (
        "control.connect_session",
        "created_at",
        "2 days",
        "used_at is not null or expires_at < now()",
    ),
    ("sync.ingress_delivery", "received_at", "7 days", "true"),
    ("events.webhook_attempt", "at", "30 days", "true"),
    ("events.webhook_delivery", "created_at", "90 days", "status <> 'PENDING'"),
    ("obs.api_rate_counter", "window_start", "1 day", "true"),
    ("obs.alert", "raised_at", "90 days", "resolved_at is not null"),
]
SOFT_DELETED_RETENTION = "90 days"


async def run_job(platform: Platform, job: str, args: dict[str, Any]) -> dict[str, Any]:
    fn = JOBS.get(job)
    if fn is None:
        return {"ok": False, "detail": {"error": f"unknown job {job}"}}
    detail = await fn(platform, **args)
    log.info(
        "maintenance_done",
        job=job,
        **{k: v for k, v in detail.items() if isinstance(v, (int, str))},
    )
    return {"ok": True, "detail": detail}


async def partitions(platform: Platform) -> dict[str, Any]:
    today = platform.clock.now().date()
    created = 0
    async with system_tx(platform.sys_pool) as conn:
        for t in DAILY:
            created += await _val(
                conn,
                "select public.sf_ensure_partitions(%s::regclass, 'day', %s, %s)",
                (t, today - timedelta(days=1), today + timedelta(days=8)),
            )
        for t in MONTHLY:
            created += await _val(
                conn,
                "select public.sf_ensure_partitions(%s::regclass, 'month', %s, %s)",
                (t, today.replace(day=1), today + timedelta(days=62)),
            )
        # Rows in a default partition mean the manager fell behind: alert.
        behind = []
        for t in (*DAILY, *MONTHLY):
            n = await _val(conn, f"select count(*) from {t}_default")  # noqa: S608
            if n:
                behind.append(t)
        if behind:
            await raise_alert(
                conn, "partition_manager_behind", ",".join(behind), {"tables": behind}
            )
    return {"created": created, "behind": len(behind)}


async def retention(platform: Platform) -> dict[str, Any]:
    today = platform.clock.now().date()
    dropped = deleted = 0
    async with system_tx(platform.sys_pool) as conn:
        for t, days in PARTITION_RETENTION_DAYS.items():
            dropped += await _val(
                conn,
                "select public.sf_drop_partitions_before(%s::regclass, %s)",
                (t, today - timedelta(days=days)),
            )
        for table, col, keep, extra in ROW_RETENTION:
            cur = await conn.execute(
                f"delete from {table} where {col} < now() - interval '{keep}' and ({extra})"  # noqa: S608 - fixed identifiers
            )
            deleted += cur.rowcount
        for table in ("data.vulnerability_finding", "data.resource"):
            cur = await conn.execute(
                f"delete from {table} where deleted_at < now() - interval '{SOFT_DELETED_RETENTION}'"  # noqa: S608 - fixed identifiers
            )
            deleted += cur.rowcount
        await audit(
            conn,
            SYSTEM,
            "maintenance.retention",
            detail={"dropped_partitions": dropped, "deleted_rows": deleted},
        )
    return {"dropped_partitions": dropped, "deleted_rows": deleted}


async def purge(platform: Platform) -> dict[str, Any]:
    """Hard-delete a connection's data on day 30 (CON-04) and mark it HARD_DELETED."""
    now = platform.clock.now()
    async with system_tx(platform.sys_pool) as conn:
        due = await fetch_all(
            conn,
            "select id, environment_id from control.connection where state = 'DELETED' "
            "and purge_after <= %s",
            (now,),
        )
    for c in due:
        async with system_tx(platform.sys_pool) as conn:
            for table in (
                "data.finding_resource",
                "data.vulnerability_finding",
                "data.resource",
                "data.stream_head",
                "data.object_clock",
                "sync.checkpoint",
                "data.quarantine",
                "sync.dirty_record",
                "control.connection_grant",
            ):
                await conn.execute(f"delete from {table} where connection_id = %s", (c["id"],))  # noqa: S608
            await conn.execute(
                "update control.connection set state = 'HARD_DELETED', updated_at = now() where id = %s",
                (c["id"],),
            )
            await audit(
                conn,
                SYSTEM,
                "connection.purged",
                target_kind="connection",
                target_id=c["id"],
                environment_id=c["environment_id"],
            )
        await platform.blob.delete_prefix(f"{c['environment_id']}/{c['id']}/")
    return {"purged": len(due)}


async def abandoned(platform: Platform) -> dict[str, Any]:
    """A connection left PENDING for 7 days is deleted (part 3, section 6)."""
    from securefabric_domain.connections import _delete

    async with system_tx(platform.sys_pool) as conn:
        rows = await fetch_all(
            conn,
            "select * from control.connection where state = 'PENDING' and created_at < %s",
            (platform.clock.now() - timedelta(days=7),),
        )
        for row in rows:
            await _delete(platform, conn, row)
    return {"deleted": len(rows)}


async def token_refresh(platform: Platform) -> dict[str, Any]:
    """Refresh tokens untouched for 24 hours, so a broken credential is found before
    the next sync (AUTH-05 point 4). Only exchange-based auth has anything to refresh."""
    from securefabric_domain.sync.bundle import build_context, load_bundle
    from securefabric_domain.sync.oplog import start_operation

    async with system_tx(platform.sys_pool) as conn:
        stale = await fetch_all(
            conn,
            """select c.id, c.environment_id from control.credential cr join control.connection c on c.id =
              cr.connection_id
                where c.state = 'ACTIVE' and cr.auth_mode in ('APP', 'OAUTH2', 'OAUTH2_CC') and not
                  cr.refresh_exhausted
                  and coalesce(cr.last_refresh_at, cr.updated_at) < now() - interval '24 hours'""",
        )
    ok = failed = 0
    for row in stale:
        try:
            async with tenant_tx(platform.pool, row["environment_id"]) as conn:
                bundle = await load_bundle(platform, conn, row["id"])
            op = await start_operation(
                platform.pool,
                environment_id=row["environment_id"],
                kind="auth",
                action="refresh",
                connection_id=row["id"],
            )
            ctx = await build_context(
                platform,
                bundle,
                stream=None,
                op_log=op,
                capture=None,
                clock=platform.clock,
                interactive=False,
            )
            auth = ctx.http._auth
            if auth is not None:
                await auth.material("default", force_refresh=True)
            await ctx.http.aclose()
            ok += 1
        except Exception as exc:
            failed += 1
            log.warning(
                "token_refresh_failed", connection_id=str(row["id"]), error=type(exc).__name__
            )
    if failed and failed >= max(3, ok):
        async with system_tx(platform.sys_pool) as conn:
            await raise_alert(conn, "refresh_failures", None, {"failed": failed, "ok": ok})
    return {"refreshed": ok, "failed": failed}


async def _resolve_cleared(conn: Conn, name: str, still_firing: set[str] | None) -> int:
    """Resolve open ``name`` alerts whose condition no longer holds.

    ``still_firing`` holds the subjects currently firing (an empty set resolves all of
    them); a subject-less alert is passed as ``{""}`` when it still fires."""
    rows = await fetch_all(
        conn,
        """update obs.alert set resolved_at = now(),
                  detail = detail || '{"resolution": {"by": "auto", "note": "condition cleared"}}'
            where name = %s and resolved_at is null and not (coalesce(subject, '') = any(%s))
        returning id""",
        (name, sorted(still_firing or set())),
    )
    return len(rows)


async def alerts(platform: Platform) -> dict[str, Any]:
    raised = 0
    resolved = 0
    async with system_tx(platform.sys_pool) as conn:
        # Freshness breach (NFR-02): a healthy connection's stream older than interval + 1 h.
        stale = await fetch_all(
            conn,
            """select s.connection_id, s.stream from sync.stream_schedule s join control.connection c on c.id =
              s.connection_id
                where c.state = 'ACTIVE' and c.health_status = 'HEALTHY' and s.state = 'STARTED'
                  and s.last_success_at < now() - make_interval(secs => s.interval_s + 3600)""",
        )
        for s in stale:
            await raise_alert(
                conn,
                "freshness_breach",
                f"{s['connection_id']}/{s['stream']}",
                {},
                severity="ticket",
            )
            raised += 1
        resolved += await _resolve_cleared(
            conn, "freshness_breach", {f"{s['connection_id']}/{s['stream']}" for s in stale}
        )
        lag = await fetch_one(
            conn,
            "select min(created_at) as oldest from events.outbox_event where dispatched_at is null",
        )
        if lag and lag["oldest"] and lag["oldest"] < platform.clock.now() - timedelta(minutes=2):
            await raise_alert(conn, "outbox_lag", None, {"oldest": lag["oldest"].isoformat()})
            raised += 1
        else:
            await conn.execute(
                "update obs.alert set resolved_at = now() where name = 'outbox_lag' and resolved_at is null"
            )
        adm = await fetch_one(
            conn,
            """select min(not_before) as oldest from sync.stream_run
                                        where state in ('QUEUED', 'PARKED', 'RETRY_WAIT') and not_before <= now()""",
        )
        if adm and adm["oldest"] and adm["oldest"] < platform.clock.now() - timedelta(minutes=5):
            await raise_alert(conn, "admission_lag", None, {"oldest": adm["oldest"].isoformat()})
            raised += 1
        else:
            # Only the queue-lag alert (no subject) clears itself; an expired run ("run <id>")
            # is a one-off event an operator resolves after reading it.
            resolved += len(
                await fetch_all(
                    conn,
                    """update obs.alert set resolved_at = now(),
                              detail = detail || '{"resolution": {"by": "auto", "note": "condition cleared"}}'
                        where name = 'admission_lag' and subject is null and resolved_at is null
                        returning id""",
                )
            )
        # Vendor outage detection (RATE-08): > 20% of a connector's runs failing over 10 min.
        rates = await fetch_all(
            conn,
            """select connector_id, count(*) as n, count(*) filter (where state = 'FAILED' and health_code in
                      ('VENDOR_SERVER_ERROR', 'RATE_LIMIT_EXCEEDED')) as failed
                 from sync.stream_run where finished_at > now() - interval '10 minutes' group by connector_id""",
        )
        for r in rates:
            if r["n"] >= 10 and r["failed"] > 0.2 * r["n"]:
                await raise_alert(
                    conn,
                    "connector_failure_rate",
                    r["connector_id"],
                    {"runs": r["n"], "failed": r["failed"]},
                )
                raised += 1
        failing = {r["connector_id"] for r in rates if r["n"] >= 10 and r["failed"] > 0.2 * r["n"]}
        resolved += await _resolve_cleared(conn, "connector_failure_rate", failing)
    return {"raised": raised, "resolved": resolved}


async def github_redelivery(platform: Platform) -> dict[str, Any]:
    """GitHub does not retry failed deliveries: poll the App's delivery log and ask
    GitHub to redeliver what failed and we never stored (part 6, section 8)."""
    from securefabric_cdk.auth import github_app_jwt
    from securefabric_domain.vault import open_vendor_app_secrets

    redelivered = 0
    async with system_tx(platform.sys_pool) as conn:
        apps = await fetch_all(
            conn,
            "select * from control.vendor_app where connector_id = 'GITHUB' and deleted_at is null",
        )
        secrets = {a["id"]: await open_vendor_app_secrets(platform, conn, a) for a in apps}
    for app in apps:
        cfg, sec = app["config"] or {}, secrets.get(app["id"]) or {}
        if not cfg.get("app_id") or not sec.get("private_key"):
            continue
        jwt, _ = github_app_jwt(cfg["app_id"], sec["private_key"])
        api = (cfg.get("api_base_url") or "https://api.github.com").rstrip("/")
        h = {
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx2.AsyncClient(transport=platform.vendor_transport(), timeout=20) as c:
            r = await c.get(f"{api}/app/hook/deliveries", params={"per_page": 100}, headers=h)
            if r.status_code != 200:
                continue
            failed = [d for d in r.json() if d.get("status") != "OK" and not d.get("redelivery")]
            if not failed:
                continue
            async with platform.sys_pool.connection() as conn:
                seen = {
                    x["delivery_id"]
                    for x in await fetch_all(
                        conn,
                        "select delivery_id from sync.ingress_delivery where vendor_app_id = %s and delivery_id = "
                        "any(%s)",
                        (app["id"], [d["guid"] for d in failed]),
                    )
                }
            for d in failed:
                if d["guid"] in seen:
                    continue
                rr = await c.post(f"{api}/app/hook/deliveries/{d['id']}/attempts", headers=h)
                redelivered += rr.status_code in (200, 202)
    return {"redelivered": redelivered}


async def usage_rollup(platform: Platform, day: str | None = None) -> dict[str, Any]:
    """BILL-01: a daily rollup per environment (sandbox connections never count)."""
    d = date.fromisoformat(day) if day else platform.clock.now().date()
    async with system_tx(platform.sys_pool) as conn:
        await conn.execute(
            """insert into obs.usage_daily (environment_id, day, active_connections, records_stored, api_calls, jobs,
              records_written)
               select e.id, %s,
                      (select count(*) from control.connection c where c.environment_id = e.id and c.state = 'ACTIVE'
                          and not c.is_sandbox and c.connector_id <> 'SANDBOX'),
                      (select coalesce(sum(live_count), 0) from data.stream_head h where h.environment_id = e.id),
                      (select coalesce(sum(quantity), 0) from obs.usage_event u where u.environment_id = e.id and
                          u.kind = 'api.calls'
                          and u.at >= %s and u.at < %s::date + 1),
                      (select count(*) from obs.usage_event u where u.environment_id = e.id and u.kind =
                          'job.finished'
                          and u.at >= %s and u.at < %s::date + 1),
                      (select coalesce(sum(added + updated + deleted), 0) from sync.stream_run r where
                          r.environment_id = e.id
                          and r.finished_at >= %s and r.finished_at < %s::date + 1)
                 from control.environment e where e.deleted_at is null
               on conflict (environment_id, day) do update set active_connections = excluded.active_connections,
                  records_stored = excluded.records_stored, api_calls = excluded.api_calls, jobs = excluded.jobs,
                  records_written = excluded.records_written""",
            (d, d, d, d, d, d, d),
        )
    return {"day": d.isoformat()}


async def _val(conn: Any, q: str, params: Any = None) -> int:
    cur = await conn.execute(q, params)
    row = await cur.fetchone()
    return int(row[0] or 0) if row else 0


async def enrichment(platform: Platform) -> dict[str, Any]:
    from securefabric_domain import enrichment as enr

    return await enr.run_all(platform)


async def nvd_incremental(platform: Platform) -> dict[str, Any]:
    from securefabric_domain import enrichment as enr

    return await enr.nvd_incremental(platform)


PAYLOAD_BATCH = 2000


async def payload_reencrypt(
    platform: Platform, *, budget: int = 20_000, connection_id: str | None = None
) -> dict[str, Any]:
    """STORE-09: seal stored vendor payloads that are plaintext (written before the keys
    were set) or sealed with an older key version (rotation). The record itself does not
    change, so ``updated_at`` and the change feed are untouched.

    Walks each table in primary-key order, so a row that cannot be opened (its key is
    gone) is counted, alerted on and skipped instead of stalling the job. ``connection_id``
    limits it to one connection (an operator re-sealing one tenant)."""
    from securefabric_core.crypto import VaultError
    from securefabric_domain.records import decode_vendor_data, encode_vendor_data, payload_binding

    keyring = platform.payload
    if keyring is None:
        return {"skipped": "PAYLOAD_KEYS not set"}
    stale = """vendor_data is not null
               and (get_byte(vendor_data, 0) = 1
                    or (get_byte(vendor_data, 0) = 2 and get_byte(vendor_data, 1) <> %s))"""
    scope = " and connection_id = %s" if connection_id else ""
    done = unreadable = remaining = 0
    for table, object_type in (
        ("data.vulnerability_finding", "vulnerability_finding"),
        ("data.resource", "resource"),
    ):
        after: tuple[Any, Any] | None = None
        while done < budget:
            async with system_tx(platform.sys_pool) as conn:
                rows = await fetch_all(
                    conn,
                    f"""select connection_id, id, environment_id, vendor_data from {table}
                         where {stale}{scope}
                           and (%s::uuid is null or (connection_id, id) > (%s::uuid, %s::uuid))
                         order by connection_id, id limit %s for update skip locked""",  # noqa: S608
                    (
                        keyring.current,
                        *([connection_id] if connection_id else []),
                        after[0] if after else None,
                        after[0] if after else None,
                        after[1] if after else None,
                        PAYLOAD_BATCH,
                    ),
                )
                if not rows:
                    break
                for r in rows:
                    bound = payload_binding(r["environment_id"], r["connection_id"], object_type)
                    try:
                        payload = decode_vendor_data(
                            r["vendor_data"], cipher=keyring, bound_to=bound
                        )
                    except VaultError:
                        unreadable += 1
                        continue
                    await conn.execute(
                        f"update {table} set vendor_data = %s where connection_id = %s and id = %s",  # noqa: S608
                        (
                            encode_vendor_data(payload, cipher=keyring, bound_to=bound),
                            r["connection_id"],
                            r["id"],
                        ),
                    )
                    done += 1
                after = (rows[-1]["connection_id"], rows[-1]["id"])
        async with system_tx(platform.sys_pool) as conn:
            row = await fetch_one(
                conn,
                f"select count(*) as n from {table} where {stale}{scope}",  # noqa: S608
                (keyring.current, *([connection_id] if connection_id else [])),
            )
            remaining += int((row or {}).get("n") or 0)
    if unreadable:
        async with system_tx(platform.sys_pool) as conn:
            await raise_alert(
                conn,
                "payload_unreadable",
                f"key version {keyring.current}",
                {"rows": unreadable, "loaded_versions": sorted(keyring.versions)},
                severity="ticket",
            )
    if done or unreadable:
        log.info(
            "payloads_reencrypted",
            rows=done,
            unreadable=unreadable,
            remaining=remaining,
            key_version=keyring.current,
        )
    return {
        "reencrypted": done,
        "unreadable": unreadable,
        "remaining": remaining - unreadable,
        "key_version": keyring.current,
    }


JOBS = {
    "payload_reencrypt": payload_reencrypt,
    "enrichment": enrichment,
    "nvd_incremental": nvd_incremental,
    "partitions": partitions,
    "retention": retention,
    "purge": purge,
    "abandoned": abandoned,
    "token_refresh": token_refresh,
    "alerts": alerts,
    "github_redelivery": github_redelivery,
    "usage_rollup": usage_rollup,
}


async def spawn_due(platform: Platform, last: dict[str, datetime]) -> list[str]:
    """Called from the scheduler tick: one task per job per window (idempotency key)."""
    from securefabric_tasks.spec import spawn_sql

    now = platform.clock.now()
    spawned = []
    async with system_tx(platform.sys_pool) as conn:
        for job, every in SCHEDULE.items():
            if job in last and (now - last[job]).total_seconds() < every:
                continue
            window = int(now.timestamp()) // every
            await spawn_sql(
                conn,
                queue="maintenance",
                task_name="maintenance.run",
                params={"job": job, "args": {}},
                idempotency_key=f"maint:{job}:{window}",
                max_attempts=3,
            )
            last[job] = now
            spawned.append(job)
    return spawned


def dumps(v: Any) -> str:
    return json.dumps(v, default=str)


__all__ = ["JOBS", "SCHEDULE", "run_job", "spawn_due"]
_ = UUID
