import json

import pytest

from app.server_api import ApiError, ApiNotConfigured, ServerAPI, derive_base_url


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return self.response


class FakeConfig:
    def __init__(self, api_url="https://example.com/api", device_id="手机"):
        self.api_url = api_url
        self.device_id = device_id

    def get(self, key, default=None):
        if key == "api_url":
            return self.api_url
        if key == "device_id":
            return self.device_id
        return default


def test_derive_base_url_variants():
    assert derive_base_url("https://example.com/api") == "https://example.com"
    assert derive_base_url("https://example.com/prefix/api/") == "https://example.com/prefix"
    assert derive_base_url("https://example.com") == "https://example.com"
    with pytest.raises(ApiNotConfigured):
        derive_base_url("")


def test_fetch_stats_encodes_device_and_date():
    session = FakeSession(FakeResponse(200, {"success": True, "total": 12, "apps": {}}))
    api = ServerAPI(FakeConfig(), session)

    data = api.fetch_stats("手机", "2026-10-26")

    assert data["total"] == 12
    call = session.calls[0]
    assert call["url"] == "https://example.com/api/stats/%E6%89%8B%E6%9C%BA"
    assert call["params"] == {"date": "2026-10-26"}


def test_envelope_unwrapping_and_bare_shapes():
    session = FakeSession(
        FakeResponse(200, {"success": True, "data": [{"appName": "A"}], "count": 1})
    )
    api = ServerAPI(FakeConfig(), session)
    assert api.fetch_recent() == [{"appName": "A"}]

    session = FakeSession(FakeResponse(200, [{"device": "手机"}]))
    api = ServerAPI(FakeConfig(), session)
    assert api.fetch_devices() == [{"device": "手机"}]


def test_server_error_and_failed_envelope():
    session = FakeSession(FakeResponse(500, {"success": False, "error": "boom"}))
    api = ServerAPI(FakeConfig(), session)
    with pytest.raises(ApiError) as exc:
        api.fetch_devices()
    assert "boom" in str(exc.value)

    session = FakeSession(FakeResponse(200, {"success": False, "error": "bad"}))
    api = ServerAPI(FakeConfig(), session)
    with pytest.raises(ApiError):
        api.fetch_devices()


def test_missing_configuration_raises():
    api = ServerAPI(FakeConfig(api_url=""), FakeSession(FakeResponse(200, [])))
    with pytest.raises(ApiNotConfigured):
        api.fetch_devices()


def test_weekly_parameters():
    session = FakeSession(FakeResponse(200, {"dailyTotals": {}}))
    api = ServerAPI(FakeConfig(), session)
    api.fetch_weekly("手机", -1)
    assert session.calls[0]["params"] == {"weekOffset": -1}


def test_monthly_parameters():
    session = FakeSession(FakeResponse(200, {"dailyTotals": {}}))
    api = ServerAPI(FakeConfig(), session)
    api.fetch_monthly("手机", -2)
    assert session.calls[0]["url"] == "https://example.com/api/monthly/%E6%89%8B%E6%9C%BA"
    assert session.calls[0]["params"] == {"monthOffset": -2}
