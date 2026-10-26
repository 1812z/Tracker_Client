"""通用异步请求任务。"""

import logging

from PyQt5.QtCore import QThread, pyqtSignal

from app.admin_api import AdminAuthError
from app.server_api import ApiError

logger = logging.getLogger(__name__)


class ApiTask(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)
    auth_failed = pyqtSignal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except AdminAuthError as exc:
            self.auth_failed.emit(str(exc) or "登录已失效，请重新登录")
        except (ApiError, ValueError) as exc:
            self.failed.emit(str(exc) or "请求失败")
        except Exception as exc:
            logger.exception("异步请求异常")
            self.failed.emit(f"请求失败: {exc}")
        else:
            self.finished_ok.emit(result)
