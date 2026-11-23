"""Session-only endpoints: /v1/me, onboarding, environments, members, audit (part 7, section 2)."""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field

from securefabric_api.deps import PlatformDep, PrincipalDep, require_session
from securefabric_api.schemas import RequestModel, ResponseModel, Timestamp
from securefabric_core import NotFoundError, ValidationFailedError
from securefabric_db import fetch_all, fetch_one
from securefabric_domain import tenancy
from securefabric_domain.workos import onboard

router = APIRouter(tags=["account"])


class EnvironmentOut(ResponseModel):
    id: UUID
    slug: str
    name: str
    is_production: bool
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: Timestamp | None = None


class AccountOut(ResponseModel):
    id: UUID
    name: str
    slug: str
    plan: str


class Me(ResponseModel):
    kind: str
    actor_id: str
    email: str | None = None
    name: str | None = None
    role: str | None = None
    is_operator: bool = False
    scopes: list[str]
    account: AccountOut | None = None
    environment_id: UUID | None = None
    environments: list[EnvironmentOut] = Field(default_factory=list)
    needs_onboarding: bool = False


@router.get("/me", name="get_me", summary="Who am I, which account and environments")
async def get_me(principal: PrincipalDep, platform: PlatformDep) -> Me:
    account = None
    envs: list[dict[str, Any]] = []
    if principal.account_id is not None:
        async with platform.pool.connection() as conn:
            account = await fetch_one(
                conn,
                "select id, name, slug, plan from control.account where id = %s",
                (principal.account_id,),
            )
        envs = (
            await tenancy.account_environments(platform, principal.account_id)
            if principal.kind == "user"
            else []
        )
    return Me(
        kind=principal.kind,
        actor_id=principal.actor_id,
        email=principal.extra.get("email"),
        name=principal.extra.get("name"),
        role=principal.role,
        is_operator=principal.is_operator,
        scopes=sorted(principal.scopes),
        account=AccountOut(**account) if account else None,
        environment_id=principal.environment_id,
        environments=[EnvironmentOut(**e) for e in envs],
        needs_onboarding=principal.account_id is None,
    )


class OnboardIn(RequestModel):
    account_name: str = Field(min_length=2, max_length=100)


class OnboardOut(ResponseModel):
    account: AccountOut
    environments: list[EnvironmentOut]


@router.post(
    "/onboarding", name="onboard", status_code=201, summary="Create the account for a first sign-in"
)
async def post_onboarding(
    body: OnboardIn, principal: PrincipalDep, platform: PlatformDep, request: Request
) -> OnboardOut:
    require_session(principal)
    account = await onboard(
        platform,
        getattr(request.app.state, "workos", None),
        principal,
        account_name=body.account_name,
    )
    envs = await tenancy.account_environments(platform, account["id"])
    return OnboardOut(
        account=AccountOut(**{k: account[k] for k in ("id", "name", "slug", "plan")}),
        environments=[EnvironmentOut(**e) for e in envs],
    )


@router.get("/environments", name="list_environments", summary="Environments of my account")
async def list_environments(principal: PrincipalDep, platform: PlatformDep) -> list[EnvironmentOut]:
    if principal.account_id is None:
        return []
    envs = await tenancy.account_environments(platform, principal.account_id)
    if principal.kind == "api_key":
        envs = [e for e in envs if e["id"] == principal.environment_id]
    return [EnvironmentOut(**e) for e in envs]


class EnvironmentIn(RequestModel):
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", max_length=40)
    name: str = Field(min_length=1, max_length=80)
    is_production: bool = False


@router.post("/environments", name="create_environment", status_code=201)
async def create_environment(
    body: EnvironmentIn, principal: PrincipalDep, platform: PlatformDep
) -> EnvironmentOut:
    require_session(principal)
    env = await tenancy.create_environment(
        platform, principal, slug=body.slug, name=body.name, is_production=body.is_production
    )
    return EnvironmentOut(**env)


class EnvironmentPatch(RequestModel):
    name: str | None = None
    settings: dict[str, Any] | None = None


@router.patch(
    "/environments/current",
    name="update_environment",
    summary="Update the selected environment's settings",
)
async def update_environment(
    body: EnvironmentPatch, principal: PrincipalDep, platform: PlatformDep
) -> EnvironmentOut:
    require_session(principal)
    settings = body.settings or {}
    origins = settings.get("allowed_redirect_origins")
    if origins is not None and (
        not isinstance(origins, list)
        or not all(
            isinstance(o, str) and o.startswith(("https://", "http://localhost")) for o in origins
        )
    ):
        raise ValidationFailedError(
            "allowed_redirect_origins must be https origins", code="invalid_settings"
        )
    env = await tenancy.update_environment_settings(platform, principal, settings, body.name)
    return EnvironmentOut(**env)


