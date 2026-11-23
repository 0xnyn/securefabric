"""Outbound webhook delivery (HOOK-03, HOOK-05, HOOK-07, HOOK-08).

One Absurd task per delivery on the ``delivery`` queue; the retry schedule uses
Absurd's durable sleeps, so a worker restart never loses a pending retry.

- Signing: ``SecureFabric-Timestamp`` and ``SecureFabric-Signature: v1=<hex>``,
  HMAC-SHA256 over ``"{timestamp}.{raw body}"``. For 24 hours after a rotation both
  secrets sign and both signatures are sent. No bare-hash header.
- Retries: 5xx, 408, 429 and network errors at 10 s, 1 m, 5 m, 30 m, 2 h, 6 h,
  12 h, 24 h with jitter, then DEAD. Other 4xx fail permanently. 15 s timeout.
- SSRF guard: HTTPS only, resolved addresses checked before every attempt.
- Auto-disable: an endpoint failing continuously for 5 days is disabled.
"""

import json
import random
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

import httpx2

from securefabric_cdk.errors import EgressDenied
from securefabric_core import get_logger
from securefabric_core.crypto import hmac_sha256_hex
from securefabric_core.telemetry import instruments
from securefabric_db import fetch_one, tenant_tx
from securefabric_domain.runtime import Platform
from securefabric_domain.vault import open_for

log = get_logger(__name__)

RETRY_SCHEDULE_S = (10, 60, 300, 1800, 7200, 21600, 43200, 86400)
TIMEOUT_S = 15.0
AUTO_DISABLE_AFTER = timedelta(days=5)
USER_AGENT = "SecureFabric-Webhooks/1"


def sign(secret: str, timestamp: int, body: bytes) -> str:
    return "v1=" + hmac_sha256_hex(secret, f"{timestamp}.".encode() + body)


def verify_signature(
    secret: str,
    header: str,
    timestamp: str,
    body: bytes,
    *,
    tolerance_s: int = 300,
    now: float | None = None,
) -> bool:
    """What a receiver does (published in the docs, used in tests)."""
    import hmac

    ts = int(timestamp)
    if abs((now or time.time()) - ts) > tolerance_s:
        return False
    expected = sign(secret, ts, body)
    return any(hmac.compare_digest(expected, part.strip()) for part in header.split(","))


@dataclass
class AttemptResult:
    status: str  # DELIVERED | RETRY | FAILED | DEAD | SKIPPED
    delay_s: float | None = None
    status_code: int | None = None


