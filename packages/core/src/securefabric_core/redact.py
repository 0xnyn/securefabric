"""Redaction by field name and by value pattern (SEC-07).

Applied in the logging pipeline before a line is written, to operation-log
messages, to error bodies stored on runs, and to recorded fixtures.
"""

import re
from collections.abc import Mapping, MutableMapping
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_NAME = re.compile(
    r"(?i)(^|_|-)(secret|password|passwd|token|authorization|api[_-]?key|apikey|private[_-]?key|"
    r"client[_-]?secret|credential|credentials|cookie|set-cookie|refresh[_-]?token|"
    r"access[_-]?token|session[_-]?token|signature|pepper|master[_-]?key)s?($|_|-)"
)

# Names that look sensitive but carry no secret (counts, hints, flags).
_ALLOWED_NAMES = frozenset(
    {
        "secret_type",
        "secret_type_display_name",
        "secret_scanning",
        "secret_scanning_push_protection",
        "secret_scanning_alerts",
        "secret_locations",
        "secret_severity",
        "secret_hint",
        "token_expires_at",
        "has_more_locations",
        "secret_scanning_validity_checks",
        "secret_scanning_non_provider_patterns",
        "secret_scanning_ai_detection",
        "credentials_schema",
        "fields_set",
    }
)

_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,255})\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,255}\b"),
    re.compile(r"\bsfk_(live|test)_[a-z0-9]+_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsfcs_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bwhsec_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{16,}\b"),
)

# Extra literal values to scrub (canary credentials in tests, a connection's own
# secrets while it syncs). Kept small: registered per process.
_EXTRA_LITERALS: set[str] = set()


def register_secret(value: str) -> None:
    if value and len(value) >= 8:
        _EXTRA_LITERALS.add(value)


def is_sensitive_name(name: str) -> bool:
    lowered = name.lower()
    if lowered in _ALLOWED_NAMES:
        return False
    return bool(_SENSITIVE_NAME.search(lowered))


def redact_text(text: str) -> str:
    for pattern in _VALUE_PATTERNS:
        text = pattern.sub(REDACTED, text)
    for literal in _EXTRA_LITERALS:
        if literal in text:
            text = text.replace(literal, REDACTED)
    return text


def redact(value: Any, *, extra_names: frozenset[str] = frozenset()) -> Any:
    """Return a copy of ``value`` with sensitive fields and values replaced."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if key in extra_names or is_sensitive_name(key):
                out[key] = REDACTED if v not in (None, "", [], {}) else v
            else:
                out[key] = redact(v, extra_names=extra_names)
        return out
    if isinstance(value, list):
        return [redact(v, extra_names=extra_names) for v in value]
    if isinstance(value, tuple):
        return tuple(redact(v, extra_names=extra_names) for v in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def structlog_processor(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """A structlog processor: redacts every field of every log line."""
    redacted: dict[str, Any] = redact(event_dict)
    return redacted