class MemberOut(ResponseModel):
    user_id: UUID
    email: str
    name: str | None = None
    role: Literal["admin", "developer", "support"]
    joined_at: Timestamp


@router.get("/members", name="list_members")
async def list_members(principal: PrincipalDep, platform: PlatformDep) -> list[MemberOut]:
    require_session(principal)
    async with platform.pool.connection() as conn:
        rows = await fetch_all(
            conn,
            """select u.id as user_id, u.email, u.name, m.role, m.created_at as joined_at
                                          from control.membership m join control.app_user u on u.id = m.user_id
                                         where m.account_id = %s order by m.created_at""",
            (principal.account_id,),
        )
    return [MemberOut(**r) for r in rows]


class InviteIn(RequestModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: Literal["admin", "developer", "support"] = "developer"


class InviteOut(ResponseModel):
    id: str
    email: str
    state: str
    expires_at: str | None = None


@router.post(
    "/members", name="invite_member", status_code=201, summary="Invite a teammate through WorkOS"
)
async def invite_member(
    body: InviteIn, principal: PrincipalDep, platform: PlatformDep, request: Request
) -> InviteOut:
    require_session(principal)
    principal.require_admin()
    workos = getattr(request.app.state, "workos", None)
    org_id = principal.extra.get("workos_org_id")
    if workos is None or not org_id:
        async with platform.pool.connection() as conn:
            acct = await fetch_one(
                conn,
                "select workos_organization_id from control.account where id = %s",
                (principal.account_id,),
            )
        org_id = (acct or {}).get("workos_organization_id")
    if workos is None or not org_id:
        raise ValidationFailedError("Invitations need WorkOS.", code="invitations_unavailable")
    inv = await workos.send_invitation(
        email=body.email,
        organization_id=org_id,
        inviter_user_id=principal.extra.get("workos_user_id"),
    )
    async with platform.pool.connection() as conn, conn.transaction():
        await tenancy.audit(
            conn,
            principal,
            "member.invited",
            target_kind="invitation",
            target_id=inv["id"],
            detail={"email": body.email, "role": body.role},
        )
    return InviteOut(
        id=inv["id"], email=inv["email"], state=inv["state"], expires_at=inv.get("expires_at")
    )


class RolePatch(RequestModel):
    role: Literal["admin", "developer", "support"]


@router.patch("/members/{user_id}", name="update_member")
async def update_member(
    user_id: UUID, body: RolePatch, principal: PrincipalDep, platform: PlatformDep
) -> MemberOut:
    require_session(principal)
    principal.require_admin()
    async with platform.pool.connection() as conn, conn.transaction():
        row = await fetch_one(
            conn,
            "update control.membership set role = %s where account_id = %s and user_id = %s returning user_id",
            (body.role, principal.account_id, user_id),
        )
        if row is None:
            raise NotFoundError("Member not found", code="member_not_found")
        await tenancy.audit(
            conn,
            principal,
            "member.role_changed",
            target_kind="user",
            target_id=user_id,
            detail={"role": body.role},
        )
        m = await fetch_one(
            conn,
            """select u.id as user_id, u.email, u.name, m.role, m.created_at as joined_at
                                       from control.membership m join control.app_user u on u.id = m.user_id
                                      where m.account_id = %s and m.user_id = %s""",
            (principal.account_id, user_id),
        )
    assert m is not None
    return MemberOut(**m)


@router.delete("/members/{user_id}", name="remove_member", status_code=204)
async def remove_member(user_id: UUID, principal: PrincipalDep, platform: PlatformDep) -> None:
    require_session(principal)
    principal.require_admin()
    async with platform.pool.connection() as conn, conn.transaction():
        row = await fetch_one(
            conn,
            "delete from control.membership where account_id = %s and user_id = %s returning user_id",
            (principal.account_id, user_id),
        )
        if row is None:
            raise NotFoundError("Member not found", code="member_not_found")
        await tenancy.audit(
            conn, principal, "member.removed", target_kind="user", target_id=user_id
        )


class AuditEventOut(ResponseModel):
    id: UUID
    actor_kind: str
    actor_id: str | None = None
    action: str
    target_kind: str | None = None
    target_id: str | None = None
    ip: str | None = None
    request_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    at: Timestamp


@router.get(
    "/audit_events", name="list_audit_events", summary="Who did what in this environment (SEC-08)"
)
async def list_audit_events(
    principal: PrincipalDep, platform: PlatformDep, limit: int = 100
) -> list[AuditEventOut]:
    require_session(principal)
    from securefabric_db import tenant_tx

    async with tenant_tx(platform.pool, principal.env) as conn:
        rows = await fetch_all(
            conn,
            "select * from obs.audit_event where environment_id = %s order by at desc limit %s",
            (principal.env, min(max(limit, 1), 500)),
        )
    return [AuditEventOut(**r) for r in rows]
