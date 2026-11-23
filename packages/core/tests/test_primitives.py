"""ids, clock, canonical hashing, vault crypto and redaction."""

import json
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from securefabric_core.canonical import CanonicalEncodingError, canonical_json, material_hash
from securefabric_core.clock import FrozenClock
from securefabric_core.crypto import (
    IngressCipher,
    LocalKeyProvider,
    VaultError,
    generate_key_pair,
    open_envelope,
    seal_envelope,
)
from securefabric_core.ids import RECORD_NAMESPACE, record_id, uuid7
from securefabric_core.redact import REDACTED, redact, redact_text, register_secret

# ---------------------------------------------------------------- ids


def test_uuid7_is_version_7_and_time_ordered() -> None:
    ids = [uuid7() for _ in range(200)]
    assert all(i.version == 7 for i in ids)
    # Same-millisecond ids are random within the ms, so compare the ms prefix only.
    prefixes = [i.int >> 80 for i in ids]
    assert prefixes == sorted(prefixes)


def test_record_id_is_stable_and_scoped() -> None:
    conn = uuid.UUID("11111111-1111-1111-1111-111111111111")
    a = record_id(conn, "finding", "dependabot:1:2")
    assert a == record_id(str(conn), "finding", "dependabot:1:2")
    assert a.version == 5
    assert a != record_id(conn, "resource", "dependabot:1:2")
    assert a != record_id(uuid.uuid4(), "finding", "dependabot:1:2")
    # The namespace is part of the public contract: never change it.
    assert str(RECORD_NAMESPACE) == "6f1c9a4e-2b7d-5c3a-9e8f-5ec0fab71c00"


def test_frozen_clock_advances() -> None:
    clock = FrozenClock(datetime(2026, 1, 1, tzinfo=UTC))
    clock.advance(minutes=5)
    assert clock.now() == datetime(2026, 1, 1, 0, 5, tzinfo=UTC)


# ---------------------------------------------------------------- canonical JSON

json_scalars = st.none() | st.booleans() | st.integers(-(2**53), 2**53) | st.text(max_size=20)
json_values = st.recursive(
    json_scalars | st.floats(allow_nan=False, allow_infinity=False, width=64),
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4)
    ),
    max_leaves=20,
)


def _shuffle_keys(value: object, seed: int) -> object:
    if isinstance(value, dict):
        items = list(value.items())
        if items:
            k = seed % len(items)
            items = items[k:] + items[:k]
            items.reverse() if seed % 2 else None
        return {key: _shuffle_keys(v, seed + 1) for key, v in items}
    if isinstance(value, list):
        return [_shuffle_keys(v, seed + 1) for v in value]
    return value


@given(json_values, st.integers(0, 1000))
def test_hash_is_independent_of_key_order(value: object, seed: int) -> None:
    assert material_hash(value) == material_hash(_shuffle_keys(value, seed))


@given(json_values)
def test_canonical_json_round_trips_through_json(value: object) -> None:
    encoded = canonical_json(value)
    # Valid JSON, and re-encoding the parsed value is a fixed point.
    assert canonical_json(json.loads(encoded)) == encoded


@given(st.integers(-(2**53), 2**53))
def test_integral_floats_hash_as_integers(n: int) -> None:
    assert material_hash({"x": float(n)}) == material_hash({"x": n})


def test_float_spelling_does_not_matter() -> None:
    assert material_hash(json.loads('{"a": 1.50}')) == material_hash(json.loads('{"a": 1.5}'))
    assert material_hash({"a": -0.0}) == material_hash({"a": 0})
    assert canonical_json({"b": [1, 2.25], "a": None}) == '{"a":null,"b":[1,2.25]}'


def test_datetimes_normalise_to_utc_millis() -> None:
    plus2 = timezone(timedelta(hours=2))
    a = datetime(2026, 3, 1, 12, 0, 0, 123456, tzinfo=plus2)
    b = datetime(2026, 3, 1, 10, 0, 0, 123999, tzinfo=UTC)
    assert canonical_json(a) == '"2026-03-01T10:00:00.123Z"'
    assert material_hash({"t": a}) == material_hash({"t": b})


