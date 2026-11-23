"""Connections (CON-01..CON-14) and jobs (SYNC-06, SYNC-13, SYNC-14, OBS-01)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from securefabric_api.deps import (
    IdempotencyDep,
    PlatformDep,
    PrincipalDep,
    allow_params,
    csv,
    tag_filters,
    uuids,
)
from securefabric_api.routes.common import Page, page
from securefabric_api.schemas import RequestModel, ResponseModel, Timestamp
from securefabric_core import NotFoundError
from securefabric_db import fetch_all, fetch_one, tenant_tx
from securefabric_domain import connections as svc
from securefabric_domain.sync import jobs
from securefabric_domain.sync.bundle import budget_key_for
from securefabric_domain.tenancy import audit

router = APIRouter(tags=["connections"])
jobs_router = APIRouter(tags=["jobs"])


class HealthOut(ResponseModel):
    name: str
    status: str
    description: str | None = None
    resolution_owner: str | None = None
    details: list[dict[str, Any]] | None = None


class StreamStatus(ResponseModel):
    name: str
    object: str
    enabled: bool
    grant: str | None = None
    grant_detail: str | None = None
    endpoint: str | None = None
    interval_s: int | None = None
    schedule_state: str | None = None
    next_run_at: Timestamp | None = None
    last_success_at: Timestamp | None = None
    record_count: int = 0
    deleted_count: int = 0
    capabilities: dict[str, Any] = Field(default_factory=dict)


class Authorization(ResponseModel):
    auth_mode: str
    fields_set: list[str]
    rotated_at: Timestamp | None = None
    last_refresh_at: Timestamp | None = None
    refresh_exhausted: bool = False


class ConnectionOut(ResponseModel):
    id: UUID
    vendor: str
    connector_version: str
    identifier: str | None = None
    organization_id: UUID
    integration_id: UUID
    state: Literal["PENDING", "ACTIVE", "PAUSED", "DELETED", "HARD_DELETED"]
    is_active: bool
    is_sandbox: bool
    direction: str
    options: dict[str, Any]
    connection_config: dict[str, Any]
    metadata: dict[str, Any]
    tags: dict[str, Any]
    health: HealthOut
    health_changed_at: Timestamp | None = None
    pending_detail: str | None = None
    created_at: Timestamp
    updated_at: Timestamp
    deleted_at: Timestamp | None = None
    authorization: Authorization | None = None
    streams: list[StreamStatus] | None = None
    refresh_interval_secs: int | None = None
    oauth2_authorize_url: str | None = Field(
        default=None, description="Leen-compatible name for authorize_url"
    )
    authorize_url: str | None = None


class ConnectionIn(RequestModel):
    vendor: str | None = Field(
        default=None, description="e.g. GITHUB; resolves to the default integration"
    )
    integration: str | None = Field(default=None, description="integration id or key")
    credentials: dict[str, Any] | None = Field(
        default=None, description="Write-only. Sealed before the request returns."
    )
    options: dict[str, Any] | None = None
    identifier: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None
    tags: dict[str, str] | None = None
    is_sandbox: bool = False


class ConnectionPatch(RequestModel):
    state: Literal["ACTIVE", "PAUSED", "DELETED"] | None = None
    options: dict[str, Any] | None = None
    credentials: dict[str, Any] | None = Field(
        default=None, description="Rotation: verified before swapping (AUTH-11)"
    )
    tags: dict[str, str] | None = None
    identifier: str | None = None


@router.post(
    "/organizations/{organization_id}/connections",
    name="create_connection",
    status_code=201,
    dependencies=[IdempotencyDep],
)
async def create_connection(
    organization_id: UUID, body: ConnectionIn, principal: PrincipalDep, platform: PlatformDep
) -> ConnectionOut:
    return ConnectionOut(
        **await svc.create_connection(
            platform,
            principal,
            organization_id=organization_id,
            vendor=body.vendor,
            integration=body.integration,
            credentials=body.credentials,
            options=body.options,
            identifier=body.identifier,
            metadata=body.metadata,
            tags=body.tags,
            is_sandbox=body.is_sandbox,
        )
    )


@router.get(
    "/connections",
    name="list_connections",
    dependencies=[
        Depends(
            allow_params(
                "organizationId",
                "vendor",
                "state",
                "healthStatus",
                "healthStatusCodes",
                "integrationId",
            )
        )
    ],
)
async def list_connections(
    request: Request,
    principal: PrincipalDep,
    platform: PlatformDep,
    organizationId: str | None = None,
    vendor: str | None = None,
    state: str | None = None,
    healthStatus: str | None = None,
    healthStatusCodes: str | None = None,
    integrationId: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> Page[ConnectionOut]:
    p = await svc.list_connections(
        platform,
        principal,
        organization_id=(uuids([organizationId], "organizationId") or [None])[0]
        if organizationId
        else None,
        vendor=csv(vendor),
        state=csv(state),
        health_status=csv(healthStatus),
        health_codes=csv(healthStatusCodes),
        tags=tag_filters(request) or None,
        integration_id=(uuids([integrationId], "integrationId") or [None])[0]
        if integrationId
        else None,
        cursor=cursor,
        limit=limit,
    )
    return Page[ConnectionOut](**page(p))


@router.get("/connections/{connection_id}", name="get_connection")
async def get_connection(
    connection_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> ConnectionOut:
    return ConnectionOut(**await svc.get_connection(platform, principal, connection_id))


@router.patch("/connections/{connection_id}", name="update_connection")
async def update_connection(
    connection_id: UUID, body: ConnectionPatch, principal: PrincipalDep, platform: PlatformDep
) -> ConnectionOut:
    return ConnectionOut(
        **await svc.update_connection(
            platform, principal, connection_id, body.model_dump(exclude_unset=True)
        )
    )


@router.delete("/connections/{connection_id}", name="delete_connection", status_code=204)
async def delete_connection(
    connection_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> None:
    await svc.delete_connection(platform, principal, connection_id)


@router.put("/connections/{connection_id}/metadata", name="replace_connection_metadata")
async def put_metadata(
    connection_id: UUID, body: dict[str, Any], principal: PrincipalDep, platform: PlatformDep
) -> dict[str, Any]:
    return await svc.set_metadata(platform, principal, connection_id, body, merge=False)


@router.patch("/connections/{connection_id}/metadata", name="merge_connection_metadata")
async def patch_metadata(
    connection_id: UUID, body: dict[str, Any], principal: PrincipalDep, platform: PlatformDep
) -> dict[str, Any]:
    return await svc.set_metadata(platform, principal, connection_id, body, merge=True)


class TestResult(ResponseModel):
    is_valid: bool
    message: str | None = None
    grants: dict[str, str] = Field(default_factory=dict)
    pending: bool = False


@router.get(
    "/connections/{connection_id}/test",
    name="test_connection",
    summary="Verify the credentials now (waits up to 30 s; a rejection is is_valid=false)",
)
async def connection_test(
    connection_id: UUID, principal: PrincipalDep, platform: PlatformDep, wait: float = 30.0
) -> TestResult:
    return TestResult(
        **await svc.run_connection_test(
            platform, principal, connection_id, wait_s=min(max(wait, 0.5), 30.0)
        )
    )


class HealthEventOut(ResponseModel):
    from_code: str | None = None
    to_code: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    job_id: UUID | None = None
    at: Timestamp


@router.get("/connections/{connection_id}/health/history", name="connection_health_history")
async def health_history(
    connection_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> list[HealthEventOut]:
    return [
        HealthEventOut(**h) for h in await svc.health_history(platform, principal, connection_id)
    ]


# ---------------------------------------------------------------- jobs


class StreamRunOut(ResponseModel):
    id: UUID
    stream: str
    mode: str
    state: str
    priority: int
    attempt: int
    added: int
    updated: int
    deleted: int
    unchanged: int
    quarantined: int
    pages: int
    vendor_requests: int
    health_code: str | None = None
    warning: str | None = None
    error: dict[str, Any] | None = None
    not_before: Timestamp | None = None
    created_at: Timestamp
    started_at: Timestamp | None = None
    finished_at: Timestamp | None = None


class JobOut(ResponseModel):
    id: UUID
    connection_id: UUID
    type: str
    status: str
    requested_by: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    health_code: str | None = None
    failure_reason: str | None = None
    created_at: Timestamp
    started_at: Timestamp | None = None
    finished_at: Timestamp | None = None
    streams: list[StreamRunOut] | None = None


class JobIn(RequestModel):
    streams: list[str] | None = None
    force_full_refresh: bool = False
    since: Timestamp | None = None


class ResetIn(RequestModel):
    streams: list[str] | None = None
    wipe: bool = Field(
        default=False, description="Delete the connection's rows first (admins only)"
    )


async def _job_out(conn: Any, job: dict[str, Any], *, with_runs: bool = True) -> JobOut:
    runs = (
        await fetch_all(
            conn, "select * from sync.stream_run where job_id = %s order by stream", (job["id"],)
        )
        if with_runs
        else None
    )
    return JobOut(**job, streams=[StreamRunOut(**r) for r in runs] if runs is not None else None)


@router.post(
    "/connections/{connection_id}/jobs",
    name="create_job",
    status_code=202,
    dependencies=[IdempotencyDep],
)
async def create_job(
    connection_id: UUID, body: JobIn, principal: PrincipalDep, platform: PlatformDep
) -> JobOut:
    principal.require("jobs:execute")
    async with tenant_tx(platform.pool, principal.env) as conn:
        key = await budget_key_for(platform, conn, connection_id)
        job_id = await jobs.on_demand(
            platform,
            conn,
            connection_id,
            streams=body.streams,
            force_full_refresh=body.force_full_refresh,
            since=body.since,
            requested_by=f"{principal.kind}:{principal.actor_id}",
            budget_key=key,
        )
        await audit(
            conn,
            principal,
            "job.requested",
            target_kind="connection",
            target_id=connection_id,
            detail={"job_id": str(job_id), "streams": body.streams},
        )
        job = await fetch_one(conn, "select * from sync.job where id = %s", (job_id,))
        assert job is not None
        return await _job_out(conn, job)


@router.get(
    "/connections/{connection_id}/jobs",
    name="list_connection_jobs",
    dependencies=[Depends(allow_params("status", "type", "startedAtSince"))],
)
async def list_connection_jobs(
    connection_id: UUID,
    principal: PrincipalDep,
    platform: PlatformDep,
    status: str | None = None,
    type: str | None = None,
    startedAtSince: datetime | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> list[JobOut]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        await svc.get_row(conn, connection_id, include_deleted=True)
        rows = await fetch_all(
            conn,
            """select * from sync.job where connection_id = %s and (%s::text[] is null or status = any(%s))
                  and (%s::text[] is null or type = any(%s)) and (%s::timestamptz is null or started_at >= %s)
                order by created_at desc limit %s""",
            (
                connection_id,
                csv(status),
                csv(status),
                csv(type),
                csv(type),
                startedAtSince,
                startedAtSince,
                min(max(limit, 1), 500),
            ),
        )
        return [await _job_out(conn, r) for r in rows]


@router.post(
    "/connections/{connection_id}/reset",
    name="reset_connection",
    status_code=202,
    dependencies=[IdempotencyDep],
)
async def reset_connection(
    connection_id: UUID, body: ResetIn, principal: PrincipalDep, platform: PlatformDep
) -> JobOut:
    principal.require("jobs:execute")
    if body.wipe:
        principal.require_admin()
    async with tenant_tx(platform.pool, principal.env) as conn:
        key = await budget_key_for(platform, conn, connection_id)
        job_id = await jobs.reset_connection(
            platform,
            conn,
            connection_id,
            streams=body.streams,
            wipe=body.wipe,
            requested_by=f"{principal.kind}:{principal.actor_id}",
            budget_key=key,
        )
        await audit(
            conn,
            principal,
            "connection.reset",
            target_kind="connection",
            target_id=connection_id,
            detail={"wipe": body.wipe, "streams": body.streams},
        )
        job = await fetch_one(conn, "select * from sync.job where id = %s", (job_id,))
        assert job is not None
        return await _job_out(conn, job)


@jobs_router.get("/jobs/{job_id}", name="get_job")
async def get_job(job_id: UUID, principal: PrincipalDep, platform: PlatformDep) -> JobOut:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        job = await fetch_one(conn, "select * from sync.job where id = %s", (job_id,))
        if job is None:
            raise NotFoundError("Job not found", code="job_not_found")
        return await _job_out(conn, job)


@jobs_router.post("/jobs/{job_id}/cancel", name="cancel_job", status_code=202)
async def cancel_job(job_id: UUID, principal: PrincipalDep, platform: PlatformDep) -> JobOut:
    principal.require("jobs:execute")
    async with tenant_tx(platform.pool, principal.env) as conn:
        await jobs.cancel_job(conn, job_id, platform.clock.now())
        await audit(conn, principal, "job.cancelled", target_kind="job", target_id=job_id)
        job = await fetch_one(conn, "select * from sync.job where id = %s", (job_id,))
        assert job is not None
        return await _job_out(conn, job)


class LogLine(ResponseModel):
    at: Timestamp
    level: str
    kind: str
    message: str
    http: dict[str, Any] | None = None
    operation_id: UUID
    stream: str | None = None


@jobs_router.get(
    "/jobs/{job_id}/logs", name="get_job_logs", summary="Operation log lines of a job (OBS-01)"
)
async def job_logs(
    job_id: UUID, principal: PrincipalDep, platform: PlatformDep, limit: int = 1000
) -> list[LogLine]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        if await fetch_one(conn, "select 1 from sync.job where id = %s", (job_id,)) is None:
            raise NotFoundError("Job not found", code="job_not_found")
        rows = await fetch_all(
            conn,
            """select e.at, e.level, e.kind, e.message, e.http, e.operation_id, split_part(o.action, ':', 1) as stream
                 from obs.operation o join obs.operation_event e on e.operation_id = o.id
                where o.job_id = %s order by e.at, e.id limit %s""",
            (job_id, min(max(limit, 1), 5000)),
        )
    return [LogLine(**r) for r in rows]
