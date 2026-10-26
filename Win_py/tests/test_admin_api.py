import pytest

from app.admin_api import AdminAPI, AdminAuthError, mask_value
from app.server_api import ApiError


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "json": kwargs.get("json"),
                "headers": kwargs.get("headers") or {},
            }
        )
        return self.responses.pop(0)


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


def test_login_and_bearer_header():
    session = FakeSession(
        [
            FakeResponse(200, {"success": True, "token": "jwt-token"}),
            FakeResponse(200, {"success": True, "config": {"AI_MODEL": "gpt-4"}}),
        ]
    )
    api = AdminAPI(FakeConfig(), session)

    api.login("admin", "password")
    assert api.is_authenticated
    assert api.username == "admin"

    config = api.get_config()
    assert config == {"AI_MODEL": "gpt-4"}
    assert session.calls[1]["url"] == "https://example.com/admin/config"
    assert session.calls[1]["headers"]["Authorization"] == "Bearer jwt-token"


def test_auth_error_clears_token():
    session = FakeSession(
        [
            FakeResponse(200, {"success": True, "token": "jwt-token"}),
            FakeResponse(401, {"success": False, "error": "expired"}),
        ]
    )
    api = AdminAPI(FakeConfig(), session)
    api.login("admin", "password")

    with pytest.raises(AdminAuthError):
        api.get_config()
    assert not api.is_authenticated


def test_insecure_transport_is_rejected():
    api = AdminAPI(FakeConfig(api_url="http://example.com/api"), FakeSession([]))
    with pytest.raises(ApiError):
        api.login("admin", "password")


def test_login_failure_is_not_auth_expiry():
    session = FakeSession(
        [FakeResponse(401, {"success": False, "message": "用户名或密码错误"})]
    )
    api = AdminAPI(FakeConfig(), session)

    with pytest.raises(ApiError) as exc:
        api.login("admin", "wrong")
    assert not isinstance(exc.value, AdminAuthError)
    assert "用户名或密码错误" in str(exc.value)


def test_mask_value():
    masked = mask_value("MONGODB_URI", "mongodb://user:secret@host/db")
    assert "••••" in masked
    assert "secret" not in masked

    assert mask_value("AI_MODEL", "gpt-4") == "gpt-4"
    assert mask_value("AI_MAX_TOKENS", "1000") == "1000"
    assert mask_value("PUBLISH_API_KEY", "abc") == "••••••"


def test_ai_trigger_encodes_device_and_body():
    session = FakeSession(
        [
            FakeResponse(200, {"success": True, "token": "jwt-token"}),
            FakeResponse(200, {"success": True, "taskId": "t1"}),
        ]
    )
    api = AdminAPI(FakeConfig(), session)
    api.login("admin", "password")

    api.ai_trigger("手机", "2026-10-26", 8)

    call = session.calls[1]
    assert call["url"] == "https://example.com/admin/ai/trigger/%E6%89%8B%E6%9C%BA"
    assert call["json"] == {"timezoneOffset": 8, "date": "2026-10-26"}


def test_update_config_sends_only_given_keys():
    session = FakeSession(
        [
            FakeResponse(200, {"success": True, "token": "jwt-token"}),
            FakeResponse(200, {"success": True, "updatedKeys": ["AI_MODEL"]}),
        ]
    )
    api = AdminAPI(FakeConfig(), session)
    api.login("admin", "password")

    api.update_config({"AI_MODEL": "gpt-3.5-turbo"})

    assert session.calls[1]["json"] == {"AI_MODEL": "gpt-3.5-turbo"}