def test_unencodable_values_are_rejected() -> None:
    with pytest.raises(CanonicalEncodingError):
        canonical_json(float("nan"))
    with pytest.raises(CanonicalEncodingError):
        canonical_json({1, 2})


# ---------------------------------------------------------------- vault

KEK = LocalKeyProvider(b"k" * 32)


def test_sealed_envelope_opens_only_with_matching_binding() -> None:
    pair = generate_key_pair(KEK)
    sealed = seal_envelope(
        pair.public_key,
        environment_id="env-a",
        connection_id="c1",
        purpose="credential",
        payload={"api_key": "s3cr3t"},
    )
    private = KEK.unwrap(pair.private_key_wrapped)
    assert open_envelope(
        private, sealed, environment_id="env-a", connection_id="c1", purpose="credential"
    ) == {"api_key": "s3cr3t"}
    # SEC-02: copied to another connection, environment or purpose, it is useless.
    for kwargs in (
        {"environment_id": "env-a", "connection_id": "c2", "purpose": "credential"},
        {"environment_id": "env-b", "connection_id": "c1", "purpose": "credential"},
        {"environment_id": "env-a", "connection_id": "c1", "purpose": "token"},
    ):
        with pytest.raises(VaultError):
            open_envelope(private, sealed, **kwargs)


def test_wrong_private_key_cannot_open() -> None:
    a, b = generate_key_pair(KEK), generate_key_pair(KEK)
    sealed = seal_envelope(
        a.public_key, environment_id="e", connection_id=None, purpose="p", payload=1
    )
    with pytest.raises(VaultError):
        open_envelope(
            KEK.unwrap(b.private_key_wrapped),
            sealed,
            environment_id="e",
            connection_id=None,
            purpose="p",
        )


def test_kek_unwrap_rejects_tampering_and_other_keys() -> None:
    wrapped = KEK.wrap(b"private")
    assert KEK.unwrap(wrapped) == b"private"
    with pytest.raises(VaultError):
        LocalKeyProvider(b"x" * 32).unwrap(wrapped)
    with pytest.raises(VaultError):
        KEK.unwrap(wrapped[:-1] + bytes([wrapped[-1] ^ 1]))


def test_wrap_only_provider_cannot_unwrap() -> None:
    api_side = KEK.wrap_only()
    wrapped = api_side.wrap(b"env-private-key")
    with pytest.raises(VaultError):
        api_side.unwrap(wrapped)
    assert KEK.unwrap(wrapped) == b"env-private-key"


def test_ingress_cipher_is_bound() -> None:
    cipher = IngressCipher(b"i" * 32)
    ct = cipher.encrypt(b"hook-secret", bound_to="app-1")
    assert cipher.decrypt(ct, bound_to="app-1") == b"hook-secret"
    with pytest.raises(VaultError):
        cipher.decrypt(ct, bound_to="app-2")


# ---------------------------------------------------------------- redaction


def test_redact_by_name_and_pattern() -> None:
    out = redact(
        {
            "Authorization": "Bearer abc.def.ghi",
            "client_secret": "x",
            "secret_type": "github_personal_access_token",
            "nested": [{"token": "t"}, "ghs_" + "a" * 36],
            "note": "key sfk_live_us_" + "A" * 43 + " leaked",
            "count": 3,
        }
    )
    assert out["Authorization"] == REDACTED
    assert out["client_secret"] == REDACTED
    assert out["secret_type"] == "github_personal_access_token"
    assert out["nested"] == [{"token": REDACTED}, REDACTED]
    assert out["note"] == f"key {REDACTED} leaked"
    assert out["count"] == 3


def test_registered_literals_are_scrubbed() -> None:
    register_secret("canary-value-123")
    assert redact_text("got canary-value-123 back") == f"got {REDACTED} back"
