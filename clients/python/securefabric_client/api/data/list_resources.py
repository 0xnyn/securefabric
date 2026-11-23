import datetime
from http import HTTPStatus
from typing import Any, cast

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.page_resource_out import PageResourceOut
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    name: None | str | Unset = UNSET,
    vendor: None | str | Unset = UNSET,
    state: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    updated_since: datetime.datetime | None | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    change_type: None | str | Unset = UNSET,
    connection_id: None | str | Unset = UNSET,
    sort: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
    x_connection_id: None | str | Unset = UNSET,
    x_organization_id: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_connection_id, Unset):
        headers["X-CONNECTION-ID"] = x_connection_id

    if not isinstance(x_organization_id, Unset):
        headers["X-ORGANIZATION-ID"] = x_organization_id

    params: dict[str, Any] = {}

    json_name: None | str | Unset
    if isinstance(name, Unset):
        json_name = UNSET
    else:
        json_name = name
    params["name"] = json_name

    json_vendor: None | str | Unset
    if isinstance(vendor, Unset):
        json_vendor = UNSET
    else:
        json_vendor = vendor
    params["vendor"] = json_vendor

    json_state: None | str | Unset
    if isinstance(state, Unset):
        json_state = UNSET
    else:
        json_state = state
    params["state"] = json_state

    json_type_: None | str | Unset
    if isinstance(type_, Unset):
        json_type_ = UNSET
    else:
        json_type_ = type_
    params["type"] = json_type_

    json_updated_since: None | str | Unset
    if isinstance(updated_since, Unset):
        json_updated_since = UNSET
    elif isinstance(updated_since, datetime.datetime):
        json_updated_since = updated_since.isoformat()
    else:
        json_updated_since = updated_since
    params["updatedSince"] = json_updated_since

    json_ids: None | str | Unset
    if isinstance(ids, Unset):
        json_ids = UNSET
    else:
        json_ids = ids
    params["ids"] = json_ids

    json_change_type: None | str | Unset
    if isinstance(change_type, Unset):
        json_change_type = UNSET
    else:
        json_change_type = change_type
    params["changeType"] = json_change_type

    json_connection_id: None | str | Unset
    if isinstance(connection_id, Unset):
        json_connection_id = UNSET
    else:
        json_connection_id = connection_id
    params["connectionId"] = json_connection_id

    json_sort: None | str | Unset
    if isinstance(sort, Unset):
        json_sort = UNSET
    else:
        json_sort = sort
    params["sort"] = json_sort

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
        "url": "/v1/resources",
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> Any | PageResourceOut | None:
    if response.status_code == 200:
        response_200 = PageResourceOut.from_dict(response.json())

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
) -> Response[Any | PageResourceOut]:
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
    vendor: None | str | Unset = UNSET,
    state: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    updated_since: datetime.datetime | None | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    change_type: None | str | Unset = UNSET,
    connection_id: None | str | Unset = UNSET,
    sort: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
    x_connection_id: None | str | Unset = UNSET,
    x_organization_id: None | str | Unset = UNSET,
) -> Response[Any | PageResourceOut]:
    """List Resources

    Args:
        name (None | str | Unset):
        vendor (None | str | Unset):
        state (None | str | Unset):
        type_ (None | str | Unset):
        updated_since (datetime.datetime | None | Unset):
        ids (None | str | Unset):
        change_type (None | str | Unset):
        connection_id (None | str | Unset):
        sort (None | str | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):
        x_connection_id (None | str | Unset):
        x_organization_id (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | PageResourceOut]
    """

    kwargs = _get_kwargs(
        name=name,
        vendor=vendor,
        state=state,
        type_=type_,
        updated_since=updated_since,
        ids=ids,
        change_type=change_type,
        connection_id=connection_id,
        sort=sort,
        cursor=cursor,
        limit=limit,
        x_connection_id=x_connection_id,
        x_organization_id=x_organization_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    name: None | str | Unset = UNSET,
    vendor: None | str | Unset = UNSET,
    state: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    updated_since: datetime.datetime | None | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    change_type: None | str | Unset = UNSET,
    connection_id: None | str | Unset = UNSET,
    sort: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
    x_connection_id: None | str | Unset = UNSET,
    x_organization_id: None | str | Unset = UNSET,
) -> Any | PageResourceOut | None:
    """List Resources

    Args:
        name (None | str | Unset):
        vendor (None | str | Unset):
        state (None | str | Unset):
        type_ (None | str | Unset):
        updated_since (datetime.datetime | None | Unset):
        ids (None | str | Unset):
        change_type (None | str | Unset):
        connection_id (None | str | Unset):
        sort (None | str | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):
        x_connection_id (None | str | Unset):
        x_organization_id (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | PageResourceOut
    """

    return sync_detailed(
        client=client,
        name=name,
        vendor=vendor,
        state=state,
        type_=type_,
        updated_since=updated_since,
        ids=ids,
        change_type=change_type,
        connection_id=connection_id,
        sort=sort,
        cursor=cursor,
        limit=limit,
        x_connection_id=x_connection_id,
        x_organization_id=x_organization_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    name: None | str | Unset = UNSET,
    vendor: None | str | Unset = UNSET,
    state: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    updated_since: datetime.datetime | None | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    change_type: None | str | Unset = UNSET,
    connection_id: None | str | Unset = UNSET,
    sort: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
    x_connection_id: None | str | Unset = UNSET,
    x_organization_id: None | str | Unset = UNSET,
) -> Response[Any | PageResourceOut]:
    """List Resources

    Args:
        name (None | str | Unset):
        vendor (None | str | Unset):
        state (None | str | Unset):
        type_ (None | str | Unset):
        updated_since (datetime.datetime | None | Unset):
        ids (None | str | Unset):
        change_type (None | str | Unset):
        connection_id (None | str | Unset):
        sort (None | str | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):
        x_connection_id (None | str | Unset):
        x_organization_id (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | PageResourceOut]
    """

    kwargs = _get_kwargs(
        name=name,
        vendor=vendor,
        state=state,
        type_=type_,
        updated_since=updated_since,
        ids=ids,
        change_type=change_type,
        connection_id=connection_id,
        sort=sort,
        cursor=cursor,
        limit=limit,
        x_connection_id=x_connection_id,
        x_organization_id=x_organization_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    name: None | str | Unset = UNSET,
    vendor: None | str | Unset = UNSET,
    state: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    updated_since: datetime.datetime | None | Unset = UNSET,
    ids: None | str | Unset = UNSET,
    change_type: None | str | Unset = UNSET,
    connection_id: None | str | Unset = UNSET,
    sort: None | str | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
    x_connection_id: None | str | Unset = UNSET,
    x_organization_id: None | str | Unset = UNSET,
) -> Any | PageResourceOut | None:
    """List Resources

    Args:
        name (None | str | Unset):
        vendor (None | str | Unset):
        state (None | str | Unset):
        type_ (None | str | Unset):
        updated_since (datetime.datetime | None | Unset):
        ids (None | str | Unset):
        change_type (None | str | Unset):
        connection_id (None | str | Unset):
        sort (None | str | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):
        x_connection_id (None | str | Unset):
        x_organization_id (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | PageResourceOut
    """

    return (
        await asyncio_detailed(
            client=client,
            name=name,
            vendor=vendor,
            state=state,
            type_=type_,
            updated_since=updated_since,
            ids=ids,
            change_type=change_type,
            connection_id=connection_id,
            sort=sort,
            cursor=cursor,
            limit=limit,
            x_connection_id=x_connection_id,
            x_organization_id=x_organization_id,
        )
    ).parsed
