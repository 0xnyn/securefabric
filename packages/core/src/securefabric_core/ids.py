"""Identifiers (docs/plan/02-data-model.md, section 6).

- Control-plane rows use UUIDv7 (time ordered). Postgres generates most of them
  with ``absurd.portable_uuidv7()``; :func:`uuid7` is the Python equivalent for
  ids we need before an insert.
- Canonical records use UUIDv5 over ``connection_id|object_kind|natural_key`` so
  the same vendor record always gets the same id (STORE-01). The namespace is
  fixed forever: changing it would re-key every stored record.
"""

import os
import time
import uuid
from typing import Literal

RECORD_NAMESPACE = uuid.UUID("6f1c9a4e-2b7d-5c3a-9e8f-5ec0fab71c00")

ObjectKind = Literal["resource", "finding"]


def uuid7() -> uuid.UUID:
    """A RFC 9562 UUIDv7: 48-bit unix milliseconds, then random bits."""
    ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version
    value |= ((rand >> 62) & 0xFFF) << 64  # rand_a, 12 bits
    value |= 0b10 << 62  # variant
    value |= rand & ((1 << 62) - 1)  # rand_b
    return uuid.UUID(int=value)


def record_id(connection_id: uuid.UUID | str, kind: ObjectKind, natural_key: str) -> uuid.UUID:
    """The stable id of a canonical record."""
    return uuid.uuid5(RECORD_NAMESPACE, f"{connection_id}|{kind}|{natural_key}")
