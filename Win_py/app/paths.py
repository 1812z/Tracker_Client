"""路径管理：区分只读资源与用户数据目录。"""

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

LEGACY_CONFIG_NAME = "config.json"
LEGACY_APPS_NAME = "apps.json"
PENDING_SHUTDOWN_NAME = "pending_shutdown.json"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resource_path(name: str) -> Path:
    """打包后从 _MEIPASS 读取只读资源，开发模式从项目根读取。"""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        base = project_root()
    return base / name


def user_data_dir() -> Path:
    """用户可写目录：打包后使用 %APPDATA%，开发模式使用项目根。"""
    if is_frozen():
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "RunTimeTracker"
        return Path.home() / ".runtimetracker"
    return project_root()


def config_path() -> Path:
    return user_data_dir() / LEGACY_CONFIG_NAME


def apps_path() -> Path:
    return user_data_dir() / LEGACY_APPS_NAME


def logs_dir() -> Path:
    return user_data_dir() / "logs"


def pending_shutdown_path() -> Path:
    """关机上报的落盘标记：发送失败时保留，下次启动补发。"""
    return user_data_dir() / PENDING_SHUTDOWN_NAME


def ensure_user_dirs() -> None:
    try:
        user_data_dir().mkdir(parents=True, exist_ok=True)
        logs_dir().mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("创建用户数据目录失败: %s", exc)


def migrate_legacy_data() -> None:
    """打包模式下，把 exe 同目录的旧配置/映射迁移到用户数据目录。"""
    if not is_frozen():
        return

    exe_dir = Path(sys.executable).resolve().parent
    target_dir = user_data_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("创建用户数据目录失败，跳过迁移: %s", exc)
        return

    for name in (LEGACY_CONFIG_NAME, LEGACY_APPS_NAME):
        source = exe_dir / name
        target = target_dir / name
        if not source.exists() or target.exists():
            continue
        try:
            shutil.copy2(source, target)
            logger.info("已迁移旧文件 %s -> %s", source, target)
        except OSError as exc:
            logger.warning("迁移旧文件失败 %s: %s", source, exc)
