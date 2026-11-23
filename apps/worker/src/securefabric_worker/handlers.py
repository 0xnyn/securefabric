"""Task handlers: thin adapters from Absurd tasks to domain services."""

from typing import Any
from uuid import UUID

from absurd_sdk import AsyncAbsurd, AsyncTaskContext

from securefabric_domain.runtime import Platform
from securefabric_tasks import Queue


def is_final_attempt(ctx: AsyncTaskContext) -> bool:
    """Whether Absurd will not retry this task if it raises now."""
    task = getattr(ctx, "_task", None) or {}
    attempt, limit = task.get("attempt"), task.get("max_attempts")
    return attempt is not None and limit is not None and int(attempt) >= int(limit)


def register(client: AsyncAbsurd, platform: Platform, queue: str) -> None:
    if queue in (Queue.SYNC_INTERACTIVE, Queue.SYNC_BULK):

        @client.register_task("sync.slice", queue=queue, default_max_attempts=20)
        async def sync_slice(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.sync.handler import handle_slice

            return await handle_slice(
                platform,
                UUID(params["run_id"]),
                UUID(params["environment_id"]),
                heartbeat=ctx.heartbeat,
            )

    if queue == Queue.CONTROL:

        @client.register_task("connection.verify", queue=queue, default_max_attempts=3)
        async def verify(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.connections import record_verify_crash, verify_connection

            env, cid = UUID(params["environment_id"]), UUID(params["connection_id"])
            reason = params.get("reason", "create")
            try:
                return await verify_connection(
                    platform, env, cid, reason=reason, staged=params.get("staged", False)
                )
            except Exception as exc:  # classified vendor errors never reach here
                await record_verify_crash(
                    platform, env, cid, reason=reason, error=exc, final=is_final_attempt(ctx)
                )
                raise

        @client.register_task("connect.complete", queue=queue, default_max_attempts=2)
        async def connect_complete(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.connect import complete_redirect

            return await complete_redirect(
                platform, params["state"], UUID(params["environment_id"])
            )

        @client.register_task("ingress.process", queue=queue, default_max_attempts=5)
        async def ingress(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.ingress import process_delivery

            return await process_delivery(platform, UUID(params["delivery_row_id"]))

        @client.register_task("passthrough.request", queue=queue, default_max_attempts=1)
        async def passthrough_request(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.passthrough import perform

            return await perform(
                platform,
                UUID(params["environment_id"]),
                UUID(params["connection_id"]),
                params["method"],
                params["path"],
                params.get("query") or {},
            )

        @client.register_task("operator.repair", queue=queue, default_max_attempts=1)
        async def operator_repair(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.operator import perform_repair

            return await perform_repair(
                platform,
                UUID(params["environment_id"]),
                UUID(params["connection_id"]),
                params["action"],
                params.get("params") or {},
            )

        @client.register_task("raw.read", queue=queue, default_max_attempts=1)
        async def raw_read(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.operator import read_raw

            return await read_raw(
                platform, UUID(params["environment_id"]), UUID(params["raw_page_id"])
            )

        @client.register_task("action.perform", queue=queue, default_max_attempts=1)
        async def action(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.actions import perform_action

            return await perform_action(
                platform, UUID(params["environment_id"]), UUID(params["action_id"])
            )

    if queue == Queue.DELIVERY:

        @client.register_task("webhook.deliver", queue=queue, default_max_attempts=3)
        async def deliver(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.events.delivery import deliver_with_retries

            return await deliver_with_retries(
                platform, UUID(params["environment_id"]), UUID(params["delivery_id"]), ctx
            )

    if queue == Queue.MAINTENANCE:

        @client.register_task("maintenance.run", queue=queue, default_max_attempts=3)
        async def maintenance(params: dict[str, Any], ctx: AsyncTaskContext) -> Any:
            from securefabric_domain.maintenance import run_job

            return await run_job(platform, params["job"], params.get("args") or {})
