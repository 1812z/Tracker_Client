"""单实例：互斥量 + 激活已运行窗口。"""

import logging

logger = logging.getLogger(__name__)


class SingleInstance:
    def __init__(self, name: str = "RunTimeTracker_Application_Mutex"):
        self._name = name
        self._mutex = None

    def acquire(self) -> bool:
        try:
            import win32api
            import win32event
            import winerror

            self._mutex = win32event.CreateMutex(None, True, self._name)
            return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS
        except Exception as exc:
            logger.warning("单实例检查失败，将继续启动: %s", exc)
            return True

    def activate_existing(self, window_title: str) -> bool:
        try:
            import win32con
            import win32gui
        except Exception as exc:
            logger.warning("激活已有窗口失败: %s", exc)
            return False

        found = [False]

        def callback(hwnd, _):
            if win32gui.GetWindowText(hwnd) != window_title:
                return True
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
            found[0] = True
            return False

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as exc:
            logger.warning("枚举窗口失败: %s", exc)
        return found[0]

    def release(self) -> None:
        if not self._mutex:
            return
        try:
            import win32api

            win32api.CloseHandle(self._mutex)
        except Exception:
            pass
        finally:
            self._mutex = None
