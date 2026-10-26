"""开机自启：HKCU Run 项。"""

import logging
import sys
from pathlib import Path

import winreg

logger = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "RunTimeTracker"


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'

    script = Path(sys.argv[0]).resolve()
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else python
    return f'"{executable}" "{script}" --minimized'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("读取开机自启配置失败: %s", exc)
        return False


def enable() -> None:
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
    except OSError as exc:
        raise RuntimeError(f"设置开机自启失败: {exc}") from exc


def disable() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise RuntimeError(f"关闭开机自启失败: {exc}") from exc


def reconcile(enabled: bool) -> None:
    """按配置对齐注册表状态（仅打包模式调用）。"""
    try:
        if enabled and not is_enabled():
            enable()
            logger.info("已按配置启用开机自启")
        elif not enabled and is_enabled():
            disable()
            logger.info("已按配置关闭开机自启")
    except RuntimeError as exc:
        logger.warning("同步开机自启失败: %s", exc)
