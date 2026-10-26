"""主窗口：页面装配、托盘、监控与系统事件。"""

import logging

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QMenu,
    QSystemTrayIcon,
)
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
)

from app import APP_DISPLAY_NAME
from app.logging_setup import apply_log_retention
from app.monitor import MonitorThread
from app.notifications import notify
from app.paths import resource_path
from app.power_events import PowerEvents, SystemState
from ui.pages.about import AboutPage
from ui.pages.admin import AdminPage
from ui.pages.devices import DevicesPage
from ui.pages.home import HomePage
from ui.pages.logs import LogPage
from ui.pages.mapping import MappingPage
from ui.pages.recent import RecentPage
from ui.pages.settings import SettingsPage
from ui.pages.stats import StatsPage

logger = logging.getLogger(__name__)


class MainWindow(FluentWindow):
    def __init__(
        self,
        config,
        mapping,
        reporter,
        server_api,
        admin_api,
        log_dir,
        start_minimized: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._mapping = mapping
        self._reporter = reporter
        self._server_api = server_api
        self._admin_api = admin_api
        self._log_dir = log_dir
        self._state = SystemState()
        self._start_minimized = start_minimized
        self._quitting = False
        self._monitor_thread = None
        self._power = None

        self._init_ui()
        self._init_log_retention()
        self._init_tray()
        self._init_monitor()
        self._init_power()

        app = QApplication.instance()
        if app is not None:
            app.paletteChanged.connect(self._apply_theme)

        QTimer.singleShot(100, self._report_startup)

    def _init_ui(self) -> None:
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(920, 680)

        self.home_page = HomePage(self._config, self)
        self.stats_page = StatsPage(self._config, self._server_api, self)
        self.recent_page = RecentPage(self._config, self._server_api, self)
        self.devices_page = DevicesPage(self._config, self._server_api, self)
        self.mapping_page = MappingPage(self._mapping, self)
        self.log_page = LogPage(self._log_dir, self)
        self.settings_page = SettingsPage(self._config, self._server_api, self)
        self.admin_page = AdminPage(self._config, self._admin_api, self)
        self.about_page = AboutPage(self)

        self.addSubInterface(self.home_page, FluentIcon.HOME, "主页")
        self.addSubInterface(self.stats_page, FluentIcon.PIE_SINGLE, "统计")
        self.addSubInterface(self.recent_page, FluentIcon.HISTORY, "最近记录")
        self.addSubInterface(self.devices_page, FluentIcon.PEOPLE, "设备")
        self.addSubInterface(self.mapping_page, FluentIcon.EDIT, "应用映射")
        self.addSubInterface(self.log_page, FluentIcon.DOCUMENT, "日志")
        self.addSubInterface(
            self.settings_page, FluentIcon.SETTING, "配置", NavigationItemPosition.BOTTOM
        )
        self.addSubInterface(
            self.admin_page, FluentIcon.DEVELOPER_TOOLS, "管理", NavigationItemPosition.BOTTOM
        )
        self.addSubInterface(
            self.about_page, FluentIcon.INFO, "关于", NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.setCurrentItem("homePage")

        self.settings_page.theme_changed.connect(self._apply_theme)
        self.settings_page.config_saved.connect(self._on_config_saved)

    def _init_log_retention(self) -> None:
        self._log_cleanup_timer = QTimer(self)
        self._log_cleanup_timer.timeout.connect(self._cleanup_logs)
        self._log_cleanup_timer.start(6 * 60 * 60 * 1000)

    def _cleanup_logs(self) -> None:
        try:
            days = int(self._config.get("log_retention_days", 30))
            count = int(self._config.get("log_retention_count", 30))
        except (TypeError, ValueError):
            days, count = 30, 30

        try:
            deleted = apply_log_retention(self._log_dir, days, count)
        except Exception:
            logger.exception("清理历史日志失败")
            return

        if deleted:
            logger.info("已清理 %s 个历史日志文件", deleted)
            self.log_page.refresh_log_files()

    def _init_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = resource_path("图标.ico")
        if not icon_path.exists():
            icon_path = resource_path("图标.png")
        self._icon_path = icon_path if icon_path.exists() else None
        if self._icon_path is not None:
            self.tray_icon.setIcon(QIcon(str(self._icon_path)))
        self.tray_icon.setToolTip(APP_DISPLAY_NAME)

        menu = QMenu(self)
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self._show_window)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _init_monitor(self) -> None:
        self._monitor_thread = MonitorThread(
            self._config,
            self._mapping,
            self._reporter,
            self._state,
            self,
        )
        self._monitor_thread.app_changed.connect(self.home_page.set_app)
        self._monitor_thread.start()

    def _init_power(self) -> None:
        self._power = PowerEvents(
            on_suspend=self._on_suspend,
            on_resume=self._on_resume,
            on_display_off=self._on_display_off,
            on_display_on=self._on_display_on,
            on_session_end=self._on_session_end,
        )
        try:
            self._power.register(int(self.winId()))
        except Exception as exc:
            logger.warning("注册电源事件失败: %s", exc)

        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._power)

    def _report_startup(self) -> None:
        self._reporter.send_critical("程序启动", True, timeout=0.0)

    def _on_suspend(self) -> None:
        self._state.set_suspended(True)
        self._reporter.send_critical("设备待机", False, timeout=2.0)

    def _on_resume(self) -> None:
        self._state.set_suspended(False)

    def _on_display_off(self) -> None:
        self._state.set_screen_off(True)
        self._reporter.send_critical("屏幕关闭", False, timeout=2.0)

    def _on_display_on(self) -> None:
        self._state.set_screen_off(False)

    def _on_session_end(self) -> None:
        self._reporter.send_critical("设备关机", False, timeout=2.0)

    def _apply_theme(self) -> None:
        self.stats_page.apply_theme()
        self.log_page.apply_theme()

    def _on_config_saved(self) -> None:
        self.home_page.on_config_saved()
        self.stats_page.on_config_saved()
        self._cleanup_logs()

    def _show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._show_window()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
        notify(
            "应用已最小化到系统托盘，可从托盘图标重新打开。",
            tray_icon=self.tray_icon,
            icon_path=self._icon_path,
            logo_path=self._toast_logo_path(),
        )

    def _toast_logo_path(self):
        """Toast 只用 png/jpg/gif，且过大的图片会被系统忽略，优先用小尺寸图标。"""
        for name in ("图标_通知.png", "图标.png"):
            path = resource_path(name)
            if path.exists():
                return path
        return None

    def quit_application(self) -> None:
        if self._quitting:
            return
        self._quitting = True

        self._reporter.send_critical("程序退出", False, timeout=2.0)

        if self._monitor_thread is not None:
            self._monitor_thread.stop()
            self._monitor_thread = None

        app = QApplication.instance()
        if self._power is not None:
            self._power.unregister()
            if app is not None:
                app.removeNativeEventFilter(self._power)
            self._power = None

        self.tray_icon.hide()
        if app is not None:
            app.quit()
