from enum import StrEnum


class AdminRepairAction(StrEnum):
    PAUSE = "pause"
    PURGE_NOW = "purge_now"
    REBUILD_COUNTS = "rebuild_counts"
    RENORMALIZE = "renormalize"
    REPROBE = "reprobe"
    RESET = "reset"
    RESUME = "resume"
    TRIGGER = "trigger"

    def __str__(self) -> str:
        return str(self.value)
