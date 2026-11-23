from http import HTTPStatus
from typing import Any, cast

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.page_organization_out import PageOrganizationOut
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    name: None | str | Unset = UNSET,
    identifier: None | str | Unset = UNSET,
    id: None | str | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    search: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_name: None | str | Unset
    if isinstance(name, Unset):
        json_name = UNSET
    else:
        json_name = name
    params["name"] = json_name

    json_identifier: None | str | Unset
    if isinstance(identifier, Unset):
        json_identifier = UNSET
    else:
        json_identifier = identifier
    params["identifier"] = json_identifier

    json_id: None | str | Unset
    if isinstance(id, Unset):
        json_id = UNSET
    else:
        json_id = id
    params["id"] = json_id

    json_ids: None | str | Unset
    if isinstance(ids, Unset):
        json_ids = UNSET
    else:
        json_ids = ids
    params["ids"] = json_ids

    json_search: None | str | Unset
    if isinstance(search, Unset):
        json_search = UNSET
    else:
        json_search = search
    params["search"] = json_search

    json_cursor: None | str | Unset
    if isinstance(cursor, Unset):
        json_cursor = UNSET
    else:
        json_cursor = cursor
    params["cursor"] = json_cursor

    json_limit: int | None | Unset
    if isinstance(limit, Unset):
        json_limit = UNSET
    else:
        json_limit = limit
    params["limit"] = json_limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/organizations",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx2.Response
) -> Any | PageOrganizationOut | None:
    if response.status_code == 200:
        response_200 = PageOrganizationOut.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = cast(Any, None)
        return response_400

    if response.status_code == 401:
        response_401 = cast(Any, None)
        return response_401

    if response.status_code == 403:
        response_403 = cast(Any, None)
        return response_403

    if response.status_code == 404:
        response_404 = cast(Any, None)
        return response_404

    if response.status_code == 409:
        response_409 = cast(Any, None)
        return response_409

    if response.status_code == 410:
        response_410 = cast(Any, None)
        return response_410

    if response.status_code == 422:
        response_422 = cast(Any, None)
        return response_422

    if response.status_code == 429:
        response_429 = cast(Any, None)
        return response_429

    if response.status_code == 500:
        response_500 = cast(Any, None)
        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx2.Response
) -> Response[Any | PageOrganizationOut]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    name: None | str | Unset = UNSET,
    identifier: None | str | Unset = UNSET,
    id: None | str | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    search: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> Response[Any | PageOrganizationOut]:
    """List Organizations

    Args:
        name (None | str | Unset):
        identifier (None | str | Unset):
        id (None | str | Unset):
        ids (None | str | Unset):
        search (None | str | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | PageOrganizationOut]
    """

    kwargs = _get_kwargs(
        name=name,
        identifier=identifier,
        id=id,
        ids=ids,
        search=search,
        cursor=cursor,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    name: None | str | Unset = UNSET,
    identifier: None | str | Unset = UNSET,
    id: None | str | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    search: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> Any | PageOrganizationOut | None:
    """List Organizations

    Args:
        name (None | str | Unset):
        identifier (None | str | Unset):
        id (None | str | Unset):
        ids (None | str | Unset):
        search (None | str | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | PageOrganizationOut
    """

    return sync_detailed(
        client=client,
        name=name,
        identifier=identifier,
        id=id,
        ids=ids,
        search=search,
        cursor=cursor,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    name: None | str | Unset = UNSET,
    identifier: None | str | Unset = UNSET,
    id: None | str | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    search: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> Response[Any | PageOrganizationOut]:
    """List Organizations

    Args:
        name (None | str | Unset):
        identifier (None | str | Unset):
        id (None | str | Unset):
        ids (None | str | Unset):
        search (None | str | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | PageOrganizationOut]
    """

    kwargs = _get_kwargs(
        name=name,
        identifier=identifier,
        id=id,
        ids=ids,
        search=search,
        cursor=cursor,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    name: None | str | Unset = UNSET,
    identifier: None | str | Unset = UNSET,
    id: None | str | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    search: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> Any | PageOrganizationOut | None:
    """List Organizations

    Args:
        name (None | str | Unset):
        identifier (None | str | Unset):
        id (None | str | Unset):
        ids (None | str | Unset):
        search (None | str | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | PageOrganizationOut
    """

    return (
        await asyncio_detailed(
            client=client,
            name=name,
            identifier=identifier,
            id=id,
            ids=ids,
            search=search,
            cursor=cursor,
            limit=limit,
        )
    ).parsed
