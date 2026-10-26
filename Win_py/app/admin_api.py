"""Admin API 客户端：登录、配置、重启、AI 任务、账户管理。"""

import logging
import re
import threading
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote, urlsplit

import requests

from app.server_api import ApiError, derive_base_url, extract_error

logger = logging.getLogger(__name__)

ADMIN_PREFIX = "/admin"
SENSITIVE_KEY_HINTS = ("KEY", "SECRET", "PASSWORD", "PWD", "URI")
SENSITIVE_EXACT_KEYS = {"TOKEN", "ACCESS_TOKEN", "REFRESH_TOKEN", "AUTH_TOKEN"}


class AdminAuthError(ApiError):
    pass


def is_sensitive_key(key: str) -> bool:
    upper = (key or "").upper()
    if upper in SENSITIVE_EXACT_KEYS:
        return True
    # AI_MAX_TOKENS 之类的配置不是凭据，只有 *_TOKEN 才是。
    if upper.endswith("_TOKEN") or "_TOKEN_" in upper:
        return True
    return any(hint in upper for hint in SENSITIVE_KEY_HINTS)


def mask_value(key: str, value: Any) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    if not is_sensitive_key(key):
        return text
    if "URI" in (key or "").upper():
        return re.sub(r"(://[^:/@]+:)([^@]+)(@)", r"\1••••\3", text)
    if len(text) <= 6:
        return "••••••"
    return f"{text[:3]}••••{text[-2:]}"


def is_transport_secure(base_url: str) -> bool:
    parts = urlsplit(base_url)
    if parts.scheme == "https":
        return True
    if parts.scheme != "http":
        return False
    host = (parts.hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "::1")


class AdminAPI:
    def __init__(self, config, session=None):
        self._config = config
        self._session = session or requests.Session()
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._username: Optional[str] = None

    @property
    def username(self) -> str:
        return self._username or ""

    @property
    def is_authenticated(self) -> bool:
        with self._lock:
            return bool(self._token)

    def logout(self) -> None:
        with self._lock:
            self._token = None
            self._username = None

    def base_url(self) -> str:
        return derive_base_url(str(self._config.get("api_url", "") or ""))

    def admin_base_url(self) -> str:
        """管理端点实际挂载在服务端 /admin 前缀下。"""
        return f"{self.base_url().rstrip('/')}{ADMIN_PREFIX}"

    def login(self, username: str, password: str) -> Dict[str, Any]:
        username = (username or "").strip()
        password = password or ""
        if not username or not password:
            raise ValueError("用户名和密码不能为空")

        data = self._request(
            "POST",
            "/login",
            json_body={"username": username, "password": password},
            auth=False,
        )
        token = data.get("token")
        if not token:
            raise ApiError("登录响应缺少 token")
        with self._lock:
            self._token = str(token)
            self._username = username
        logger.info("管理员登录成功: %s", username)
        return data

    def update_account(self, username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if username:
            body["username"] = username
        if password:
            body["password"] = password
        if not body:
            raise ValueError("请填写要更新的用户名或密码")

        data = self._request("POST", "/account/update", json_body=body)
        if data.get("requireRelogin"):
            self.logout()
        return data

    def get_config(self) -> Dict[str, Any]:
        data = self._request("GET", "/config")
        config = data.get("config")
        return config if isinstance(config, dict) else {}

    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        if not updates:
            raise ValueError("没有需要更新的配置")
        return self._request("POST", "/config", json_body=updates)

    def restart(self) -> Dict[str, Any]:
        data = self._request("POST", "/restart")
        self.logout()
        return data

    def ai_start(self) -> Dict[str, Any]:
        return self._request("POST", "/ai/start")

    def ai_stop(self) -> Dict[str, Any]:
        return self._request("POST", "/ai/stop")

    def ai_trigger(
        self,
        device: str,
        date: Optional[str] = None,
        timezone_offset: int = 8,
    ) -> Dict[str, Any]:
        device = (device or "").strip()
        if not device:
            raise ValueError("设备 ID 不能为空")
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise ValueError("日期格式必须为 YYYY-MM-DD")
        try:
            offset = int(timezone_offset)
        except (TypeError, ValueError):
            raise ValueError("时区偏移必须是整数")

        body: Dict[str, Any] = {"timezoneOffset": offset}
        if date:
            body["date"] = date
        return self._request(
            "POST",
            f"/ai/trigger/{quote(device, safe='')}",
            json_body=body,
        )

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        auth: bool = True,
        timeout: float = 8.0,
    ) -> Dict[str, Any]:
        base = self.admin_base_url()
        if not is_transport_secure(base):
            raise ApiError("管理功能要求 HTTPS（本机地址除外）")

        headers = {"Accept": "application/json"}
        if auth:
            with self._lock:
                token = self._token
            if not token:
                raise AdminAuthError("请先登录")
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = self._session.request(
                method,
                f"{base}{path}",
                json=json_body,
                headers=headers,
                timeout=timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"网络请求失败: {exc}") from exc

        data = self._parse_json(response)
        if response.status_code in (401, 403):
            if auth:
                self.logout()
                raise AdminAuthError("登录已失效，请重新登录", status=response.status_code)
            raise ApiError(
                extract_error(data) or "用户名或密码错误",
                status=response.status_code,
            )
        if not 200 <= response.status_code < 300:
            message = extract_error(data) or f"HTTP {response.status_code}"
            raise ApiError(message, status=response.status_code)
        if not isinstance(data, dict):
            raise ApiError("服务端响应不是有效 JSON 对象")
        if data.get("success") is False:
            raise ApiError(extract_error(data) or "操作失败", status=response.status_code)
        return data

    @staticmethod
    def _parse_json(response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None
