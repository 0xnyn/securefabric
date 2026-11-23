import datetime
from http import HTTPStatus
from typing import Any, cast
from uuid import UUID

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.page_operation_out import PageOperationOut
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    job_id: None | Unset | UUID = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_kind: None | str | Unset
    if isinstance(kind, Unset):
        json_kind = UNSET
    else:
        json_kind = kind
    params["kind"] = json_kind

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    json_connection_id: None | str | Unset
    if isinstance(connection_id, Unset):
        json_connection_id = UNSET
    elif isinstance(connection_id, UUID):
        json_connection_id = str(connection_id)
    else:
        json_connection_id = connection_id
    params["connectionId"] = json_connection_id

    json_job_id: None | str | Unset
    if isinstance(job_id, Unset):
        json_job_id = UNSET
    elif isinstance(job_id, UUID):
        json_job_id = str(job_id)
    else:
        json_job_id = job_id
    params["jobId"] = json_job_id

    json_since: None | str | Unset
    if isinstance(since, Unset):
        json_since = UNSET
    elif isinstance(since, datetime.datetime):
        json_since = since.isoformat()
    else:
        json_since = since
    params["since"] = json_since

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
        "url": "/v1/operations",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx2.Response
) -> Any | PageOperationOut | None:
    if response.status_code == 200:
        response_200 = PageOperationOut.from_dict(response.json())

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
) -> Response[Any | PageOperationOut]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    job_id: None | Unset | UUID = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> Response[Any | PageOperationOut]:
    """List Operations

    Args:
        kind (None | str | Unset):
        status (None | str | Unset):
        connection_id (None | Unset | UUID):
        job_id (None | Unset | UUID):
        since (datetime.datetime | None | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | PageOperationOut]
    """

    kwargs = _get_kwargs(
        kind=kind,
        status=status,
        connection_id=connection_id,
        job_id=job_id,
        since=since,
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
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    job_id: None | Unset | UUID = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> Any | PageOperationOut | None:
    """List Operations

    Args:
        kind (None | str | Unset):
        status (None | str | Unset):
        connection_id (None | Unset | UUID):
        job_id (None | Unset | UUID):
        since (datetime.datetime | None | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | PageOperationOut
    """

    return sync_detailed(
        client=client,
        kind=kind,
        status=status,
        connection_id=connection_id,
        job_id=job_id,
        since=since,
        cursor=cursor,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    job_id: None | Unset | UUID = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> Response[Any | PageOperationOut]:
    """List Operations

    Args:
        kind (None | str | Unset):
        status (None | str | Unset):
        connection_id (None | Unset | UUID):
        job_id (None | Unset | UUID):
        since (datetime.datetime | None | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | PageOperationOut]
    """

    kwargs = _get_kwargs(
        kind=kind,
        status=status,
        connection_id=connection_id,
        job_id=job_id,
        since=since,
        cursor=cursor,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    job_id: None | Unset | UUID = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    cursor: None | str | Unset = UNSET,
    limit: int | None | Unset = UNSET,
) -> Any | PageOperationOut | None:
    """List Operations

    Args:
        kind (None | str | Unset):
        status (None | str | Unset):
        connection_id (None | Unset | UUID):
        job_id (None | Unset | UUID):
        since (datetime.datetime | None | Unset):
        cursor (None | str | Unset):
        limit (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | PageOperationOut
    """

    return (
        await asyncio_detailed(
            client=client,
            kind=kind,
            status=status,
            connection_id=connection_id,
            job_id=job_id,
            since=since,
            cursor=cursor,
            limit=limit,
        )
    ).parsed
