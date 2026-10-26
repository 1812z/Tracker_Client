"""写入客户端：POST /api，带退避重试与错误解析。"""

import logging
import threading
import time
from typing import Any, Dict, Tuple

import requests

logger = logging.getLogger(__name__)


def extract_error(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("error", "message", "details"):
            value = data.get(key)
            if value:
                return str(value)
    return ""


class ApiClient:
    def __init__(self, config, session=None):
        self._config = config
        self._session = session or requests.Session()
        self._lock = threading.Lock()

    def post_report(self, payload: Dict[str, Any], max_retries: int = 3, timeout=(3.05, 5.0)) -> Tuple[bool, str]:
        api_url = str(self._config.get("api_url", "") or "").strip()
        if not api_url:
            return False, "未配置 API 地址"

        last_error = "未知错误"
        for attempt in range(max(1, max_retries)):
            try:
                with self._lock:
                    response = self._session.post(api_url, json=payload, timeout=timeout)
            except requests.exceptions.RequestException as exc:
                last_error = f"网络请求失败: {exc}"
                logger.warning("上报请求异常 (%s/%s): %s", attempt + 1, max_retries, exc)
            else:
                if 200 <= response.status_code < 300:
                    try:
                        data = response.json()
                    except ValueError:
                        return False, "服务端响应不是有效 JSON"
                    if isinstance(data, dict) and data.get("success") is True:
                        return True, ""
                    return False, extract_error(data) or "服务端返回失败"
                if 400 <= response.status_code < 500:
                    try:
                        data = response.json()
                    except ValueError:
                        data = None
                    message = extract_error(data) or response.text[:200]
                    return False, f"HTTP {response.status_code}: {message}"
                last_error = f"HTTP {response.status_code}"
                logger.warning("上报失败 HTTP %s (%s/%s)", response.status_code, attempt + 1, max_retries)

            if attempt < max_retries - 1:
                time.sleep(1 if attempt == 0 else 2)

        return False, last_error
