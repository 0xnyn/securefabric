"""Task contracts and the transactional spawn the engine relies on."""

import uuid
from typing import Any

import psycopg
import pytest
from pydantic import ValidationError

from securefabric_tasks import ALL_TASKS, ROLE_QUEUES, SYNC_SLICE_BULK, Queue, SliceParams
from securefabric_tasks.spec import spawn_sql


def test_every_task_runs_on_a_known_queue_that_some_worker_role_serves() -> None:
    served = {q for queues in ROLE_QUEUES.values() for q in queues}
    assert served == set(Queue)
    for spec in ALL_TASKS:
        assert spec.queue in set(Queue), spec.name
        assert spec.max_attempts >= 1
    # One handler per (queue, name): the worker registers each pair once.
    pairs = [(spec.queue, spec.name) for spec in ALL_TASKS]
    assert len(pairs) == len(set(pairs))


def test_params_are_strict_and_frozen() -> None:
    with pytest.raises(ValidationError):
        SliceParams.model_validate({"run_id": "r", "environment_id": "e", "extra": 1})
    p = SliceParams(run_id="r", environment_id="e")
    with pytest.raises(ValidationError):
        p.slice = 2  # type: ignore[misc]


def test_queues_exist_in_the_database(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        names = {r[0] for r in conn.execute("select queue_name from absurd.queues")}
    assert set(Queue) <= names


async def _count(conn: psycopg.AsyncConnection[Any], key: str) -> int:
    cur = await conn.execute(
        "select count(*) from absurd.t_sync_bulk where idempotency_key = %s", (key,)
    )
    row = await cur.fetchone()
    assert row is not None
    return int(row[0])


async def test_spawn_sql_commits_with_the_caller_and_dedups_by_key(database_url: str) -> None:
    key = f"test-{uuid.uuid4()}"
    params = SliceParams(run_id=str(uuid.uuid4()), environment_id=str(uuid.uuid4()))
    spawn: dict[str, Any] = {
        "queue": SYNC_SLICE_BULK.queue,
        "task_name": SYNC_SLICE_BULK.name,
        "params": params.model_dump(mode="json"),
        "idempotency_key": key,
    }
    async with await psycopg.AsyncConnection.connect(database_url) as conn:
        # Rolled back with the caller's transaction: no task.
        async with conn.transaction(force_rollback=True):
            await spawn_sql(conn, **spawn)
        assert await _count(conn, key) == 0
        try:
            async with conn.transaction():
                first = await spawn_sql(conn, **spawn)
            async with conn.transaction():
                second = await spawn_sql(conn, **spawn)
            assert first == second and await _count(conn, key) == 1
        finally:
            async with conn.transaction():
                await conn.execute(
                    "delete from absurd.t_sync_bulk where idempotency_key = %s", (key,)
                )
