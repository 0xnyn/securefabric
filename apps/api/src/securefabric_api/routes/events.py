"""Outbound webhooks and the event feed (HOOK-01..HOOK-08, part 7 section 9)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import Field

from securefabric_api.deps import IdempotencyDep, PlatformDep, PrincipalDep, csv
from securefabric_api.schemas import RequestModel, ResponseModel, Timestamp
from securefabric_domain.events import endpoints as svc

router = APIRouter(tags=["webhooks"])


class EndpointOut(ResponseModel):
    id: UUID
    url: str
    description: str | None = None
    event_types: list[str]
    enabled: bool
    disabled_reason: str | None = None
    failing_since: Timestamp | None = None
    secret_hint: str | None = None
    previous_secret_expires_at: Timestamp | None = None
    created_at: Timestamp


class EndpointCreated(EndpointOut):
    secret: str = Field(description="Signing secret. Shown once.")


class EndpointIn(RequestModel):
    url: str
    description: str | None = None
    event_types: list[str] = Field(default_factory=list, description="Empty means every event type")
    enabled: bool = True


class EndpointPatch(RequestModel):
    url: str | None = None
    description: str | None = None
    event_types: list[str] | None = None
    enabled: bool | None = None


@router.get("/webhook_endpoints", name="list_webhook_endpoints")
async def list_endpoints(principal: PrincipalDep, platform: PlatformDep) -> list[EndpointOut]:
    return [EndpointOut(**e) for e in await svc.list_endpoints(platform, principal)]


@router.post(
    "/webhook_endpoints",
    name="create_webhook_endpoint",
    status_code=201,
    dependencies=[IdempotencyDep],
)
async def create_endpoint(
    body: EndpointIn, principal: PrincipalDep, platform: PlatformDep
) -> EndpointCreated:
    return EndpointCreated(
        **await svc.create_endpoint(
            platform,
            principal,
            url=body.url,
            description=body.description,
            event_types=body.event_types,
            enabled=body.enabled,
        )
    )


@router.get("/webhook_endpoints/{endpoint_id}", name="get_webhook_endpoint")
async def get_endpoint(
    endpoint_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> EndpointOut:
    return EndpointOut(**await svc.get_endpoint(platform, principal, endpoint_id))


@router.patch("/webhook_endpoints/{endpoint_id}", name="update_webhook_endpoint")
async def update_endpoint(
    endpoint_id: UUID, body: EndpointPatch, principal: PrincipalDep, platform: PlatformDep
) -> EndpointOut:
    return EndpointOut(
        **await svc.update_endpoint(
            platform, principal, endpoint_id, body.model_dump(exclude_unset=True)
        )
    )


@router.delete("/webhook_endpoints/{endpoint_id}", name="delete_webhook_endpoint", status_code=204)
async def delete_endpoint(
    endpoint_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> None:
    await svc.delete_endpoint(platform, principal, endpoint_id)


@router.post("/webhook_endpoints/{endpoint_id}/rotate_secret", name="rotate_webhook_secret")
async def rotate(
    endpoint_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> EndpointCreated:
    return EndpointCreated(**await svc.rotate_secret(platform, principal, endpoint_id))


class PingOut(ResponseModel):
    event_id: str
    delivery_id: UUID


@router.post("/webhook_endpoints/{endpoint_id}/ping", name="ping_webhook_endpoint", status_code=202)
async def ping(endpoint_id: UUID, principal: PrincipalDep, platform: PlatformDep) -> PingOut:
    return PingOut(**await svc.ping(platform, principal, endpoint_id))


class DeliveryOut(ResponseModel):
    id: UUID
    event_id: str
    event_type: str
    endpoint_id: UUID
    status: str
    attempts: int
    next_attempt_at: Timestamp | None = None
    last_status_code: int | None = None
    last_latency_ms: int | None = None
    last_error: str | None = None
    created_at: Timestamp
    delivered_at: Timestamp | None = None
    attempts_log: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/webhook_endpoints/{endpoint_id}/deliveries", name="list_webhook_deliveries")
async def deliveries(
    endpoint_id: UUID,
    principal: PrincipalDep,
    platform: PlatformDep,
    status: str | None = None,
    limit: int = 100,
) -> list[DeliveryOut]:
    return [
        DeliveryOut(**d)
        for d in await svc.list_deliveries(
            platform, principal, endpoint_id, status=csv(status), limit=limit
        )
    ]


class ReplayOut(ResponseModel):
    id: UUID
    status: str


@router.post(
    "/webhook_deliveries/{delivery_id}/replay", name="replay_webhook_delivery", status_code=202
)
async def replay(delivery_id: UUID, principal: PrincipalDep, platform: PlatformDep) -> ReplayOut:
    return ReplayOut(**await svc.replay(platform, principal, delivery_id))


class ReplayRangeIn(RequestModel):
    since: Timestamp
    until: Timestamp | None = None


class ReplayRangeOut(ResponseModel):
    replayed: int


@router.post(
    "/webhook_endpoints/{endpoint_id}/replay", name="replay_webhook_range", status_code=202
)
async def replay_range(
    endpoint_id: UUID, body: ReplayRangeIn, principal: PrincipalDep, platform: PlatformDep
) -> ReplayRangeOut:
    return ReplayRangeOut(
        replayed=await svc.replay_range(
            platform, principal, endpoint_id, since=body.since, until=body.until
        )
    )


class EventsPage(ResponseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None = None


@router.get(
    "/events", name="list_events", tags=["events"], summary="The outbox as a pull feed, in id order"
)
async def events(
    principal: PrincipalDep,
    platform: PlatformDep,
    after: str | None = None,
    type: str | None = None,
    connectionId: UUID | None = None,
    limit: int = 100,
) -> EventsPage:
    return EventsPage(
        **await svc.events_feed(
            platform,
            principal,
            after=after,
            types=csv(type),
            connection_id=connectionId,
            limit=limit,
        )
    )
