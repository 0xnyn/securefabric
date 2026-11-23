import json
import logging

import pytest

from securefabric_core import (
    AppError,
    BaseServiceSettings,
    Environment,
    LogFormat,
    NotFoundError,
    configure_logging,
    get_logger,
)


def test_error_to_dict_includes_details_only_when_present() -> None:
    assert AppError("boom").to_dict() == {"code": "internal_error", "message": "boom"}
    err = NotFoundError("missing", id="42")
    assert err.status_code == 404
    assert err.to_dict() == {"code": "not_found", "message": "missing", "details": {"id": "42"}}


def test_settings_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_FORMAT", "json")
    settings = BaseServiceSettings(_env_file=None)
    assert settings.environment is Environment.PRODUCTION
    assert settings.is_production
    assert settings.log_format is LogFormat.JSON


def test_settings_reject_bad_log_level() -> None:
    with pytest.raises(ValueError, match="log_level"):
        BaseServiceSettings(log_level="LOUD", _env_file=None)


def test_json_logging_emits_structured_lines(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", LogFormat.JSON)
    get_logger("test").info("hello", answer=42)
    line = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "hello"
    assert payload["answer"] == 42
    assert payload["level"] == "info"
    assert logging.getLogger().level == logging.INFO
