"""Read-only passthrough (RAW-01): a vendor request on the customer's behalf.

Only requests matching the connector's ``passthrough_allowlist`` are allowed
(``GET /repos/{owner}/{repo}`` style templates). The control worker performs
them, because only workers can open credentials; the API waits for the result.
Bodies are size-capped and redacted; nothing is stored beyond the operation log.
"""

import asyncio
import json
import re
from typing import Any
from uuid import UUID

from securefabric_cdk.errors import ConnectorError
from securefabric_core import ValidationFailedError
from securefabric_core.redact import redact
from securefabric_db import fetch_one, tenant_tx
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal, audit
from securefabric_tasks.spec import spawn_sql

MAX_BODY = 256 * 1024


def _template_regex(template: str) -> re.Pattern[str]:
    method, _, path = template.partition(" ")
    pattern = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(path))
    return re.compile(rf"^{method}\s{pattern}$")


def allowed(platform: Platform, connector_id: str, method: str, path: str) -> bool:
    if ".." in path or "//" in path or not path.startswith("/"):
        return False
    templates = platform.registry.manifest(connector_id).passthrough_allowlist
    return any(
        _template_regex(t).match(f"{method.upper()} {path.split('?')[0]}") for t in templates
    )


async def request(
    platform: Platform,
    principal: Principal,
    connection_id: UUID,
    *,
    method: str,
    path: str,
    query: dict[str, str] | None,
    wait_s: float = 30.0,
) -> dict[str, Any]:
    principal.require("data:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        c = await fetch_one(
            conn,
            "select connector_id, state from control.connection where id = %s and deleted_at is null",
            (connection_id,),
        )
        if c is None:
            from securefabric_core import NotFoundError

            raise NotFoundError("Connection not found", code="connection_not_found")
        if method.upper() != "GET" or not allowed(platform, c["connector_id"], method, path):
            raise ValidationFailedError(
                f"{method} {path} is not on the {c['connector_id']} passthrough allowlist.",
                code="passthrough_not_allowed",
                errors=[
                    {
                        "field": "path",
                        "message": "allowed: "
                        + ", ".join(
                            platform.registry.manifest(c["connector_id"]).passthrough_allowlist
                        ),
                    }
                ],
            )
        task = await spawn_sql(
            conn,
            queue="control",
            task_name="passthrough.request",
            params={
                "connection_id": str(connection_id),
                "environment_id": str(principal.env),
                "method": method.upper(),
                "path": path,
                "query": query or {},
            },
            max_attempts=1,
        )
        await audit(
            conn,
            principal,
            "passthrough.requested",
            target_kind="connection",
            target_id=connection_id,
            detail={"method": method, "path": path},
        )
    deadline = asyncio.get_running_loop().time() + wait_s
    while asyncio.get_running_loop().time() < deadline:
        async with platform.pool.connection() as conn:
            snap = await fetch_one(
                conn, "select state, result from absurd.get_task_result('control', %s)", (task,)
            )
        if snap and snap["state"] in ("completed", "failed", "cancelled"):
            return snap["result"] or {"status": None, "error": "the request failed"}
        await asyncio.sleep(0.2)
    return {"status": None, "error": "timed out waiting for a worker", "task_id": task}


async def perform(
    platform: Platform,
    environment_id: UUID,
    connection_id: UUID,
    method: str,
    path: str,
    query: dict[str, str],
) -> dict[str, Any]:
    from securefabric_domain.sync.bundle import build_context, load_bundle
    from securefabric_domain.sync.oplog import finish_operation, start_operation

    async with tenant_tx(platform.pool, environment_id) as conn:
        bundle = await load_bundle(platform, conn, connection_id)
    if not allowed(platform, bundle.manifest.id, method, path):  # re-check in the worker
        return {"status": None, "error": "not allowed"}
    op = await start_operation(
        platform.pool,
        environment_id=environment_id,
        kind="passthrough",
        action=f"{method} {path}",
        connection_id=connection_id,
        organization_id=bundle.connection["organization_id"],
    )
    ctx = await build_context(
        platform,
        bundle,
        stream=None,
        op_log=op,
        capture=None,
        clock=platform.clock,
        interactive=True,
    )
    try:
        resp = await ctx.http.request(method, path, params=query, allow=tuple(range(400, 600)))
        body: Any
        try:
            body = resp.json() if resp.content else None
        except ValueError:
            body = resp.text[:MAX_BODY]
        raw = json.dumps(body, default=str)
        truncated = len(raw) > MAX_BODY
        result = {
            "status": resp.status_code,
            "truncated": truncated,
            "headers": {
                k: v
                for k, v in resp.headers.items()
                if k.lower() in ("content-type", "link", "x-ratelimit-remaining")
            },
            "body": redact(json.loads(raw[:MAX_BODY]) if not truncated else raw[:MAX_BODY]),
        }
        await finish_operation(
            platform.pool,
            op,
            status="success" if resp.status_code < 400 else "failed",
            summary={"status": resp.status_code},
        )
        return result
    except ConnectorError as exc:
        await finish_operation(platform.pool, op, status="failed", summary={"error": exc.message})
        return {"status": None, "error": exc.message}
    finally:
        await ctx.http.aclose()
