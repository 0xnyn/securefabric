"""The closed error taxonomy (docs/plan/05-connector-sdk.md, section 3).

The HTTP client raises most of these from the manifest's retry policy; connectors
raise the rest where only they can tell (GitHub's "Advanced Security must be
enabled" versus a real permission error). The engine maps each to a run outcome
and health code (part 4, section 5).
"""

from datetime import datetime

from securefabric_schema import HealthCode


class ConnectorError(Exception):
    """Base class. ``health_code`` is what a run that ends with it reports."""

    health_code: HealthCode = HealthCode.INTERNAL_ERROR
    retryable: bool = False

    def __init__(self, message: str = "", **detail: object) -> None:
        super().__init__(message or type(self).__name__)
        self.message = message or type(self).__name__
        self.detail = detail


class AuthRejected(ConnectorError):
    """The vendor rejected the credential (401, revoked, uninstalled)."""

    health_code = HealthCode.UNAUTHORIZED


class ReauthorizationRequired(ConnectorError):
    """Token refresh is exhausted; a human must re-authorize."""

    health_code = HealthCode.REAUTHORIZATION_REQUIRED


class PermissionMissing(ConnectorError):
    """The credential works but lacks the permission a stream needs."""

    health_code = HealthCode.UNAUTHORIZED

    def __init__(
        self, stream: str | None = None, endpoint: str | None = None, message: str = ""
    ) -> None:
        super().__init__(
            message or f"permission missing for {stream or 'request'}",
            stream=stream,
            endpoint=endpoint,
        )
        self.stream = stream
        self.endpoint = endpoint


class FeatureNotEnabled(ConnectorError):
    """The vendor feature is off for this scope. A coverage fact, not a failure."""

    health_code = HealthCode.HEALTHY

    def __init__(
        self, stream: str | None = None, scope: str | None = None, message: str = ""
    ) -> None:
        super().__init__(
            message or f"{stream or 'feature'} not enabled for {scope or 'scope'}",
            stream=stream,
            scope=scope,
        )
        self.stream = stream
        self.scope = scope


class RateLimited(ConnectorError):
    """The vendor asked us to wait until ``reset_at``."""

    health_code = HealthCode.RATE_LIMIT_EXCEEDED
    retryable = True

    def __init__(self, reset_at: datetime, message: str = "") -> None:
        super().__init__(
            message or f"rate limited until {reset_at.isoformat()}", reset_at=reset_at.isoformat()
        )
        self.reset_at = reset_at


class VendorUnavailable(ConnectorError):
    """5xx, timeouts, connection resets and DNS failures after in-request retries."""

    health_code = HealthCode.VENDOR_SERVER_ERROR
    retryable = True


class VendorRejected(ConnectorError):
    """A 4xx the client could not classify further."""

    health_code = HealthCode.VENDOR_CLIENT_ERROR

    def __init__(
        self, status: int, message: str = "", body: str = "", endpoint: str | None = None
    ) -> None:
        super().__init__(
            message or f"vendor rejected the request with {status}",
            status=status,
            endpoint=endpoint,
        )
        self.status = status
        self.body = body
        self.endpoint = endpoint


class ConfigInvalid(ConnectorError):
    """Invalid options, base URL or connection config."""

    health_code = HealthCode.CONFIGURATION_ERROR


class EgressDenied(ConfigInvalid):
    """A URL resolved to a private, loopback, link-local or metadata address."""


class Gone(ConnectorError):
    """The requested record no longer exists at the vendor (targeted refresh)."""

    health_code = HealthCode.HEALTHY


class CursorExpired(ConnectorError):
    """A stored pagination cursor was rejected; restart the pass (same generation)."""

    retryable = True


class ExportExpired(ConnectorError):
    """An async export expired at the vendor; request it again."""

    retryable = True


class Cancelled(Exception):
    """Cooperative cancellation of a slice (SYNC-13). Not a connector failure."""


class DeadlineExceeded(Exception):
    """The run passed its deadline (SYNC-09)."""
