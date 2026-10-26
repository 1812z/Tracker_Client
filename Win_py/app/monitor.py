"""监控线程：只采集前台状态，不直接阻塞网络。"""

import logging
import threading

from PyQt5.QtCore import QThread, pyqtSignal

from app.foreground import NON_RUNNING_STATES, get_foreground_app

logger = logging.getLogger(__name__)


class MonitorThread(QThread):
    app_changed = pyqtSignal(str)

    def __init__(self, config, mapping, reporter, state, parent=None):
        super().__init__(parent)
        self._config = config
        self._mapping = mapping
        self._reporter = reporter
        self._state = state
        self._stop_event = threading.Event()
        self._last_app = None

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                app_name = get_foreground_app(
                    self._mapping,
                    suspended=self._state.suspended,
                    screen_off=self._state.screen_off,
                )
                self._reporter.submit(app_name, app_name not in NON_RUNNING_STATES)
                if app_name != self._last_app:
                    self._last_app = app_name
                    self.app_changed.emit(app_name)
            except Exception:
                logger.exception("监控线程错误")

            self._stop_event.wait(self._interval())

    def _interval(self) -> int:
        try:
            value = int(self._config.get("monitor_interval", 1))
        except (TypeError, ValueError):
            value = 1
        return max(1, min(3600, value))

    def stop(self, wait_ms: int = 3000) -> None:
        self._stop_event.set()
        self.wait(wait_ms)
