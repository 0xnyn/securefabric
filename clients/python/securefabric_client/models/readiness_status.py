from enum import StrEnum


class ReadinessStatus(StrEnum):
    DEGRADED = "degraded"
    OK = "ok"

    def __str__(self) -> str:
        return str(self.value)
