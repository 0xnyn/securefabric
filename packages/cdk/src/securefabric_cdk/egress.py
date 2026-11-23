"""Egress policy (RATE-07, HOOK-08, AUTH-12).

Every outbound call resolves the host itself, rejects any address that is not
globally routable (private, loopback, link-local, metadata, CGNAT, multicast,
reserved), and connects to the checked address with the original name for TLS
(SNI and certificate verification), so DNS rebinding between check and connect
is impossible. Redirects pass through the transport again and are re-checked.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx2

from securefabric_cdk.errors import EgressDenied

_METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata", "instance-data"})


def _is_allowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def resolve_checked(host: str, port: int, *, allow_private: bool = False) -> list[str]:
    """Resolve ``host`` and return its addresses, or raise :class:`EgressDenied`."""
    if host.lower().rstrip(".") in _METADATA_HOSTS:
        raise EgressDenied(f"{host} is a metadata endpoint")
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        addrs = [str(literal)]
    else:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise httpx2.ConnectError(f"DNS resolution failed for {host}") from exc
        addrs = list(dict.fromkeys(str(info[4][0]) for info in infos))
    if not allow_private:
        for addr in addrs:
            if not _is_allowed_ip(ipaddress.ip_address(addr)):
                raise EgressDenied(f"{host} resolves to a non-public address", host=host)
    return addrs


async def check_url(url: str, *, allow_private: bool = False, require_https: bool = False) -> None:
    """Validate a customer-supplied URL (GHES base URL, webhook endpoint)."""
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise EgressDenied("URL must be absolute http(s)")
    if require_https and parts.scheme != "https":
        raise EgressDenied("URL must use https")
    if parts.username or parts.password:
        raise EgressDenied("URL must not carry credentials")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    await resolve_checked(parts.hostname, port, allow_private=allow_private)


class EgressTransport(httpx2.AsyncBaseTransport):
    """Wraps a real transport: resolve, check, pin, connect."""

    def __init__(
        self, inner: httpx2.AsyncBaseTransport | None = None, *, allow_private: bool = False
    ) -> None:
        self._inner = inner or httpx2.AsyncHTTPTransport()
        self._allow_private = allow_private

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        addrs = await resolve_checked(host, port, allow_private=self._allow_private)
        try:
            ipaddress.ip_address(host.strip("[]"))
            is_literal = True
        except ValueError:
            is_literal = False
        if not is_literal:
            pinned = addrs[0]
            pinned_host = f"[{pinned}]" if ":" in pinned else pinned
            request.url = request.url.copy_with(host=pinned_host.strip("[]"))
            request.headers["host"] = host if request.url.port is None else f"{host}:{port}"
            request.extensions = {**request.extensions, "sni_hostname": host}
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()
