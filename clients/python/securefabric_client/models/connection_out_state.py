from enum import StrEnum


class ConnectionOutState(StrEnum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"
    HARD_DELETED = "HARD_DELETED"
    PAUSED = "PAUSED"
    PENDING = "PENDING"

    def __str__(self) -> str:
        return str(self.value)
