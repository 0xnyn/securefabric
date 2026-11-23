from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote
from uuid import UUID

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.admin_raw_pages_response_200_item import AdminRawPagesResponse200Item
from ...types import UNSET, Response, Unset


def _get_kwargs(
    environment_id: UUID,
    *,
    connection_id: None | Unset | UUID = UNSET,
    run_id: None | Unset | UUID = UNSET,
    x_support_reason: str,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["X-Support-Reason"] = x_support_reason

    params: dict[str, Any] = {}

    json_connection_id: None | str | Unset
    if isinstance(connection_id, Unset):
        json_connection_id = UNSET
    elif isinstance(connection_id, UUID):
        json_connection_id = str(connection_id)
    else:
        json_connection_id = connection_id
    params["connectionId"] = json_connection_id

    json_run_id: None | str | Unset
    if isinstance(run_id, Unset):
        json_run_id = UNSET
    elif isinstance(run_id, UUID):
        json_run_id = str(run_id)
    else:
        json_run_id = run_id
    params["runId"] = json_run_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/admin/environments/{environment_id}/raw_pages".format(
            environment_id=quote(str(environment_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx2.Response
) -> Any | list[AdminRawPagesResponse200Item] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = AdminRawPagesResponse200Item.from_dict(response_200_item_data)

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


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx2.Response
) -> Response[Any | list[AdminRawPagesResponse200Item]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    environment_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    connection_id: None | Unset | UUID = UNSET,
    run_id: None | Unset | UUID = UNSET,
    x_support_reason: str,
) -> Response[Any | list[AdminRawPagesResponse200Item]]:
    """Operators: archived raw vendor pages of a connection or run (audited)

    Args:
        environment_id (UUID):
        connection_id (None | Unset | UUID):
        run_id (None | Unset | UUID):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | list[AdminRawPagesResponse200Item]]
    """

    kwargs = _get_kwargs(
        environment_id=environment_id,
        connection_id=connection_id,
        run_id=run_id,
        x_support_reason=x_support_reason,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    environment_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    connection_id: None | Unset | UUID = UNSET,
    run_id: None | Unset | UUID = UNSET,
    x_support_reason: str,
) -> Any | list[AdminRawPagesResponse200Item] | None:
    """Operators: archived raw vendor pages of a connection or run (audited)

    Args:
        environment_id (UUID):
        connection_id (None | Unset | UUID):
        run_id (None | Unset | UUID):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | list[AdminRawPagesResponse200Item]
    """

    return sync_detailed(
        environment_id=environment_id,
        client=client,
        connection_id=connection_id,
        run_id=run_id,
        x_support_reason=x_support_reason,
    ).parsed


async def asyncio_detailed(
    environment_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    connection_id: None | Unset | UUID = UNSET,
    run_id: None | Unset | UUID = UNSET,
    x_support_reason: str,
) -> Response[Any | list[AdminRawPagesResponse200Item]]:
    """Operators: archived raw vendor pages of a connection or run (audited)

    Args:
        environment_id (UUID):
        connection_id (None | Unset | UUID):
        run_id (None | Unset | UUID):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | list[AdminRawPagesResponse200Item]]
    """

    kwargs = _get_kwargs(
        environment_id=environment_id,
        connection_id=connection_id,
        run_id=run_id,
        x_support_reason=x_support_reason,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    environment_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    connection_id: None | Unset | UUID = UNSET,
    run_id: None | Unset | UUID = UNSET,
    x_support_reason: str,
) -> Any | list[AdminRawPagesResponse200Item] | None:
    """Operators: archived raw vendor pages of a connection or run (audited)

    Args:
        environment_id (UUID):
        connection_id (None | Unset | UUID):
        run_id (None | Unset | UUID):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | list[AdminRawPagesResponse200Item]
    """

    return (
        await asyncio_detailed(
            environment_id=environment_id,
            client=client,
            connection_id=connection_id,
            run_id=run_id,
            x_support_reason=x_support_reason,
        )
    ).parsed
