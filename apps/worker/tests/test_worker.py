"""The worker: every task the platform spawns has a handler on its queue, and roles
map to queues as part 1 describes."""

import re
from pathlib import Path

from absurd_sdk import AsyncAbsurd

from securefabric_tasks import ROLE_QUEUES, Queue
from securefabric_worker.handlers import register
from securefabric_worker.main import ROLES, parse_args

DOMAIN = Path(__file__).parents[3] / "packages/domain/src/securefabric_domain"


class _P:  # handlers only close over the platform; registration never touches it
    pass


def registered(queue: str) -> set[str]:
    client = AsyncAbsurd("postgresql://unused", queue_name=queue)
    register(client, _P(), queue)  # type: ignore[arg-type]
    return set(client._registry)


def spawned_tasks() -> dict[str, str]:
    """task_name -> queue, from every spawn_sql call in the domain."""
    out = {}
    pat = re.compile(r'queue="(\w+)",\s*task_name="([\w.]+)"')
    for py in DOMAIN.rglob("*.py"):
        for queue, name in pat.findall(py.read_text()):
            out[name] = queue
    return out


def test_every_spawned_task_has_a_handler_on_its_queue() -> None:
    spawned = spawned_tasks()
    assert {
        "sync.slice",
        "connection.verify",
        "webhook.deliver",
        "ingress.process",
        "maintenance.run",
    } - {"sync.slice"} <= set(spawned)
    for name, queue in spawned.items():
        assert name in registered(queue), (
            f"{name} is spawned on {queue} but no handler is registered there"
        )
    for q in (Queue.SYNC_INTERACTIVE, Queue.SYNC_BULK):
        assert "sync.slice" in registered(q)


def test_roles_and_queues() -> None:
    assert set(ROLES) == {"scheduler", "sync", "control", "delivery", "maintenance"}
    assert ROLE_QUEUES["sync"] == (Queue.SYNC_INTERACTIVE, Queue.SYNC_BULK)
    assert parse_args(["--role", "control"]).role == "control"


def test_final_attempt_detection() -> None:
    from types import SimpleNamespace
    from typing import Any, cast

    from securefabric_worker.handlers import is_final_attempt

    def ctx(attempt: int, limit: int | None) -> Any:
        return cast(Any, SimpleNamespace(_task={"attempt": attempt, "max_attempts": limit}))

    assert not is_final_attempt(ctx(1, 3))
    assert is_final_attempt(ctx(3, 3))
    assert not is_final_attempt(ctx(5, None))  # unbounded retries: never final
    assert not is_final_attempt(cast(Any, SimpleNamespace()))
