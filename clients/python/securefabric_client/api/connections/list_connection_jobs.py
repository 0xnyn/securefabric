import datetime
from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote
from uuid import UUID

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.job_out import JobOut
from ...types import UNSET, Response, Unset


def _get_kwargs(
    connection_id: UUID,
    *,
    status: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    started_at_since: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    json_type_: None | str | Unset
    if isinstance(type_, Unset):
        json_type_ = UNSET
    else:
        json_type_ = type_
    params["type"] = json_type_

    json_started_at_since: None | str | Unset
    if isinstance(started_at_since, Unset):
        json_started_at_since = UNSET
    elif isinstance(started_at_since, datetime.datetime):
        json_started_at_since = started_at_since.isoformat()
    else:
        json_started_at_since = started_at_since
    params["startedAtSince"] = json_started_at_since

    params["limit"] = limit

    json_cursor: None | str | Unset
    if isinstance(cursor, Unset):
        json_cursor = UNSET
    else:
        json_cursor = cursor
    params["cursor"] = json_cursor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/connections/{connection_id}/jobs".format(
            connection_id=quote(str(connection_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> Any | list[JobOut] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = JobOut.from_dict(response_200_item_data)

            response_200.append(response_200_item)

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


def _build_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> Response[Any | list[JobOut]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    status: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    started_at_since: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: None | str | Unset = UNSET,
) -> Response[Any | list[JobOut]]:
    """List Connection Jobs

    Args:
        connection_id (UUID):
        status (None | str | Unset):
        type_ (None | str | Unset):
        started_at_since (datetime.datetime | None | Unset):
        limit (int | Unset):  Default: 50.
        cursor (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | list[JobOut]]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        status=status,
        type_=type_,
        started_at_since=started_at_since,
        limit=limit,
        cursor=cursor,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    status: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    started_at_since: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: None | str | Unset = UNSET,
) -> Any | list[JobOut] | None:
    """List Connection Jobs

    Args:
        connection_id (UUID):
        status (None | str | Unset):
        type_ (None | str | Unset):
        started_at_since (datetime.datetime | None | Unset):
        limit (int | Unset):  Default: 50.
        cursor (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | list[JobOut]
    """

    return sync_detailed(
        connection_id=connection_id,
        client=client,
        status=status,
        type_=type_,
        started_at_since=started_at_since,
        limit=limit,
        cursor=cursor,
    ).parsed


async def asyncio_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    status: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    started_at_since: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: None | str | Unset = UNSET,
) -> Response[Any | list[JobOut]]:
    """List Connection Jobs

    Args:
        connection_id (UUID):
        status (None | str | Unset):
        type_ (None | str | Unset):
        started_at_since (datetime.datetime | None | Unset):
        limit (int | Unset):  Default: 50.
        cursor (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | list[JobOut]]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        status=status,
        type_=type_,
        started_at_since=started_at_since,
        limit=limit,
        cursor=cursor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    status: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    started_at_since: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: None | str | Unset = UNSET,
) -> Any | list[JobOut] | None:
    """List Connection Jobs

    Args:
        connection_id (UUID):
        status (None | str | Unset):
        type_ (None | str | Unset):
        started_at_since (datetime.datetime | None | Unset):
        limit (int | Unset):  Default: 50.
        cursor (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | list[JobOut]
    """

    return (
        await asyncio_detailed(
            connection_id=connection_id,
            client=client,
            status=status,
            type_=type_,
            started_at_since=started_at_since,
            limit=limit,
            cursor=cursor,
        )
    ).parsed
