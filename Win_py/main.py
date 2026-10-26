"""RunTime Tracker 入口。"""

import argparse
import logging
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from app import APP_DISPLAY_NAME, APP_NAME, __version__
from app import app_identity, autostart
from app.admin_api import AdminAPI
from app.api_client import ApiClient
from app.app_mapping import AppMapping
from app.config import AppConfig
from app.logging_setup import apply_log_retention, setup_logging
from app.paths import (
    ensure_user_dirs,
    is_frozen,
    logs_dir,
    migrate_legacy_data,
    resource_path,
)
from app.reporter import Reporter
from app.server_api import ServerAPI
from app.single_instance import SingleInstance
from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_DISPLAY_NAME)
    parser.add_argument("--minimized", action="store_true", help="启动后仅驻留系统托盘")
    return parser.parse_args()


def _apply_theme(config: AppConfig) -> None:
    theme = int(config.get("theme", 0))
    if theme == 1:
        setTheme(Theme.LIGHT)
    elif theme == 2:
        setTheme(Theme.DARK)
    else:
        setTheme(Theme.AUTO)


def _cleanup_logs(config: AppConfig) -> None:
    try:
        days = int(config.get("log_retention_days", 30))
        count = int(config.get("log_retention_count", 30))
    except (TypeError, ValueError):
        days, count = 30, 30
    try:
        deleted = apply_log_retention(logs_dir(), days, count)
        if deleted:
            logger.info("已清理 %s 个历史日志文件", deleted)
    except Exception:
        logger.exception("清理历史日志失败")


def main() -> int:
    args = _parse_args()

    icon_ico = resource_path("图标.ico")
    icon_png = resource_path("图标.png")
    # 注册表里的通知图标需要长期存在的路径：打包版用 exe 自身，开发版用项目图标。
    identity_icon = Path(sys.executable) if is_frozen() else (
        icon_ico if icon_ico.exists() else icon_png
    )
    app_identity.register(identity_icon)

    instance = SingleInstance(f"{APP_NAME}_Application_Mutex")
    if not instance.acquire():
        instance.activate_existing(APP_DISPLAY_NAME)
        return 0

    migrate_legacy_data()
    ensure_user_dirs()
    setup_logging(logs_dir(), cleanup=False)

    config = AppConfig()
    config.load()
    _cleanup_logs(config)

    if is_frozen():
        autostart.reconcile(bool(config.get("auto_start", False)))

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("CSSQY")

    icon_path = icon_ico
    if not icon_path.exists():
        icon_path = icon_png
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    _apply_theme(config)

    mapping = AppMapping()
    mapping.load()

    reporter = Reporter(config, ApiClient(config))
    reporter.start()

    server_api = ServerAPI(config)
    admin_api = AdminAPI(config)

    window = MainWindow(
        config=config,
        mapping=mapping,
        reporter=reporter,
        server_api=server_api,
        admin_api=admin_api,
        log_dir=logs_dir(),
        start_minimized=args.minimized,
    )
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    if not args.minimized:
        window.show()

    logger.info("应用启动完成，版本 %s", __version__)

    try:
        exit_code = app.exec_()
    finally:
        reporter.stop()
        instance.release()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
