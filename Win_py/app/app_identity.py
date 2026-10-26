"""Windows 应用标识：让通知、任务栏显示正确的应用名称与图标。"""

import logging
import sys
from pathlib import Path
from typing import Optional

from app import APP_DISPLAY_NAME, APP_NAME

logger = logging.getLogger(__name__)

APP_USER_MODEL_ID = f"CSSQY.{APP_NAME}"
_AUMID_KEY = r"Software\Classes\AppUserModelId"


def register(icon_path: Optional[Path] = None) -> None:
    """注册 AppUserModelID，Windows 才能解析通知标题与图标。

    仅设置 SetCurrentProcessExplicitAppUserModelID 不够：如果对应的
    HKCU\\Software\\Classes\\AppUserModelId 项没有 DisplayName，
    Windows 通知会回退成 Microsoft.Explorer.Notification.{...} 之类的占位标题。
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
    except Exception:
        logger.debug("设置 AppUserModelID 失败", exc_info=True)

    try:
        import winreg

        key_path = f"{_AUMID_KEY}\\{APP_USER_MODEL_ID}"
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
            if icon_path is not None:
                try:
                    winreg.SetValueEx(
                        key, "IconUri", 0, winreg.REG_SZ, str(icon_path)
                    )
                except OSError as exc:
                    logger.debug("写入通知图标失败: %s", exc)
    except OSError as exc:
        logger.warning("注册应用通知标识失败: %s", exc)
