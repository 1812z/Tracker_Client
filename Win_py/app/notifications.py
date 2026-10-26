"""Windows 通知：优先使用系统 Toast，失败时回退到托盘气泡。"""

import hashlib
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from app import APP_DISPLAY_NAME
from app.app_identity import APP_USER_MODEL_ID

logger = logging.getLogger(__name__)

_shortcut_ready = False
_LOGO_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif")

TOAST_XML = (
    "<toast>"
    "<visual><binding template='ToastGeneric'>{logo}{texts}</binding></visual>"
    "</toast>"
)


def _start_menu_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def _ensure_shortcut(icon_path: Optional[Path]) -> bool:
    """创建带 AppUserModel.ID 的开始菜单快捷方式。

    未打包的 Win32 程序要显示原生 Toast，Windows 要求 AUMID 能通过开始菜单
    快捷方式解析到显示名，否则通知标题会退化成占位文本。
    """
    global _shortcut_ready
    if _shortcut_ready:
        return True

    lnk = _start_menu_dir() / "RunTimeTracker.lnk"
    try:
        import win32com.client
        from win32com.propsys import propsys, pscon

        lnk.parent.mkdir(parents=True, exist_ok=True)

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(lnk))
        if getattr(sys, "frozen", False):
            shortcut.Targetpath = sys.executable
            shortcut.Arguments = ""
            shortcut.WorkingDirectory = str(Path(sys.executable).parent)
        else:
            shortcut.Targetpath = sys.executable
            shortcut.Arguments = f'"{Path(sys.argv[0]).resolve()}"'
            shortcut.WorkingDirectory = str(Path(__file__).resolve().parent.parent)
        if icon_path is not None:
            shortcut.IconLocation = str(icon_path)
        shortcut.Description = APP_DISPLAY_NAME
        shortcut.save()

        store = propsys.SHGetPropertyStoreFromParsingName(
            str(lnk), None, 2, propsys.IID_IPropertyStore
        )
        store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(APP_USER_MODEL_ID))
        store.Commit()

        _shortcut_ready = True
        return True
    except Exception as exc:
        # 快捷方式已存在时（例如目标目录只读）仍可正常弹出 Toast，不必回退。
        if lnk.exists():
            logger.debug("刷新通知快捷方式失败，沿用已有快捷方式: %s", exc)
            _shortcut_ready = True
            return True
        logger.warning("创建通知快捷方式失败，将回退到托盘气泡: %s", exc)
        return False


def _toast_logo(logo_path: Optional[Path]) -> str:
    """返回可用于 Toast 的应用图标 URL；没有可用图片时返回空串。

    Windows 的 <image src> 只能加载纯 ASCII 路径，项目目录名（如「图标.png」）
    通常含中文，所以这里把图片复制到临时目录后再用哈希命名的 ASCII 路径引用。
    """
    if logo_path is None:
        return ""
    path = Path(logo_path)
    suffix = path.suffix.lower()
    if not path.exists() or suffix not in _LOGO_SUFFIXES:
        return ""
    try:
        data = path.read_bytes()
    except OSError:
        return ""

    digest = hashlib.sha1(data).hexdigest()[:16]
    target = Path(tempfile.gettempdir()) / f"runtime_tracker_toast_{digest}{suffix}"
    if not str(target).isascii():
        return ""
    try:
        if not target.exists() or target.stat().st_size != len(data):
            target.write_bytes(data)
        return target.as_uri()
    except (OSError, ValueError):
        return ""


def _build_xml(title: Optional[str], message: str, logo_url: str = "") -> str:
    texts = []
    if title and title != APP_DISPLAY_NAME:
        texts.append(f"<text>{_escape(title)}</text>")
    texts.append(f"<text>{_escape(message)}</text>")

    logo = ""
    if logo_url:
        logo = (
            '<image placement="appLogoOverride" hint-crop="square" '
            f'src="{_escape(logo_url)}"/>'
        )
    return TOAST_XML.format(texts="".join(texts), logo=logo)


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def notify(
    message: str,
    title: Optional[str] = None,
    tray_icon=None,
    icon_path: Optional[Path] = None,
    logo_path: Optional[Path] = None,
) -> bool:
    """发送系统通知；成功返回 True。"""
    if sys.platform == "win32" and _ensure_shortcut(icon_path):
        try:
            from winrt.windows.data.xml.dom import XmlDocument
            from winrt.windows.ui.notifications import (
                ToastNotification,
                ToastNotificationManager,
            )

            document = XmlDocument()
            document.load_xml(_build_xml(title, message, _toast_logo(logo_path)))
            notifier = ToastNotificationManager.create_toast_notifier(APP_USER_MODEL_ID)
            notifier.show(ToastNotification(document))
            return True
        except Exception as exc:
            logger.debug("发送系统通知失败，回退到托盘气泡: %s", exc)

    if tray_icon is not None:
        try:
            from PyQt5.QtWidgets import QSystemTrayIcon

            tray_icon.showMessage(
                APP_DISPLAY_NAME,
                message,
                QSystemTrayIcon.Information,
                3000,
            )
            return True
        except Exception:
            logger.debug("托盘气泡通知失败", exc_info=True)
    return False
