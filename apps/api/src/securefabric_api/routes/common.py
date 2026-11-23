"""Shared response models."""

from typing import Any

from securefabric_api.schemas import ResponseModel


class Page[T](ResponseModel):
    """Keyset page (API-02)."""

    items: list[T]
    next_cursor: str | None = None
    previous_cursor: str | None = None


class Deleted(ResponseModel):
    id: Any
    deleted: bool = True


def page(p: Any) -> dict[str, Any]:
    return {"items": p.items, "next_cursor": p.next_cursor, "previous_cursor": p.previous_cursor}
