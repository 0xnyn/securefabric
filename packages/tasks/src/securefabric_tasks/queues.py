"""Queue names (docs/plan/01-architecture.md, section 5; part 4, section 2).

Two sync queues with separate worker pools give a hard reservation: bulk work
can never occupy the interactive workers.
"""

from enum import StrEnum


class Queue(StrEnum):
    SYNC_INTERACTIVE = "sync_interactive"
    SYNC_BULK = "sync_bulk"
    CONTROL = "control"
    DELIVERY = "delivery"
    MAINTENANCE = "maintenance"


ROLE_QUEUES: dict[str, tuple[Queue, ...]] = {
    "sync": (Queue.SYNC_INTERACTIVE, Queue.SYNC_BULK),
    "sync-interactive": (Queue.SYNC_INTERACTIVE,),
    "sync-bulk": (Queue.SYNC_BULK,),
    "control": (Queue.CONTROL,),
    "delivery": (Queue.DELIVERY,),
    "maintenance": (Queue.MAINTENANCE,),
}
