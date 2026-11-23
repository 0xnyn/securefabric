"""Canonical JSON and the material hash (docs/plan/02-data-model.md, section 6).

The encoding is independent of key order, whitespace and float spelling, so a
record whose meaning did not change hashes the same and is not rewritten
(STORE-02, STORE-03). Rules:

- object keys sorted by code point, no insignificant whitespace;
- datetimes normalised to UTC with millisecond precision (``...T10:15:00.123Z``);
- floats with an integral value encode as integers (``1.0`` == ``1``), others by
  Python's shortest round-trip ``repr``; ``-0.0`` is ``0``; NaN and infinities are
  rejected because JSON cannot carry them;
- UUIDs, enums and dates encode as strings; sets are rejected (no order).
"""

import hashlib
import json
import math
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class CanonicalEncodingError(ValueError):
    pass


def format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    value = value.astimezone(UTC)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def _float(value: float) -> str:
    if math.isnan(value) or math.isinf(value):
        raise CanonicalEncodingError("NaN and infinity have no canonical JSON form")
    if value == 0:
        return "0"
    if value.is_integer() and abs(value) < 2**63:
        return str(int(value))
    return repr(value)


def _encode(value: Any, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, Enum):
        _encode(value.value, out)
    elif isinstance(value, int):
        out.append(str(value))
    elif isinstance(value, float):
        out.append(_float(value))
    elif isinstance(value, Decimal):
        _encode(float(value), out)
    elif isinstance(value, str):
        out.append(json.dumps(value, ensure_ascii=False))
    elif isinstance(value, datetime):
        out.append(json.dumps(format_datetime(value)))
    elif isinstance(value, date):
        out.append(json.dumps(value.isoformat()))
    elif isinstance(value, uuid.UUID):
        out.append(json.dumps(str(value)))
    elif isinstance(value, Mapping):
        items = sorted(((str(k), v) for k, v in value.items()), key=lambda kv: kv[0])
        out.append("{")
        for i, (k, v) in enumerate(items):
            if i:
                out.append(",")
            out.append(json.dumps(k, ensure_ascii=False))
            out.append(":")
            _encode(v, out)
        out.append("}")
    elif isinstance(value, (set, frozenset)):
        raise CanonicalEncodingError("sets have no canonical order")
    elif isinstance(value, (list, tuple)) or (
        isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray))
    ):
        out.append("[")
        for i, v in enumerate(value):
            if i:
                out.append(",")
            _encode(v, out)
        out.append("]")
    else:
        raise CanonicalEncodingError(f"cannot canonically encode {type(value).__name__}")


def canonical_json(value: Any) -> str:
    out: list[str] = []
    _encode(value, out)
    return "".join(out)


def material_hash(value: Any) -> bytes:
    """SHA-256 over the canonical JSON of ``value``."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).digest()
