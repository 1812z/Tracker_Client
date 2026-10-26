"""前台应用识别与窗口标题规则。"""

import logging
from typing import List, Optional, Tuple

import psutil
import win32gui
import win32process

logger = logging.getLogger(__name__)

STATE_SUSPENDED = "设备待机"
STATE_SCREEN_OFF = "屏幕关闭"
STATE_SHUTDOWN = "设备关机"
STATE_DESKTOP = "桌面"
STATE_UNKNOWN = "未知"
STATE_SYSTEM = "系统进程"

NON_RUNNING_STATES = {STATE_SUSPENDED, STATE_SCREEN_OFF, STATE_SHUTDOWN}

# 顺序敏感：具体工具在前，通用词在后，避免“设置”之类误判。
TITLE_RULES: List[Tuple[Tuple[str, ...], str]] = [
    (("任务管理器", "task manager"), "任务管理器"),
    (("设备管理器", "device manager"), "设备管理器"),
    (("磁盘管理", "disk management"), "磁盘管理"),
    (("事件查看器", "event viewer"), "事件查看器"),
    (("任务计划程序", "task scheduler"), "任务计划程序"),
    (("计算机管理", "computer management"), "计算机管理"),
    (("本地组策略编辑器", "group policy"), "本地组策略编辑器"),
    (("注册表编辑器", "registry editor"), "注册表编辑器"),
    (("系统配置", "system configuration"), "系统配置"),
    (("命令提示符", "command prompt"), "命令提示符"),
    (("powershell",), "PowerShell"),
    (("windows terminal",), "Windows Terminal"),
    (("文件资源管理器", "file explorer"), "文件资源管理器"),
    (("控制面板", "control panel"), "控制面板"),
    (("截图工具", "snipping tool"), "截图工具"),
    (("写字板", "wordpad"), "写字板"),
    (("计算器", "calculator"), "计算器"),
    (("画图", "paint"), "画图"),
    (("便笺", "sticky notes"), "便笺"),
    (("记事本", "notepad"), "记事本"),
    (("onenote",), "OneNote"),
    (("outlook",), "Outlook"),
    (("powerpoint",), "PowerPoint"),
    (("excel",), "Excel"),
    (("word",), "Word"),
    (("opera",), "Opera浏览器"),
    (("brave",), "Brave浏览器"),
    (("vivaldi",), "Vivaldi浏览器"),
    (("safari",), "Safari浏览器"),
    (("edge",), "Edge浏览器"),
    (("chrome",), "Chrome浏览器"),
    (("firefox",), "Firefox浏览器"),
    (("服务", "services"), "服务"),
    (("设置", "settings"), "系统设置"),
]


def resolve_title(window_title: str) -> Optional[str]:
    if not window_title:
        return None
    lowered = window_title.lower()
    for keywords, display_name in TITLE_RULES:
        if any(keyword in lowered for keyword in keywords):
            return display_name
    return None


def get_foreground_app(mapping, suspended: bool = False, screen_off: bool = False) -> str:
    if suspended:
        return STATE_SUSPENDED
    if screen_off:
        return STATE_SCREEN_OFF

    try:
        window = win32gui.GetForegroundWindow()
    except Exception as exc:
        logger.debug("获取前台窗口失败: %s", exc)
        return STATE_UNKNOWN
    if not window:
        return STATE_DESKTOP

    try:
        window_title = win32gui.GetWindowText(window)
    except Exception:
        window_title = ""

    try:
        _, pid = win32process.GetWindowThreadProcessId(window)
    except Exception:
        pid = 0
    if not pid:
        return STATE_DESKTOP

    try:
        exe_name = psutil.Process(pid).name()
        mapped_name = mapping.lookup(exe_name)
        if mapped_name == exe_name:
            resolved = resolve_title(window_title)
            if resolved:
                return resolved
        return mapped_name
    except Exception as exc:
        logger.debug("读取前台进程失败: %s", exc)
        if window_title:
            return resolve_title(window_title) or window_title
        return STATE_SYSTEM
