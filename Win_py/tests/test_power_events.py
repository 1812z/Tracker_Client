import ctypes
from ctypes import wintypes

from app.power_events import (
    WM_ENDSESSION,
    WM_QUERYENDSESSION,
    PowerEvents,
)


def _msg(message: int, wparam: int = 0, lparam: int = 0) -> wintypes.MSG:
    msg = wintypes.MSG()
    msg.hwnd = 0
    msg.message = message
    msg.wParam = wparam
    msg.lParam = lparam
    return msg


def test_session_end_fires_once_for_query_and_end_session():
    events = []
    power = PowerEvents(on_session_end=lambda: events.append("end"))

    query = _msg(WM_QUERYENDSESSION)
    assert power.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(query)) == (False, 0)
    assert events == ["end"]

    # WM_ENDSESSION 紧接着到达时不应重复上报
    end = _msg(WM_ENDSESSION, 1)
    power.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(end))
    assert events == ["end"]


def test_session_end_ignored_for_other_event_types():
    events = []
    power = PowerEvents(on_session_end=lambda: events.append("end"))

    query = _msg(WM_QUERYENDSESSION)
    power.nativeEventFilter(b"xcb_generic_event_t", ctypes.addressof(query))
    assert events == []
