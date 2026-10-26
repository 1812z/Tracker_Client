"""只读查询客户端：devices / recent / stats / weekly / ip。"""

import logging
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlsplit, urlunsplit

import requests

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail


class ApiNotConfigured(ApiError):
    pass


def extract_error(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("error", "message", "details"):
            value = data.get(key)
            if value:
                return str(value)
    return ""


def derive_base_url(api_url: str) -> str:
    """从上报地址推导服务端基地址，例如 https://host/api -> https://host。"""
    api_url = (api_url or "").strip()
    if not api_url:
        raise ApiNotConfigured("未配置 API 地址")

    parts = urlsplit(api_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ApiNotConfigured("API 地址格式不正确")

    path = parts.path.rstrip("/")
    if path.lower().endswith("/api"):
        path = path[:-4]
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


class ServerAPI:
    def __init__(self, config, session=None):
        self._config = config
        self._session = session or requests.Session()
        self._lock = threading.Lock()

    def _base_url(self) -> str:
        return derive_base_url(str(self._config.get("api_url", "") or ""))

    def _device(self) -> str:
        device = str(self._config.get("device_id", "") or "").strip()
        if not device:
            raise ApiNotConfigured("未配置设备 ID")
        return device

    @staticmethod
    def _quote_device(device: str) -> str:
        return quote(device, safe="")

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, timeout: float = 5.0) -> Any:
        url = f"{self._base_url()}{path}"
        try:
            with self._lock:
                response = self._session.get(
                    url,
                    params=params,
                    timeout=timeout,
                    headers={"Accept": "application/json"},
                )
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"网络请求失败: {exc}") from exc

        data = self._parse_json(response)
        if not 200 <= response.status_code < 300:
            message = extract_error(data) or f"HTTP {response.status_code}"
            raise ApiError(message, status=response.status_code)

        if data is None:
            raise ApiError("服务端响应不是有效 JSON")
        if isinstance(data, dict):
            if data.get("success") is False:
                raise ApiError(extract_error(data) or "服务端返回失败", status=response.status_code)
            if "data" in data:
                return data["data"]
        return data

    @staticmethod
    def _parse_json(response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def fetch_devices(self) -> List[Dict[str, Any]]:
        data = self._get("/api/devices")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("devices", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    def fetch_recent(self, device: Optional[str] = None) -> List[Dict[str, Any]]:
        device = device or self._device()
        data = self._get(f"/api/recent/{self._quote_device(device)}")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("data", "records"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    def fetch_stats(self, device: Optional[str] = None, date: Optional[str] = None) -> Dict[str, Any]:
        device = device or self._device()
        params = {"date": date} if date else None
        data = self._get(f"/api/stats/{self._quote_device(device)}", params=params)
        return data if isinstance(data, dict) else {}

    def fetch_weekly(
        self,
        device: Optional[str] = None,
        week_offset: int = 0,
        app_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        device = device or self._device()
        params: Dict[str, Any] = {"weekOffset": int(week_offset)}
        if app_name:
            params["appName"] = app_name
        data = self._get(f"/api/weekly/{self._quote_device(device)}", params=params)
        return data if isinstance(data, dict) else {}

    def fetch_monthly(
        self,
        device: Optional[str] = None,
        month_offset: int = 0,
        app_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        device = device or self._device()
        params: Dict[str, Any] = {"monthOffset": int(month_offset)}
        if app_name:
            params["appName"] = app_name
        data = self._get(f"/api/monthly/{self._quote_device(device)}", params=params)
        return data if isinstance(data, dict) else {}

    def test_connection(self) -> Dict[str, Any]:
        data = self._get("/api/ip", timeout=5.0)
        return data if isinstance(data, dict) else {}
