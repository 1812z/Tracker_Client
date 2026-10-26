"""配置模型：默认值合并、校验、原子保存。"""

import copy
import json
import logging
import os
import socket
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from app.paths import config_path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_url": "",
    "secret_key": "",
    "device_id": "",
    "report_enabled": True,
    "monitor_interval": 1,
    "theme": 0,
    "auto_start": False,
    "log_retention_days": 30,
    "log_retention_count": 30,
}

PLACEHOLDER_API_URLS = {"https://api.example.com", "http://api.example.com"}
PLACEHOLDER_SECRET = "your_secret_key"
PLACEHOLDER_DEVICE = "your_device_id"


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def validate_api_url(url: str) -> None:
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        raise ValueError("API 地址必须以 http:// 或 https:// 开头")


def validate_interval(value: Any) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("监控间隔必须是整数")
    if not 1 <= number <= 3600:
        raise ValueError("监控间隔必须在 1–3600 秒之间")
    return number


def validate_log_retention(days: Any, count: Any) -> tuple:
    try:
        days_value = int(str(days).strip())
        count_value = int(str(count).strip())
    except (TypeError, ValueError):
        raise ValueError("日志留存天数和数量必须是整数")
    if not 1 <= days_value <= 3650:
        raise ValueError("日志留存天数必须在 1–3650 天之间")
    if not 1 <= count_value <= 1000:
        raise ValueError("日志留存数量必须在 1–1000 个之间")
    return days_value, count_value


class AppConfig:
    """线程安全的配置对象。"""

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else config_path()
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> "AppConfig":
        with self._lock:
            data = copy.deepcopy(DEFAULT_CONFIG)
            if self._path.exists():
                try:
                    raw = json.loads(self._path.read_text(encoding="utf-8"))
                    if not isinstance(raw, dict):
                        raise ValueError("配置根节点必须是 JSON 对象")
                    data.update(raw)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    logger.error("加载配置失败，将使用默认配置: %s", exc)
                    self._backup_broken_file()
            self._data = data
            self._normalize_locked()
            self._save_locked()
        return self

    def _backup_broken_file(self) -> None:
        try:
            broken = self._path.with_name(self._path.name + ".bad")
            os.replace(self._path, broken)
            logger.warning("损坏的配置已备份为 %s", broken)
        except OSError as exc:
            logger.warning("备份损坏配置失败: %s", exc)

    def _normalize_locked(self) -> None:
        api_url = str(self._data.get("api_url", "") or "").strip()
        if api_url in PLACEHOLDER_API_URLS:
            api_url = ""
        self._data["api_url"] = api_url

        secret = str(self._data.get("secret_key", "") or "").strip()
        if secret == PLACEHOLDER_SECRET:
            secret = ""
        self._data["secret_key"] = secret

        device = str(self._data.get("device_id", "") or "").strip()
        if device in ("", PLACEHOLDER_DEVICE):
            device = self._generate_device_id()
        self._data["device_id"] = device

        self._data["report_enabled"] = _as_bool(
            self._data.get("report_enabled"), DEFAULT_CONFIG["report_enabled"]
        )
        self._data["auto_start"] = _as_bool(
            self._data.get("auto_start"), DEFAULT_CONFIG["auto_start"]
        )
        self._data["monitor_interval"] = _as_int(
            self._data.get("monitor_interval"), DEFAULT_CONFIG["monitor_interval"], 1, 3600
        )
        self._data["theme"] = _as_int(self._data.get("theme"), DEFAULT_CONFIG["theme"], 0, 2)
        self._data["log_retention_days"] = _as_int(
            self._data.get("log_retention_days"),
            DEFAULT_CONFIG["log_retention_days"],
            1,
            3650,
        )
        self._data["log_retention_count"] = _as_int(
            self._data.get("log_retention_count"),
            DEFAULT_CONFIG["log_retention_count"],
            1,
            1000,
        )
        self._data.pop("version", None)

    @staticmethod
    def _generate_device_id() -> str:
        hostname = socket.gethostname() or "device"
        return f"{hostname}-{uuid.uuid4().hex[:8]}"

    def ensure_device_id(self) -> str:
        with self._lock:
            current = str(self._data.get("device_id", "") or "").strip()
            if current and current != PLACEHOLDER_DEVICE:
                return current
            generated = self._generate_device_id()
            self._data["device_id"] = generated
            return generated

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data)

    def save(self) -> bool:
        with self._lock:
            return self._save_locked()

    def _save_locked(self) -> bool:
        temp_path = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.with_name(self._path.name + ".tmp")
            temp_path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(temp_path, self._path)
            return True
        except OSError as exc:
            logger.error("保存配置失败: %s", exc)
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            return False

    def is_report_configured(self) -> bool:
        with self._lock:
            api_url = str(self._data.get("api_url", "")).strip()
            secret = str(self._data.get("secret_key", "")).strip()
            device = str(self._data.get("device_id", "")).strip()
        return bool(api_url.startswith(("http://", "https://")) and secret and device)

    def is_query_configured(self) -> bool:
        with self._lock:
            api_url = str(self._data.get("api_url", "")).strip()
            device = str(self._data.get("device_id", "")).strip()
        return bool(api_url.startswith(("http://", "https://")) and device)
