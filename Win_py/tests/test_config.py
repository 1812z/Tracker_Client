import json

import pytest

from app.config import (
    AppConfig,
    validate_api_url,
    validate_interval,
    validate_log_retention,
)


def test_missing_file_creates_defaults(tmp_path):
    path = tmp_path / "config.json"
    config = AppConfig(path).load()

    assert path.exists()
    assert config.get("monitor_interval") == 1
    assert config.get("api_url") == ""
    assert config.get("log_retention_days") == 30
    assert config.get("log_retention_count") == 30
    device_id = config.get("device_id")
    assert device_id and device_id != "your_device_id"

    reloaded = AppConfig(path).load()
    assert reloaded.get("device_id") == device_id


def test_partial_config_is_merged_and_normalized(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "api_url": "https://api.example.com",
                "secret_key": "your_secret_key",
                "monitor_interval": 9999,
                "theme": 9,
                "log_retention_days": 0,
                "log_retention_count": 5000,
                "version": "1.0.1",
            }
        ),
        encoding="utf-8",
    )

    config = AppConfig(path).load()

    assert config.get("api_url") == ""
    assert config.get("secret_key") == ""
    assert config.get("monitor_interval") == 3600
    assert config.get("theme") == 2
    assert config.get("log_retention_days") == 1
    assert config.get("log_retention_count") == 1000
    assert config.get("version") is None
    assert config.get("report_enabled") is True


def test_broken_config_is_backed_up(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not-json", encoding="utf-8")

    config = AppConfig(path).load()

    assert (tmp_path / "config.json.bad").exists()
    assert config.get("monitor_interval") == 1


def test_validation_helpers():
    with pytest.raises(ValueError):
        validate_api_url("ftp://example.com")
    with pytest.raises(ValueError):
        validate_interval(0)
    with pytest.raises(ValueError):
        validate_interval("abc")
    assert validate_interval("30") == 30

    with pytest.raises(ValueError):
        validate_log_retention(0, 30)
    with pytest.raises(ValueError):
        validate_log_retention(30, 0)
    assert validate_log_retention("30", "10") == (30, 10)
