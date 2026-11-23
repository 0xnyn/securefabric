"""Keyset pagination with opaque, signed, versioned cursors (API-02, API-03).

A cursor encodes the sort key of the boundary row, the sort direction, a hash of
the active filters and the scope. Signing means a tampered cursor is a 400, not
a strange query. Sending a different filter set than the cursor was created
with is a 400 naming the parameter that changed.
"""

import base64
import hashlib
import hmac
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import sql

from securefabric_core import BadRequestError
from securefabric_core.canonical import canonical_json
from securefabric_db import Conn, fetch_all

CURSOR_VERSION = 1
MAX_LIMIT = 500
DEFAULT_LIMIT = 100


@dataclass(frozen=True, slots=True)
class Cursor:
    sort: str  # e.g. "updated_at:asc"
    after: list[Any]  # sort key values of the boundary row, then id
    direction: str  # "next" | "prev"
    filters: dict[str, Any]
    scope: str


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _jsonable(v: Any) -> Any:
    if isinstance(v, datetime):
        return {"t": v.isoformat()}
    if isinstance(v, UUID):
        return str(v)
    return v


def _from_jsonable(v: Any) -> Any:
    if isinstance(v, dict) and set(v) == {"t"}:
        return datetime.fromisoformat(v["t"])
    return v


def encode_cursor(key: bytes, cursor: Cursor) -> str:
    body = json.dumps(
        {
            "v": CURSOR_VERSION,
            "s": cursor.sort,
            "a": [_jsonable(x) for x in cursor.after],
            "d": cursor.direction,
            "f": cursor.filters,
            "c": cursor.scope,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    sig = hmac.new(key, body, hashlib.sha256).digest()[:16]
    return _b64(body) + "." + _b64(sig)


def decode_cursor(key: bytes, token: str) -> Cursor:
    try:
        body_b64, sig_b64 = token.split(".", 1)
        body = _unb64(body_b64)
        sig = _unb64(sig_b64)
    except (ValueError, TypeError) as exc:
        raise BadRequestError("The cursor is malformed.", code="invalid_cursor") from exc
    expected = hmac.new(key, body, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(sig, expected):
        raise BadRequestError("The cursor is invalid or was tampered with.", code="invalid_cursor")
    data = json.loads(body)
    if data.get("v") != CURSOR_VERSION:
        raise BadRequestError(
            "The cursor was issued by an incompatible API version.", code="invalid_cursor"
        )
    return Cursor(
        sort=data["s"],
        after=[_from_jsonable(x) for x in data["a"]],
        direction=data["d"],
        filters=data["f"],
        scope=data["c"],
    )


def check_cursor_filters(cursor: Cursor, filters: dict[str, Any], scope: str) -> None:
    """The filter set travels inside the cursor. Resending the same values is fine;
    a different value is a 400 naming the parameter (API-03)."""
    if cursor.scope != scope:
        raise BadRequestError(
            "The cursor belongs to a different scope.", code="cursor_scope_mismatch"
        )
    for name in sorted(set(cursor.filters) | set(filters)):
        if name not in filters:
            continue  # omitted on follow-up requests: the cursor's value applies
        if canonical_json(cursor.filters.get(name)) != canonical_json(filters[name]):
            raise BadRequestError(
                f"The parameter {name!r} differs from the one this cursor was created with.",
                code="cursor_filter_mismatch",
                errors=[{"field": name, "message": "differs from the cursor's filter"}],
            )


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if limit < 1 or limit > MAX_LIMIT:
        raise BadRequestError(
            f"limit must be between 1 and {MAX_LIMIT}.",
            code="invalid_limit",
            errors=[{"field": "limit", "message": f"must be 1..{MAX_LIMIT}"}],
        )
    return limit


@dataclass(frozen=True, slots=True)
class PageOut[T]:
    items: list[T]
    next_cursor: str | None
    previous_cursor: str | None


# ---------------------------------------------------------------- keyset queries


async def keyset_page(
    conn: Conn,
    *,
    key: bytes,
    base: sql.Composable,
    where: Sequence[sql.Composable],
    params: Sequence[Any],
    sort_name: str,
    sort_exprs: Sequence[str],
    sort_keys: Callable[[dict[str, Any]], list[Any]],
    descending: bool,
    cursor_token: str | None,
    filters: dict[str, Any],
    scope: str,
    limit: int,
) -> PageOut[dict[str, Any]]:
    """Run ``base`` (a ``select ... from ...``) with keyset paging.

    ``sort_exprs`` are SQL expressions ending in the id tiebreaker; ``sort_keys``
    extracts the same values from a row. All columns share one direction, so a
    row-value comparison is exact and index-friendly.
    """
    clauses = list(where)
    args = list(params)
    direction = "next"
    if cursor_token:
        cur = decode_cursor(key, cursor_token)
        check_cursor_filters(cur, filters, scope)
        if cur.sort != sort_name:
            raise BadRequestError(
                "The sort differs from the one this cursor was created with.",
                code="cursor_filter_mismatch",
                errors=[{"field": "sort", "message": "differs from the cursor's sort"}],
            )
        filters = cur.filters
        direction = cur.direction
        forward = (direction == "next") != descending
        op = ">" if forward else "<"
        cols = sql.SQL(", ").join(sql.SQL(e) for e in sort_exprs)
        marks = sql.SQL(", ").join(sql.Placeholder() for _ in sort_exprs)
        clauses.append(sql.SQL("({}) {} ({})").format(cols, sql.SQL(op), marks))
        args.extend(cur.after)
    reverse = direction == "prev"
    order_desc = descending != reverse
    order = sql.SQL(", ").join(
        sql.SQL("{} {}").format(sql.SQL(e), sql.SQL("desc" if order_desc else "asc"))
        for e in sort_exprs
    )
    query = sql.SQL("{} {} order by {} limit {}").format(
        base,
        sql.SQL("where ") + sql.SQL(" and ").join(clauses) if clauses else sql.SQL(""),
        order,
        sql.Literal(limit + 1),
    )
    rows = await fetch_all(conn, query, args)
    has_more = len(rows) > limit
    rows = rows[:limit]
    if reverse:
        rows.reverse()
    if not rows:
        return PageOut(items=[], next_cursor=None, previous_cursor=None)

    def mk(row: dict[str, Any], d: str) -> str:
        return encode_cursor(
            key,
            Cursor(sort=sort_name, after=sort_keys(row), direction=d, filters=filters, scope=scope),
        )

    next_cursor: str | None
    previous_cursor: str | None
    if reverse:
        next_cursor = mk(rows[-1], "next")
        previous_cursor = mk(rows[0], "prev") if has_more else None
    else:
        next_cursor = mk(rows[-1], "next") if has_more else None
        previous_cursor = mk(rows[0], "prev") if cursor_token else None
    return PageOut(items=rows, next_cursor=next_cursor, previous_cursor=previous_cursor)
