"""Vault and signing primitives (docs/plan/03-tenancy-connections-vault.md, section 5).

Key hierarchy::

    KEK (KeyProvider)                     worker roles only
      └─ wraps → environment X25519 private key
                   pairs with → public key (readable by the API)
                      └─ seals → credentials, tokens, vendor app secrets, webhook secrets
    Ingress key (symmetric, API)          inbound webhook secrets only

A sealed box carries no associated data, so the binding SEC-02 asks for (a
ciphertext copied to another connection must not open) lives inside the sealed
plaintext as an envelope ``{v, environment_id, connection_id, purpose, payload}``
that :func:`open_envelope` checks against the row it was read from.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import string
from dataclasses import dataclass
from typing import Any, Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from nacl.public import PrivateKey, PublicKey, SealedBox

ENVELOPE_VERSION = 1
_KEK_AAD = b"securefabric/vault-kek/v1"
_INGRESS_AAD_PREFIX = b"securefabric/ingress/v1/"
_WRAP_FORMAT = 1
_BASE62 = string.digits + string.ascii_letters


class VaultError(Exception):
    """A sealed value could not be opened, or opened to the wrong binding."""


def decode_key(value: str, *, length: int = 32, name: str = "key") -> bytes:
    """Decode a base64 (standard or urlsafe) secret and check its length."""
    raw = value.strip()
    padded = raw + "=" * (-len(raw) % 4)
    try:
        key = base64.b64decode(padded.replace("-", "+").replace("_", "/"), validate=True)
    except ValueError as exc:
        raise VaultError(f"{name} is not valid base64") from exc
    if len(key) != length:
        raise VaultError(f"{name} must decode to {length} bytes, got {len(key)}")
    return key


# ---------------------------------------------------------------------------
# Key encryption key
# ---------------------------------------------------------------------------


class KeyProvider(Protocol):
    """Wraps and unwraps private keys. Local master key in dev, cloud KMS in prod.

    The KEK is asymmetric, so wrapping needs only its public half. The API holds a
    :class:`WrapOnlyKeyProvider` (it can create environments and seal their new
    private keys) and can never unwrap; only worker roles hold the private half.
    """

    def wrap(self, plaintext: bytes) -> bytes: ...

    def unwrap(self, wrapped: bytes) -> bytes: ...


class WrapOnlyKeyProvider:
    def __init__(self, kek_public_key: bytes) -> None:
        if len(kek_public_key) != 32:
            raise VaultError("the KEK public key must be 32 bytes")
        self.public_key = kek_public_key

    def wrap(self, plaintext: bytes) -> bytes:
        return bytes([_WRAP_FORMAT]) + seal(self.public_key, plaintext)

    def unwrap(self, wrapped: bytes) -> bytes:
        raise VaultError("this process cannot unwrap keys (wrap-only key provider)")


class LocalKeyProvider(WrapOnlyKeyProvider):
    """The KEK derived from ``VAULT_MASTER_KEY`` (32 bytes, base64). Workers only."""

    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != 32:
            raise VaultError("the master key must be 32 bytes")
        seed = hashlib.sha256(_KEK_AAD + master_key).digest()
        self._private = PrivateKey(seed)
        super().__init__(bytes(self._private.public_key))

    @classmethod
    def from_b64(cls, value: str) -> "LocalKeyProvider":
        return cls(decode_key(value, name="VAULT_MASTER_KEY"))

    def wrap_only(self) -> WrapOnlyKeyProvider:
        return WrapOnlyKeyProvider(self.public_key)

    def unwrap(self, wrapped: bytes) -> bytes:
        if not wrapped or wrapped[0] != _WRAP_FORMAT:
            raise VaultError("unknown wrapped key format")
        return unseal(bytes(self._private), wrapped[1:])


# ---------------------------------------------------------------------------
# Environment key pairs and sealed envelopes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KeyPair:
    public_key: bytes
    private_key_wrapped: bytes


def generate_key_pair(provider: KeyProvider) -> KeyPair:
    """A fresh X25519 pair, private half wrapped by the KEK. Safe to call in the API:
    the API only ever stores the wrapped half, which it cannot open."""
    private = PrivateKey.generate()
    return KeyPair(
        public_key=bytes(private.public_key),
        private_key_wrapped=provider.wrap(bytes(private)),
    )


def seal(public_key: bytes, plaintext: bytes) -> bytes:
    return bytes(SealedBox(PublicKey(public_key)).encrypt(plaintext))


def unseal(private_key: bytes, ciphertext: bytes) -> bytes:
    try:
        return bytes(SealedBox(PrivateKey(private_key)).decrypt(ciphertext))
    except Exception as exc:
        raise VaultError("could not open sealed value") from exc


def seal_envelope(
    public_key: bytes,
    *,
    environment_id: str,
    connection_id: str | None,
    purpose: str,
    payload: Any,
) -> bytes:
    envelope = {
        "v": ENVELOPE_VERSION,
        "environment_id": str(environment_id),
        "connection_id": str(connection_id) if connection_id is not None else None,
        "purpose": purpose,
        "payload": payload,
    }
    return seal(public_key, json.dumps(envelope, separators=(",", ":")).encode())


def open_envelope(
    private_key: bytes,
    ciphertext: bytes,
    *,
    environment_id: str,
    connection_id: str | None,
    purpose: str,
) -> Any:
    """Open and check the binding. A mismatch is a :class:`VaultError` (SEC-02)."""
    try:
        envelope = json.loads(unseal(private_key, ciphertext))
    except json.JSONDecodeError as exc:
        raise VaultError("sealed value is not an envelope") from exc
    expected = {
        "v": ENVELOPE_VERSION,
        "environment_id": str(environment_id),
        "connection_id": str(connection_id) if connection_id is not None else None,
        "purpose": purpose,
    }
    for key, want in expected.items():
        if envelope.get(key) != want:
            raise VaultError(f"sealed value is bound to a different {key}")
    return envelope["payload"]


# ---------------------------------------------------------------------------
# Ingress key: symmetric, held by the API, for inbound webhook secrets only
# ---------------------------------------------------------------------------


class IngressCipher:
    def __init__(self, key: bytes) -> None:
        self._aead = AESGCM(key)

    @classmethod
    def from_b64(cls, value: str) -> "IngressCipher":
        return cls(decode_key(value, name="INGRESS_KEY"))

    def encrypt(self, plaintext: bytes, *, bound_to: str) -> bytes:
        nonce = os.urandom(12)
        aad = _INGRESS_AAD_PREFIX + bound_to.encode()
        return bytes([_WRAP_FORMAT]) + nonce + self._aead.encrypt(nonce, plaintext, aad)

    def decrypt(self, ciphertext: bytes, *, bound_to: str) -> bytes:
        if not ciphertext or ciphertext[0] != _WRAP_FORMAT:
            raise VaultError("unknown ingress ciphertext format")
        aad = _INGRESS_AAD_PREFIX + bound_to.encode()
        try:
            return self._aead.decrypt(ciphertext[1:13], ciphertext[13:], aad)
        except Exception as exc:
            raise VaultError("could not decrypt ingress secret") from exc


class PayloadKeyring:
    """STORE-09: AES-256-GCM for stored vendor payloads, with versioned keys.

    ``PAYLOAD_KEYS`` is ``"1:<base64 32 bytes>,2:<...>"``. New payloads are sealed
    with the highest version; every listed version still opens, so a key rotates by
    adding a version, letting rows re-encrypt over time, then dropping the old one.
    The ciphertext is bound to its row's identity (``bound_to``), so a payload copied
    onto another tenant's row does not open.
    """

    _AAD = b"sf-payload-v1:"

    def __init__(self, keys: dict[int, bytes]) -> None:
        if not keys:
            raise VaultError("PAYLOAD_KEYS lists no keys")
        if any(not 1 <= v <= 255 for v in keys):
            raise VaultError("payload key versions are 1..255")
        self._aeads = {v: AESGCM(k) for v, k in keys.items()}
        self.current = max(keys)
        self.versions = frozenset(keys)

    @classmethod
    def from_setting(cls, value: str) -> "PayloadKeyring":
        keys: dict[int, bytes] = {}
        for part in value.split(","):
            if not part.strip():
                continue
            version, _, b64 = part.strip().partition(":")
            keys[int(version)] = decode_key(b64, name=f"PAYLOAD_KEYS version {version}")
        return cls(keys)

    def seal(self, plaintext: bytes, *, bound_to: str) -> bytes:
        nonce = os.urandom(12)
        ct = self._aeads[self.current].encrypt(nonce, plaintext, self._AAD + bound_to.encode())
        return bytes([self.current]) + nonce + ct

    def open(self, blob: bytes, *, bound_to: str) -> bytes:
        aead = self._aeads.get(blob[0]) if blob else None
        if aead is None:
            raise VaultError("payload sealed with an unknown key version")
        try:
            return aead.decrypt(blob[1:13], blob[13:], self._AAD + bound_to.encode())
        except Exception as exc:
            raise VaultError("payload does not open (wrong key or wrong row)") from exc


# ---------------------------------------------------------------------------
# Tokens, keyed hashes, signatures
# ---------------------------------------------------------------------------


def random_base62(length: int) -> str:
    return "".join(secrets.choice(_BASE62) for _ in range(length))


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def keyed_hash(pepper: bytes, value: str) -> bytes:
    return hmac.new(pepper, value.encode(), hashlib.sha256).digest()


def sha256(value: bytes | str) -> bytes:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).digest()


def hmac_sha256_hex(secret: bytes | str, message: bytes) -> str:
    key = secret.encode() if isinstance(secret, str) else secret
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def constant_time_equals(a: str | bytes, b: str | bytes) -> bool:
    a_b = a.encode() if isinstance(a, str) else a
    b_b = b.encode() if isinstance(b, str) else b
    return hmac.compare_digest(a_b, b_b)
