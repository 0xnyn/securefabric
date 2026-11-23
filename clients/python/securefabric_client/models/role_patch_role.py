from enum import StrEnum


class RolePatchRole(StrEnum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    SUPPORT = "support"

    def __str__(self) -> str:
        return str(self.value)
