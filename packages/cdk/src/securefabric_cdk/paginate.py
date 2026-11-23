"""Pagination helpers (RATE-09).

Each helper yields ``(items, response, resume)`` where ``resume`` is an opaque,
JSON-serialisable token that restarts the listing *after* this page. Streams
store it in their checkpoint, so a resumed slice continues where it stopped.
"""

import re
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx2

from securefabric_cdk.http import HttpClient

_LINK = re.compile(r'<([^>]+)>\s*;\s*rel="?([^";]+)"?')


def parse_link_header(value: str | None) -> dict[str, str]:
    links: dict[str, str] = {}
    if not value:
        return links
    for part in value.split(","):
        m = _LINK.search(part)
        if m:
            for rel in m.group(2).split():
                links[rel] = m.group(1)
    return links


@dataclass(frozen=True, slots=True)
class PageResult:
    items: list[Any]
    response: httpx2.Response
    resume: Any  # None when the listing is exhausted


def _items(body: Any, items_key: str | None) -> list[Any]:
    if items_key is None:
        return list(body or [])
    return list((body or {}).get(items_key) or [])


async def link_header_pages(
    http: HttpClient,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    resume_url: str | None = None,
    items_key: str | None = None,
    allow: tuple[int, ...] = (),
) -> AsyncIterator[PageResult]:
    """``Link: <...>; rel="next"`` pagination (GitHub). Resume token: the next URL."""
    url: str | None = resume_url or http.url(path)
    first = resume_url is None
    while url:
        resp = await http.request("GET", url, params=params if first else None, allow=allow)
        first = False
        if resp.status_code in allow:
            yield PageResult([], resp, None)
            return
        nxt = parse_link_header(resp.headers.get("link")).get("next")
        yield PageResult(_items(resp.json(), items_key), resp, nxt)
        url = nxt


async def cursor_pages(
    http: HttpClient,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    cursor: str | None = None,
    cursor_param: str = "cursor",
    next_cursor: Callable[[Any], str | None] = lambda b: (b or {}).get("next_cursor"),
    items_key: str | None = "items",
) -> AsyncIterator[PageResult]:
    """Body-cursor pagination. Resume token: the next cursor."""
    while True:
        q = dict(params or {})
        if cursor:
            q[cursor_param] = cursor
        resp = await http.request("GET", path, params=q)
        body = resp.json()
        cursor = next_cursor(body)
        yield PageResult(_items(body, items_key), resp, cursor)
        if not cursor:
            return


async def page_token_pages(
    http: HttpClient,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    page_token: str | None = None,
    token_param: str = "pageToken",  # noqa: S107
    next_token_key: str = "nextPageToken",  # noqa: S107
    items_key: str | None = "items",
) -> AsyncIterator[PageResult]:
    """Google-style ``pageToken`` / ``nextPageToken``."""
    async for page in cursor_pages(
        http,
        path,
        params=params,
        cursor=page_token,
        cursor_param=token_param,
        next_cursor=lambda b: (b or {}).get(next_token_key),
        items_key=items_key,
    ):
        yield page


async def offset_pages(
    http: HttpClient,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    offset: int = 0,
    limit: int = 100,
    offset_param: str = "offset",
    limit_param: str = "limit",
    items_key: str | None = "items",
    total_key: str | None = "total",
) -> AsyncIterator[PageResult]:
    """Offset/limit pagination. Resume token: the next offset (int)."""
    while True:
        q = {**dict(params or {}), offset_param: offset, limit_param: limit}
        resp = await http.request("GET", path, params=q)
        body = resp.json()
        items = _items(body, items_key)
        offset += len(items)
        total = (body or {}).get(total_key) if total_key and isinstance(body, dict) else None
        done = len(items) < limit or (total is not None and offset >= int(total))
        yield PageResult(items, resp, None if done else offset)
        if done:
            return
