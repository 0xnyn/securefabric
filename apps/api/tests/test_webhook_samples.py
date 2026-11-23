"""The published verification samples (docs/webhooks/verify.*) accept exactly what the
delivery code signs, in every language the docs show (M10: samples in four languages).

Each sample runs as a real program against signatures from ``delivery.sign``.
"""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from securefabric_domain.events.delivery import sign

SAMPLES = Path(__file__).resolve().parents[3] / "docs" / "webhooks"
SECRET = "whsec_test_9f1c"
OLD = "whsec_old_33aa"
BODY = b'{"id":"evt_1","type":"sync.completed","data":{"records":3}}'

RUNNERS = {
    "python": (["python3", str(SAMPLES / "verify.py")], "python3"),
    "node": (["node", str(SAMPLES / "verify.mjs")], "node"),
    "go": ([], "go"),  # compiled once below: `go run` itself writes to stderr on exit 1
    "ruby": (["ruby", str(SAMPLES / "verify.rb")], "ruby"),
}


_GO_BINARY: list[str] = []


def _argv(lang: str) -> list[str]:
    if lang != "go":
        return RUNNERS[lang][0]
    if not _GO_BINARY:
        out = Path(tempfile.mkdtemp()) / "verify"
        subprocess.run(  # noqa: S603 - fixed toolchain call
            ["go", "build", "-o", str(out), str(SAMPLES / "verify.go")],  # noqa: S607
            check=True,
            timeout=300,
        )
        _GO_BINARY.append(str(out))
    return _GO_BINARY


def run(lang: str, secret: str, header: str, ts: str, body: bytes) -> bool:
    argv = _argv(lang)
    proc = subprocess.run(  # noqa: S603 - fixed sample programs
        [*argv, secret, header, ts], input=body, capture_output=True, timeout=120
    )
    # A crash must never pass for a rejection: exit 0/1 and nothing on stderr.
    assert proc.returncode in (0, 1) and not proc.stderr, proc.stderr.decode()
    return proc.returncode == 0


@pytest.mark.parametrize("lang", list(RUNNERS))
def test_sample_accepts_what_we_sign_and_rejects_the_rest(lang: str) -> None:
    if shutil.which(RUNNERS[lang][1]) is None:
        pytest.skip(f"{RUNNERS[lang][1]} is not installed")
    now = int(time.time())
    good = sign(SECRET, now, BODY)
    assert run(lang, SECRET, good, str(now), BODY)
    # Rotation: both secrets sign for 24 h; either matches.
    assert run(lang, SECRET, f"{sign(OLD, now, BODY)}, {good}", str(now), BODY)
    assert not run(lang, SECRET, good, str(now), BODY + b" ")  # body changed
    assert not run(lang, "whsec_wrong", good, str(now), BODY)  # wrong secret
    stale = now - 3600
    assert not run(lang, SECRET, sign(SECRET, stale, BODY), str(stale), BODY)  # replay
    assert not run(lang, SECRET, good, "not-a-number", BODY)
