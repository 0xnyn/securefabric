from enum import StrEnum


class ConnectionPatchStateType0(StrEnum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"
    PAUSED = "PAUSED"

    def __str__(self) -> str:
        return str(self.value)
