"""系统电源/会话事件：休眠、恢复、息屏、关机。"""

import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable, Optional

from PyQt5.QtCore import QAbstractNativeEventFilter

logger = logging.getLogger(__name__)

WM_QUERYENDSESSION = 0x0011
WM_POWERBROADCAST = 0x0218
PBT_APMSUSPEND = 0x0004
PBT_APMRESUMEAUTOMATIC = 0x0012
PBT_POWERSETTINGCHANGE = 0x8013
DEVICE_NOTIFY_WINDOW_HANDLE = 0


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


CONSOLE_DISPLAY_STATE = GUID(
    0x6FE69556,
    0x704A,
    0x47A0,
    (ctypes.c_ubyte * 8)(0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47),
)


class POWERBROADCAST_SETTING(ctypes.Structure):
    _fields_ = [
        ("PowerSetting", GUID),
        ("DataLength", wintypes.DWORD),
        ("Data", ctypes.c_ubyte * 4),
    ]


class SystemState:
    def __init__(self):
        self._lock = threading.Lock()
        self._suspended = False
        self._screen_off = False

    @property
    def suspended(self) -> bool:
        with self._lock:
            return self._suspended

    @property
    def screen_off(self) -> bool:
        with self._lock:
            return self._screen_off

    def set_suspended(self, value: bool) -> None:
        with self._lock:
            self._suspended = bool(value)

    def set_screen_off(self, value: bool) -> None:
        with self._lock:
            self._screen_off = bool(value)


def _guid_equal(left: GUID, right: GUID) -> bool:
    return ctypes.string_at(ctypes.byref(left), ctypes.sizeof(GUID)) == ctypes.string_at(
        ctypes.byref(right), ctypes.sizeof(GUID)
    )


class PowerEvents(QAbstractNativeEventFilter):
    def __init__(
        self,
        on_suspend: Optional[Callable[[], None]] = None,
        on_resume: Optional[Callable[[], None]] = None,
        on_display_off: Optional[Callable[[], None]] = None,
        on_display_on: Optional[Callable[[], None]] = None,
        on_session_end: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._on_suspend = on_suspend
        self._on_resume = on_resume
        self._on_display_off = on_display_off
        self._on_display_on = on_display_on
        self._on_session_end = on_session_end
        self._notify_handle = None
        self._hwnd = None
        self._suspended = False
        self._screen_off = False
        self._session_end_fired = False

    def register(self, hwnd: int) -> bool:
        self._hwnd = hwnd
        try:
            user32 = ctypes.windll.user32
            user32.RegisterPowerSettingNotification.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(GUID),
                wintypes.DWORD,
            ]
            user32.RegisterPowerSettingNotification.restype = wintypes.HANDLE
            handle = user32.RegisterPowerSettingNotification(
                wintypes.HWND(hwnd),
                ctypes.byref(CONSOLE_DISPLAY_STATE),
                DEVICE_NOTIFY_WINDOW_HANDLE,
            )
        except Exception as exc:
            logger.warning("注册息屏通知失败: %s", exc)
            return False

        if not handle:
            logger.warning("注册息屏通知失败，屏幕关闭状态将不可用")
            return False
        self._notify_handle = handle
        return True

    def unregister(self) -> None:
        if not self._notify_handle:
            return
        try:
            user32 = ctypes.windll.user32
            user32.UnregisterPowerSettingNotification.argtypes = [wintypes.HANDLE]
            user32.UnregisterPowerSettingNotification.restype = wintypes.BOOL
            user32.UnregisterPowerSettingNotification(self._notify_handle)
        except Exception as exc:
            logger.debug("注销息屏通知失败: %s", exc)
        finally:
            self._notify_handle = None

    def nativeEventFilter(self, eventType, message):
        if eventType not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0

        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_QUERYENDSESSION:
                self._fire_session_end()
            elif msg.message == WM_POWERBROADCAST:
                if msg.wParam == PBT_APMSUSPEND:
                    self._handle_suspend()
                elif msg.wParam == PBT_APMRESUMEAUTOMATIC:
                    self._handle_resume()
                elif msg.wParam == PBT_POWERSETTINGCHANGE:
                    self._handle_power_setting(msg.lParam)
        except Exception as exc:
            logger.debug("处理系统电源消息失败: %s", exc)

        return False, 0

    def _fire_session_end(self) -> None:
        if self._session_end_fired:
            return
        self._session_end_fired = True
        if self._on_session_end:
            self._on_session_end()

    def _handle_suspend(self) -> None:
        if self._suspended:
            return
        self._suspended = True
        if self._on_suspend:
            self._on_suspend()

    def _handle_resume(self) -> None:
        if not self._suspended:
            return
        self._suspended = False
        if self._on_resume:
            self._on_resume()

    def _handle_power_setting(self, lparam: int) -> None:
        setting = ctypes.cast(
            ctypes.c_void_p(lparam), ctypes.POINTER(POWERBROADCAST_SETTING)
        ).contents
        if not _guid_equal(setting.PowerSetting, CONSOLE_DISPLAY_STATE):
            return
        if setting.DataLength < 1:
            return

        state = int(setting.Data[0])
        if state == 0 and not self._screen_off:
            self._screen_off = True
            if self._on_display_off:
                self._on_display_off()
        elif state == 1 and self._screen_off:
            self._screen_off = False
            if self._on_display_on:
                self._on_display_on()
