from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote
from uuid import UUID

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.test_result import TestResult
from ...types import UNSET, Response, Unset


def _get_kwargs(
    connection_id: UUID,
    *,
    wait: float | Unset = 30.0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["wait"] = wait

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/connections/{connection_id}/test".format(
            connection_id=quote(str(connection_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> Any | TestResult | None:
    if response.status_code == 200:
        response_200 = TestResult.from_dict(response.json())

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


def _build_response(*, client: AuthenticatedClient | Client, response: httpx2.Response) -> Response[Any | TestResult]:
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
    wait: float | Unset = 30.0,
) -> Response[Any | TestResult]:
    """Verify the credentials now (waits up to 30 s; a rejection is is_valid=false)

    Args:
        connection_id (UUID):
        wait (float | Unset):  Default: 30.0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | TestResult]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        wait=wait,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    wait: float | Unset = 30.0,
) -> Any | TestResult | None:
    """Verify the credentials now (waits up to 30 s; a rejection is is_valid=false)

    Args:
        connection_id (UUID):
        wait (float | Unset):  Default: 30.0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | TestResult
    """

    return sync_detailed(
        connection_id=connection_id,
        client=client,
        wait=wait,
    ).parsed


async def asyncio_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    wait: float | Unset = 30.0,
) -> Response[Any | TestResult]:
    """Verify the credentials now (waits up to 30 s; a rejection is is_valid=false)

    Args:
        connection_id (UUID):
        wait (float | Unset):  Default: 30.0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | TestResult]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        wait=wait,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    wait: float | Unset = 30.0,
) -> Any | TestResult | None:
    """Verify the credentials now (waits up to 30 s; a rejection is is_valid=false)

    Args:
        connection_id (UUID):
        wait (float | Unset):  Default: 30.0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | TestResult
    """

    return (
        await asyncio_detailed(
            connection_id=connection_id,
            client=client,
            wait=wait,
        )
    ).parsed
