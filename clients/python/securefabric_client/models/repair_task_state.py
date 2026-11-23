from enum import StrEnum


class RepairTaskState(StrEnum):
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING = "pending"
    RUNNING = "running"
    SLEEPING = "sleeping"

    def __str__(self) -> str:
        return str(self.value)
