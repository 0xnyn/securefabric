from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote
from uuid import UUID

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.action_out import ActionOut
from ...types import UNSET, Response, Unset


def _get_kwargs(
    action_id: UUID,
    *,
    prefer: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(prefer, Unset):
        headers["prefer"] = prefer

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/actions/{action_id}".format(
            action_id=quote(str(action_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> ActionOut | Any | None:
    if response.status_code == 200:
        response_200 = ActionOut.from_dict(response.json())

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


def _build_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> Response[ActionOut | Any]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    action_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    prefer: None | str | Unset = UNSET,
) -> Response[ActionOut | Any]:
    """Get Action

    Args:
        action_id (UUID):
        prefer (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ActionOut | Any]
    """

    kwargs = _get_kwargs(
        action_id=action_id,
        prefer=prefer,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    action_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    prefer: None | str | Unset = UNSET,
) -> ActionOut | Any | None:
    """Get Action

    Args:
        action_id (UUID):
        prefer (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ActionOut | Any
    """

    return sync_detailed(
        action_id=action_id,
        client=client,
        prefer=prefer,
    ).parsed


async def asyncio_detailed(
    action_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    prefer: None | str | Unset = UNSET,
) -> Response[ActionOut | Any]:
    """Get Action

    Args:
        action_id (UUID):
        prefer (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ActionOut | Any]
    """

    kwargs = _get_kwargs(
        action_id=action_id,
        prefer=prefer,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    action_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    prefer: None | str | Unset = UNSET,
) -> ActionOut | Any | None:
    """Get Action

    Args:
        action_id (UUID):
        prefer (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ActionOut | Any
    """

    return (
        await asyncio_detailed(
            action_id=action_id,
            client=client,
            prefer=prefer,
        )
    ).parsed
