def test_payload_keyring_binds_rows_and_rotates() -> None:
    import base64
    import os

    import pytest

    from securefabric_core.crypto import PayloadKeyring, VaultError

    k1, k2 = (base64.b64encode(os.urandom(32)).decode() for _ in range(2))
    v1 = PayloadKeyring.from_setting(f"1:{k1}")
    blob = v1.seal(b"payload", bound_to="env/conn/finding")
    assert v1.open(blob, bound_to="env/conn/finding") == b"payload"
    with pytest.raises(VaultError):
        v1.open(blob, bound_to="env/OTHER/finding")  # copied onto another row: refused
    # Rotation: add version 2; old rows still open, new rows use 2.
    both = PayloadKeyring.from_setting(f"1:{k1},2:{k2}")
    assert both.current == 2 and both.open(blob, bound_to="env/conn/finding") == b"payload"
    assert both.seal(b"x", bound_to="b")[0] == 2
    # Once version 1 is dropped, its rows no longer open (re-encrypt before dropping).
    with pytest.raises(VaultError):
        PayloadKeyring.from_setting(f"2:{k2}").open(blob, bound_to="env/conn/finding")
