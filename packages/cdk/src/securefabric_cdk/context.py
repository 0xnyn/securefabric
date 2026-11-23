"""The context a connector is handed: everything it may touch (part 5, section 3).

There is no ``ctx.db`` and no ``ctx.credentials``. The HTTP client injects auth
itself, so connector code never holds a token.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from securefabric_cdk import paginate
from securefabric_cdk.errors import Cancelled, DeadlineExceeded
from securefabric_cdk.http import HttpClient, MemoryOpLog, OpLog
from securefabric_core.clock import SYSTEM_CLOCK, Clock


class _Log:
    def __init__(self, sink: OpLog) -> None:
        self._sink = sink

    def debug(self, message: str, **fields: Any) -> None:
        self._sink.log("debug", message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        self._sink.log("info", message, **fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._sink.log("warning", message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self._sink.log("error", message, **fields)


@dataclass
class Context:
    http: HttpClient
    config: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    clock: Clock = SYSTEM_CLOCK
    deadline: datetime | None = None
    stream: str | None = None
    log_sink: OpLog = field(default_factory=MemoryOpLog)
    cancelled: bool = False
    paginate = paginate

    @property
    def log(self) -> _Log:
        return _Log(self.log_sink)

    def now(self) -> datetime:
        return self.clock.now()

    def remaining_seconds(self) -> float | None:
        if self.deadline is None:
            return None
        return (self.deadline - self.clock.now()).total_seconds()

    def check(self) -> None:
        """Cooperative cancellation and deadline check; long loops call this."""
        if self.cancelled:
            raise Cancelled()
        if self.deadline is not None and self.clock.now() >= self.deadline:
            raise DeadlineExceeded()
