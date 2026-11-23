from http import HTTPStatus
from typing import Any, cast
from uuid import UUID

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.events_page import EventsPage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    after: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    limit: int | Unset = 100,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_after: None | str | Unset
    if isinstance(after, Unset):
        json_after = UNSET
    else:
        json_after = after
    params["after"] = json_after

    json_type_: None | str | Unset
    if isinstance(type_, Unset):
        json_type_ = UNSET
    else:
        json_type_ = type_
    params["type"] = json_type_

    json_connection_id: None | str | Unset
    if isinstance(connection_id, Unset):
        json_connection_id = UNSET
    elif isinstance(connection_id, UUID):
        json_connection_id = str(connection_id)
    else:
        json_connection_id = connection_id
    params["connectionId"] = json_connection_id

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/events",
        "params": params,
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> Any | EventsPage | None:
    if response.status_code == 200:
        response_200 = EventsPage.from_dict(response.json())

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


def _build_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> Response[Any | EventsPage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    after: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    limit: int | Unset = 100,
) -> Response[Any | EventsPage]:
    """The outbox as a pull feed, in id order

    Args:
        after (None | str | Unset):
        type_ (None | str | Unset):
        connection_id (None | Unset | UUID):
        limit (int | Unset):  Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | EventsPage]
    """

    kwargs = _get_kwargs(
        after=after,
        type_=type_,
        connection_id=connection_id,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    after: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    limit: int | Unset = 100,
) -> Any | EventsPage | None:
    """The outbox as a pull feed, in id order

    Args:
        after (None | str | Unset):
        type_ (None | str | Unset):
        connection_id (None | Unset | UUID):
        limit (int | Unset):  Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | EventsPage
    """

    return sync_detailed(
        client=client,
        after=after,
        type_=type_,
        connection_id=connection_id,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    after: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    limit: int | Unset = 100,
) -> Response[Any | EventsPage]:
    """The outbox as a pull feed, in id order

    Args:
        after (None | str | Unset):
        type_ (None | str | Unset):
        connection_id (None | Unset | UUID):
        limit (int | Unset):  Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | EventsPage]
    """

    kwargs = _get_kwargs(
        after=after,
        type_=type_,
        connection_id=connection_id,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    after: None | str | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    connection_id: None | Unset | UUID = UNSET,
    limit: int | Unset = 100,
) -> Any | EventsPage | None:
    """The outbox as a pull feed, in id order

    Args:
        after (None | str | Unset):
        type_ (None | str | Unset):
        connection_id (None | Unset | UUID):
        limit (int | Unset):  Default: 100.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | EventsPage
    """

    return (
        await asyncio_detailed(
            client=client,
            after=after,
            type_=type_,
            connection_id=connection_id,
            limit=limit,
        )
    ).parsed
