from enum import StrEnum


class MemberOutRole(StrEnum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    SUPPORT = "support"

    def __str__(self) -> str:
        return str(self.value)
