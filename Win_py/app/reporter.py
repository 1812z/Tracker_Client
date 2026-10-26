"""上报调度：最新状态优先、失败退避、急救上报。"""

import logging
import queue
import threading
import time
from typing import Any, Dict, Optional, Tuple

from app.battery import get_battery_status

logger = logging.getLogger(__name__)

RETRY_INITIAL = 5.0
RETRY_MAX = 60.0


class Reporter:
    def __init__(self, config, client, battery_provider=get_battery_status):
        self._config = config
        self._client = client
        self._battery_provider = battery_provider
        self._lock = threading.Lock()
        self._queue = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pending: Optional[Tuple[str, bool]] = None
        self._last_success: Optional[str] = None
        self._failed_app: Optional[str] = None
        self._retry_after = 0.0
        self._retry_delay = RETRY_INITIAL
        self._warned_unconfigured = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, name="ReporterWorker", daemon=True)
        self._thread.start()

    def stop(self, drain_ms: int = 1500) -> None:
        self._stop_event.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(None)
            except queue.Empty:
                pass
        if self._thread is not None:
            self._thread.join(max(0, drain_ms) / 1000)
            self._thread = None

    def submit(self, app_name: str, running: bool) -> None:
        if not self._should_report():
            return

        now = time.monotonic()
        with self._lock:
            if app_name == self._last_success:
                return
            if self._pending == (app_name, running):
                return
            if app_name == self._failed_app and now < self._retry_after:
                return
            self._pending = (app_name, running)

        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait((app_name, running))
        except queue.Full:
            pass

    def send_critical(self, app_name: str, running: bool, timeout: float = 2.0) -> None:
        """单次直发，用于启动、退出、休眠、息屏、关机等关键状态。"""
        thread = threading.Thread(
            target=self._send_once,
            args=(app_name, running),
            name="ReporterCritical",
            daemon=True,
        )
        thread.start()
        if timeout > 0:
            thread.join(timeout)

    def _send_once(self, app_name: str, running: bool) -> None:
        if not self._should_report():
            return
        ok, message = self._client.post_report(
            self._build_payload(app_name, running),
            max_retries=1,
            timeout=(2.0, 3.0),
        )
        with self._lock:
            if ok:
                self._last_success = app_name
                self._pending = None
                self._failed_app = None
                self._retry_after = 0.0
                self._retry_delay = RETRY_INITIAL
        if ok:
            logger.info("关键状态上报成功: %s, running: %s", app_name, running)
        else:
            logger.warning("关键状态上报失败: %s (%s)", app_name, message)

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break

            app_name, running = item
            payload = self._build_payload(app_name, running)
            ok, message = self._client.post_report(payload)

            if ok:
                with self._lock:
                    self._last_success = app_name
                    if self._pending == (app_name, running):
                        self._pending = None
                    self._failed_app = None
                    self._retry_after = 0.0
                    self._retry_delay = RETRY_INITIAL
                logger.info("上报成功: %s, running: %s", app_name, running)
            else:
                with self._lock:
                    if self._pending == (app_name, running):
                        self._pending = None
                    self._failed_app = app_name
                    self._retry_after = time.monotonic() + self._retry_delay
                    self._retry_delay = min(RETRY_MAX, self._retry_delay * 2)
                logger.warning("上报失败: %s (%s)", app_name, message)

    def _should_report(self) -> bool:
        if not self._config.get("report_enabled", True):
            return False
        if self._config.is_report_configured():
            return True

        with self._lock:
            if not self._warned_unconfigured:
                logger.warning("上报未配置：请填写 API 地址、密钥和设备 ID")
                self._warned_unconfigured = True
        return False

    def _build_payload(self, app_name: str, running: bool) -> Dict[str, Any]:
        snapshot = self._config.snapshot()
        payload: Dict[str, Any] = {
            "secret": snapshot.get("secret_key", ""),
            "device": snapshot.get("device_id", ""),
            "app_name": app_name,
            "running": bool(running),
        }

        try:
            battery_level, is_charging = self._battery_provider()
        except Exception as exc:
            logger.debug("读取电池状态失败: %s", exc)
            battery_level, is_charging = None, None

        if battery_level is not None and 1 <= battery_level <= 100:
            payload["batteryLevel"] = int(battery_level)
            payload["isCharging"] = bool(is_charging)
        return payload
