from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote
from uuid import UUID

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.admin_repair_action import AdminRepairAction
from ...models.admin_repair_response_admin_admin_repair import AdminRepairResponseAdminAdminRepair
from ...models.repair_in import RepairIn
from ...types import Response


def _get_kwargs(
    environment_id: UUID,
    connection_id: UUID,
    action: AdminRepairAction,
    *,
    body: RepairIn,
    x_support_reason: str,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["X-Support-Reason"] = x_support_reason

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/admin/environments/{environment_id}/connections/{connection_id}/{action}".format(
            environment_id=quote(str(environment_id), safe=""),
            connection_id=quote(str(connection_id), safe=""),
            action=quote(str(action), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx2.Response
) -> AdminRepairResponseAdminAdminRepair | Any | None:
    if response.status_code == 200:
        response_200 = AdminRepairResponseAdminAdminRepair.from_dict(response.json())

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
) -> Response[AdminRepairResponseAdminAdminRepair | Any]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    environment_id: UUID,
    connection_id: UUID,
    action: AdminRepairAction,
    *,
    client: AuthenticatedClient | Client,
    body: RepairIn,
    x_support_reason: str,
) -> Response[AdminRepairResponseAdminAdminRepair | Any]:
    """Operators: trigger, pause, resume, reset, renormalize, purge_now, rebuild_counts, reprobe

    Args:
        environment_id (UUID):
        connection_id (UUID):
        action (AdminRepairAction):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)
        body (RepairIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminRepairResponseAdminAdminRepair | Any]
    """

    kwargs = _get_kwargs(
        environment_id=environment_id,
        connection_id=connection_id,
        action=action,
        body=body,
        x_support_reason=x_support_reason,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    environment_id: UUID,
    connection_id: UUID,
    action: AdminRepairAction,
    *,
    client: AuthenticatedClient | Client,
    body: RepairIn,
    x_support_reason: str,
) -> AdminRepairResponseAdminAdminRepair | Any | None:
    """Operators: trigger, pause, resume, reset, renormalize, purge_now, rebuild_counts, reprobe

    Args:
        environment_id (UUID):
        connection_id (UUID):
        action (AdminRepairAction):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)
        body (RepairIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminRepairResponseAdminAdminRepair | Any
    """

    return sync_detailed(
        environment_id=environment_id,
        connection_id=connection_id,
        action=action,
        client=client,
        body=body,
        x_support_reason=x_support_reason,
    ).parsed


async def asyncio_detailed(
    environment_id: UUID,
    connection_id: UUID,
    action: AdminRepairAction,
    *,
    client: AuthenticatedClient | Client,
    body: RepairIn,
    x_support_reason: str,
) -> Response[AdminRepairResponseAdminAdminRepair | Any]:
    """Operators: trigger, pause, resume, reset, renormalize, purge_now, rebuild_counts, reprobe

    Args:
        environment_id (UUID):
        connection_id (UUID):
        action (AdminRepairAction):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)
        body (RepairIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminRepairResponseAdminAdminRepair | Any]
    """

    kwargs = _get_kwargs(
        environment_id=environment_id,
        connection_id=connection_id,
        action=action,
        body=body,
        x_support_reason=x_support_reason,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    environment_id: UUID,
    connection_id: UUID,
    action: AdminRepairAction,
    *,
    client: AuthenticatedClient | Client,
    body: RepairIn,
    x_support_reason: str,
) -> AdminRepairResponseAdminAdminRepair | Any | None:
    """Operators: trigger, pause, resume, reset, renormalize, purge_now, rebuild_counts, reprobe

    Args:
        environment_id (UUID):
        connection_id (UUID):
        action (AdminRepairAction):
        x_support_reason (str): Why an operator is acting in this customer's environment (audited)
        body (RepairIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminRepairResponseAdminAdminRepair | Any
    """

    return (
        await asyncio_detailed(
            environment_id=environment_id,
            connection_id=connection_id,
            action=action,
            client=client,
            body=body,
            x_support_reason=x_support_reason,
        )
    ).parsed