async def attempt_delivery(
    platform: Platform, environment_id: UUID, delivery_id: UUID
) -> AttemptResult:
    async with tenant_tx(platform.pool, environment_id) as conn:
        d = await fetch_one(
            conn, "select * from events.webhook_delivery where id = %s for update", (delivery_id,)
        )
        if d is None or d["status"] in ("DELIVERED", "DEAD", "FAILED"):
            return AttemptResult("SKIPPED")
        ep = await fetch_one(
            conn, "select * from events.webhook_endpoint where id = %s", (d["endpoint_id"],)
        )
        ev = await fetch_one(
            conn, "select payload from events.outbox_event where id = %s", (d["event_id"],)
        )
        if ep is None or ep["deleted_at"] is not None or not ep["enabled"] or ev is None:
            await conn.execute(
                "update events.webhook_delivery set status = 'FAILED', last_error = %s where id = %s",
                ("endpoint disabled or deleted", delivery_id),
            )
            return AttemptResult("FAILED")
        secrets = [
            await open_for(
                platform,
                conn,
                environment_id,
                ep["secret_sealed"],
                version=ep["secret_key_version"],
                connection_id=ep["id"],
                purpose="webhook_secret",
            )
        ]
        if (
            ep["previous_secret_sealed"]
            and ep["previous_secret_expires_at"]
            and ep["previous_secret_expires_at"] > platform.clock.now()
        ):
            secrets.append(
                await open_for(
                    platform,
                    conn,
                    environment_id,
                    ep["previous_secret_sealed"],
                    version=ep["secret_key_version"],
                    connection_id=ep["id"],
                    purpose="webhook_secret",
                )
            )
    body = json.dumps(ev["payload"], separators=(",", ":"), sort_keys=True).encode()
    ts = int(platform.clock.now().timestamp())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "SecureFabric-Event-Id": ev["payload"]["id"],
        "SecureFabric-Event-Type": ev["payload"]["type"],
        "SecureFabric-Delivery-Id": str(delivery_id),
        "SecureFabric-Timestamp": str(ts),
        "SecureFabric-Signature": ",".join(sign(s, ts, body) for s in secrets),
    }
    attempt_no = d["attempts"] + 1
    started = time.perf_counter()
    code: int | None = None
    error: str | None = None
    excerpt: str | None = None
    try:
        if not ep["url"].startswith("https://") and not platform.settings.egress_allow_private:
            raise EgressDenied("webhook URLs must use https")
        async with httpx2.AsyncClient(
            transport=platform.webhook_transport(), timeout=TIMEOUT_S, follow_redirects=False
        ) as c:
            resp = await c.post(ep["url"], content=body, headers=headers)
        code = resp.status_code
        excerpt = resp.text[:1024] if resp.content else None
    except EgressDenied as exc:
        error = f"egress denied: {exc.message}"
    except httpx2.HTTPError as exc:
        error = f"{type(exc).__name__}: {str(exc)[:200]}"
    latency = int((time.perf_counter() - started) * 1000)

    if code is not None and 200 <= code < 300:
        outcome = AttemptResult("DELIVERED", status_code=code)
    elif error and error.startswith("egress denied"):
        outcome = AttemptResult("FAILED")
    elif code is None or code >= 500 or code in (408, 429):
        if attempt_no > len(RETRY_SCHEDULE_S):
            outcome = AttemptResult("DEAD", status_code=code)
        else:
            outcome = AttemptResult(
                "RETRY",
                RETRY_SCHEDULE_S[attempt_no - 1] * random.uniform(0.9, 1.1),  # noqa: S311 - jitter
                code,
            )
    else:
        outcome = AttemptResult("FAILED", status_code=code)
    instruments().webhook_deliveries.add(1, {"outcome": outcome.status.lower()})

    async with tenant_tx(platform.pool, environment_id) as conn:
        await conn.execute(
            """insert into events.webhook_attempt (delivery_id, environment_id, attempt, status_code, latency_ms,
                                                   response_excerpt, error) values (%s, %s, %s, %s, %s, %s, %s)""",
            (delivery_id, environment_id, attempt_no, code, latency, excerpt, error),
        )
        status = {"DELIVERED": "DELIVERED", "RETRY": "PENDING", "FAILED": "FAILED", "DEAD": "DEAD"}[
            outcome.status
        ]
        await conn.execute(
            """update events.webhook_delivery set status = %s, attempts = %s, last_status_code = %s, last_latency_ms
              = %s,
                      last_error = %s, next_attempt_at = %s, delivered_at = case when %s then now() else delivered_at
                          end
                where id = %s""",
            (
                status,
                attempt_no,
                code,
                latency,
                error,
                platform.clock.now() + timedelta(seconds=outcome.delay_s)
                if outcome.delay_s
                else None,
                outcome.status == "DELIVERED",
                delivery_id,
            ),
        )
        if outcome.status == "DELIVERED":
            await conn.execute(
                "update events.webhook_endpoint set failing_since = null where id = %s", (ep["id"],)
            )
        else:
            row = await fetch_one(
                conn,
                """update events.webhook_endpoint set failing_since = coalesce(failing_since, %s) where id = %s
                   returning failing_since""",
                (platform.clock.now(), ep["id"]),
            )
            if (
                row
                and row["failing_since"]
                and platform.clock.now() - row["failing_since"] >= AUTO_DISABLE_AFTER
            ):
                await conn.execute(
                    """update events.webhook_endpoint set enabled = false,
                              disabled_reason = 'failing continuously for 5 days' where id = %s""",
                    (ep["id"],),
                )
                log.warning("webhook_endpoint_auto_disabled", endpoint_id=str(ep["id"]))
                from securefabric_domain.sync.scheduler import raise_alert

                await raise_alert(
                    conn,
                    "dead_deliveries",
                    f"endpoint {ep['id']} disabled",
                    {"environment_id": str(environment_id)},
                    severity="ticket",
                )
    return outcome


async def deliver_with_retries(
    platform: Platform, environment_id: UUID, delivery_id: UUID, ctx: Any = None
) -> dict[str, Any]:
    """The delivery task. Durable sleeps between attempts (Absurd ``sleep_for``)."""
    for n in range(len(RETRY_SCHEDULE_S) + 2):
        if ctx is not None:
            result = await ctx.step(
                f"attempt-{n}", lambda: _attempt_json(platform, environment_id, delivery_id)
            )
        else:
            result = await _attempt_json(platform, environment_id, delivery_id)
        if result["status"] != "RETRY":
            return dict(result)
        if ctx is not None:
            await ctx.sleep_for(f"wait-{n}", float(result["delay_s"]))
        else:
            return dict(result)
    return {"status": "DEAD"}


async def _attempt_json(
    platform: Platform, environment_id: UUID, delivery_id: UUID
) -> dict[str, Any]:
    r = await attempt_delivery(platform, environment_id, delivery_id)
    return {"status": r.status, "delay_s": r.delay_s, "status_code": r.status_code}
