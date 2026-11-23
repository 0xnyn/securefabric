from enum import StrEnum


class AlertOutSeverity(StrEnum):
    INFO = "info"
    PAGE = "page"
    TICKET = "ticket"

    def __str__(self) -> str:
        return str(self.value)
