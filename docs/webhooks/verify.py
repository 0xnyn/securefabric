"""Verify a SecureFabric webhook (Python 3, standard library only)."""

import hashlib
import hmac
import sys
import time


def verify(
    secret: str, signature_header: str, timestamp: str, raw_body: bytes, tolerance_s: int = 300
) -> bool:
    """True if any v1= signature matches and the timestamp is fresh."""
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > tolerance_s:  # replay protection
        return False
    expected = (
        "v1=" + hmac.new(secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
    )
    # During a secret rotation two signatures are sent, comma-separated.
    return any(hmac.compare_digest(expected, part.strip()) for part in signature_header.split(","))


if (
    __name__ == "__main__"
):  # verify.py <secret> <SecureFabric-Signature> <SecureFabric-Timestamp> < body
    ok = verify(sys.argv[1], sys.argv[2], sys.argv[3], sys.stdin.buffer.read())
    sys.exit(0 if ok else 1)
