from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote
from uuid import UUID

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.admin_raw_page_response_admin_admin_raw_page import AdminRawPageResponseAdminAdminRawPage
from ...types import Response


def _get_kwargs(
    environment_id: UUID,
    raw_page_id: UUID,
    *,
    x_support_reason: str,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["X-Support-Reason"] = x_support_reason

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/admin/environments/{environment_id}/raw_pages/{raw_page_id}".format(
            environment_id=quote(str(environment_id), safe=""),
            raw_page_id=quote(str(raw_page_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx2.Response
) -> AdminRawPageResponseAdminAdminRawPage | Any | None:
    if response.status_code == 200:
        response_200 = AdminRawPageResponseAdminAdminRawPage.from_dict(response.json())

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
) -> Response[AdminRawPageResponseAdminAdminRawPage | Any]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    environment_id: UUID,
    raw_page_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    x_support_reason: str,
) -> Response[AdminRawPageResponseAdminAdminRawPage | Any]:
    """Operators: one archived raw page, opened in the control worker (audited)

    Args:
        environment_id (UUID):
        raw_page_id (UUID):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminRawPageResponseAdminAdminRawPage | Any]
    """

    kwargs = _get_kwargs(
        environment_id=environment_id,
        raw_page_id=raw_page_id,
        x_support_reason=x_support_reason,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    environment_id: UUID,
    raw_page_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    x_support_reason: str,
) -> AdminRawPageResponseAdminAdminRawPage | Any | None:
    """Operators: one archived raw page, opened in the control worker (audited)

    Args:
        environment_id (UUID):
        raw_page_id (UUID):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminRawPageResponseAdminAdminRawPage | Any
    """

    return sync_detailed(
        environment_id=environment_id,
        raw_page_id=raw_page_id,
        client=client,
        x_support_reason=x_support_reason,
    ).parsed


async def asyncio_detailed(
    environment_id: UUID,
    raw_page_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    x_support_reason: str,
) -> Response[AdminRawPageResponseAdminAdminRawPage | Any]:
    """Operators: one archived raw page, opened in the control worker (audited)

    Args:
        environment_id (UUID):
        raw_page_id (UUID):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminRawPageResponseAdminAdminRawPage | Any]
    """

    kwargs = _get_kwargs(
        environment_id=environment_id,
        raw_page_id=raw_page_id,
        x_support_reason=x_support_reason,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    environment_id: UUID,
    raw_page_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    x_support_reason: str,
) -> AdminRawPageResponseAdminAdminRawPage | Any | None:
    """Operators: one archived raw page, opened in the control worker (audited)

    Args:
        environment_id (UUID):
        raw_page_id (UUID):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminRawPageResponseAdminAdminRawPage | Any
    """

    return (
        await asyncio_detailed(
            environment_id=environment_id,
            raw_page_id=raw_page_id,
            client=client,
            x_support_reason=x_support_reason,
        )
    ).parsed
