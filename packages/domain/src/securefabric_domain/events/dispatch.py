"""Outbox dispatch (docs/plan/07-public-api-and-events.md, section 9).

Reads undispatched events in id order, creates one ``webhook_delivery`` per
subscribed, enabled endpoint, spawns a delivery task for each, and marks the
event dispatched, all in one transaction. A crash before commit dispatches the
event again on the next tick; the unique (event, endpoint) makes that a no-op.
"""

from securefabric_db import fetch_all, system_tx
from securefabric_domain.runtime import Platform
from securefabric_tasks.spec import spawn_sql

BATCH = 500


async def dispatch_outbox(platform: Platform) -> int:
    async with system_tx(platform.sys_pool) as conn:
        events = await fetch_all(
            conn,
            """select id, environment_id, type, created_at from events.outbox_event
                where dispatched_at is null order by id limit %s for update skip locked""",
            (BATCH,),
        )
        for ev in events:
            endpoints = await fetch_all(
                conn,
                """select id from events.webhook_endpoint
                    where environment_id = %s and enabled and deleted_at is null
                      and (cardinality(event_types) = 0 or %s = any(event_types))""",
                (ev["environment_id"], ev["type"]),
            )
            for ep in endpoints:
                rows = await fetch_all(
                    conn,
                    """insert into events.webhook_delivery (environment_id, event_id, endpoint_id, event_type,
                      next_attempt_at)
                       values (%s, %s, %s, %s, now()) on conflict (event_id, endpoint_id) do nothing returning id""",
                    (ev["environment_id"], ev["id"], ep["id"], ev["type"]),
                )
                for r in rows:
                    await spawn_sql(
                        conn,
                        queue="delivery",
                        task_name="webhook.deliver",
                        params={
                            "delivery_id": str(r["id"]),
                            "environment_id": str(ev["environment_id"]),
                        },
                        idempotency_key=f"delivery:{r['id']}",
                        max_attempts=3,
                    )
            await conn.execute(
                "update events.outbox_event set dispatched_at = now() where created_at = %s and id = %s",
                (ev["created_at"], ev["id"]),
            )
    return len(events)
