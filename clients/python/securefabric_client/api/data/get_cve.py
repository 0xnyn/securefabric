from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx2

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.get_cve_response_data_get_cve import GetCveResponseDataGetCve
from ...types import Response


def _get_kwargs(
    cve_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/enrichments/cves/{cve_id}".format(
            cve_id=quote(str(cve_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx2.Response
) -> Any | GetCveResponseDataGetCve | None:
    if response.status_code == 200:
        response_200 = GetCveResponseDataGetCve.from_dict(response.json())

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
) -> Response[Any | GetCveResponseDataGetCve]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    cve_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Any | GetCveResponseDataGetCve]:
    """CVE mirror lookup: NVD, KEV, EPSS, aliases (ENR-04)

    Args:
        cve_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | GetCveResponseDataGetCve]
    """

    kwargs = _get_kwargs(
        cve_id=cve_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    cve_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Any | GetCveResponseDataGetCve | None:
    """CVE mirror lookup: NVD, KEV, EPSS, aliases (ENR-04)

    Args:
        cve_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | GetCveResponseDataGetCve
    """

    return sync_detailed(
        cve_id=cve_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    cve_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Any | GetCveResponseDataGetCve]:
    """CVE mirror lookup: NVD, KEV, EPSS, aliases (ENR-04)

    Args:
        cve_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | GetCveResponseDataGetCve]
    """

    kwargs = _get_kwargs(
        cve_id=cve_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    cve_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Any | GetCveResponseDataGetCve | None:
    """CVE mirror lookup: NVD, KEV, EPSS, aliases (ENR-04)

    Args:
        cve_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx2.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | GetCveResponseDataGetCve
    """

    return (
        await asyncio_detailed(
            cve_id=cve_id,
            client=client,
        )
    ).parsed
