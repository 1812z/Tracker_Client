"""配置页：主题、API、监控、开机自启与连接测试。"""

import time
from functools import partial

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CardWidget,
    ComboBox,
    InfoBar,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SwitchButton,
    Theme,
    TitleLabel,
    setTheme,
)

from app import autostart
from app.config import validate_api_url, validate_interval, validate_log_retention
from ui.theme import body_label
from ui.workers import ApiTask


class SettingsPage(QWidget):
    theme_changed = pyqtSignal()
    config_saved = pyqtSignal()

    def __init__(self, config, server_api, parent=None):
        super().__init__(parent)
        self.setObjectName("configPage")
        self._config = config
        self._server_api = server_api
        self._test_task = None
        self._test_started = 0.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.addWidget(TitleLabel("配置"))

        layout.addWidget(self._build_theme_card(container))
        layout.addWidget(self._build_api_card(container))
        layout.addWidget(self._build_monitor_card(container))
        layout.addWidget(self._build_log_card(container))
        layout.addWidget(self._build_autostart_card(container))

        button_row = QHBoxLayout()
        self._test_button = PushButton("测试连接")
        self._save_button = PrimaryPushButton("保存配置")
        button_row.addWidget(self._test_button)
        button_row.addWidget(self._save_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._status_label = body_label("")
        layout.addWidget(self._status_label)
        layout.addStretch(1)

        self._test_button.clicked.connect(self._test_connection)
        self._save_button.clicked.connect(self._save_config)

    def _build_theme_card(self, parent) -> CardWidget:
        card = CardWidget(parent)
        layout = QVBoxLayout(card)
        layout.addWidget(body_label("主题设置"))
        self._theme_combo = ComboBox()
        self._theme_combo.addItems(["跟随系统", "浅色主题", "深色主题"])
        self._theme_combo.blockSignals(True)
        self._theme_combo.setCurrentIndex(int(self._config.get("theme", 0)))
        self._theme_combo.blockSignals(False)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        layout.addWidget(self._theme_combo)
        return card

    def _build_api_card(self, parent) -> CardWidget:
        card = CardWidget(parent)
        layout = QVBoxLayout(card)
        layout.addWidget(body_label("API 设置"))

        row = QHBoxLayout()
        label = body_label("API 地址:")
        label.setMinimumWidth(90)
        self._api_url_edit = LineEdit()
        self._api_url_edit.setText(self._config.get("api_url", ""))
        self._api_url_edit.setPlaceholderText("https://your-server.example/api")
        row.addWidget(label)
        row.addWidget(self._api_url_edit)
        layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("密钥:")
        label.setMinimumWidth(90)
        self._secret_edit = LineEdit()
        self._secret_edit.setText(self._config.get("secret_key", ""))
        self._secret_edit.setEchoMode(QLineEdit.Password)
        row.addWidget(label)
        row.addWidget(self._secret_edit)
        layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("设备 ID:")
        label.setMinimumWidth(90)
        self._device_edit = LineEdit()
        self._device_edit.setText(self._config.get("device_id", ""))
        row.addWidget(label)
        row.addWidget(self._device_edit)
        layout.addLayout(row)

        layout.addWidget(body_label("密钥仅保存在本机配置文件中，请勿使用与他人共享的密钥。"))
        return card

    def _build_monitor_card(self, parent) -> CardWidget:
        card = CardWidget(parent)
        layout = QVBoxLayout(card)
        layout.addWidget(body_label("监控设置"))

        row = QHBoxLayout()
        label = body_label("监控间隔(秒):")
        label.setMinimumWidth(90)
        self._interval_edit = LineEdit()
        self._interval_edit.setText(str(self._config.get("monitor_interval", 1)))
        row.addWidget(label)
        row.addWidget(self._interval_edit)
        layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("上报功能:")
        label.setMinimumWidth(90)
        self._report_switch = SwitchButton()
        self._report_switch.setChecked(bool(self._config.get("report_enabled", True)))
        self._report_switch.checkedChanged.connect(self._on_report_toggled)
        row.addWidget(label)
        row.addWidget(self._report_switch)
        row.addStretch(1)
        layout.addLayout(row)
        return card

    def _build_log_card(self, parent) -> CardWidget:
        card = CardWidget(parent)
        layout = QVBoxLayout(card)
        layout.addWidget(body_label("日志留存"))

        row = QHBoxLayout()
        label = body_label("保留天数:")
        label.setMinimumWidth(90)
        self._log_days_edit = LineEdit()
        self._log_days_edit.setText(str(self._config.get("log_retention_days", 30)))
        row.addWidget(label)
        row.addWidget(self._log_days_edit)
        layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("保留数量:")
        label.setMinimumWidth(90)
        self._log_count_edit = LineEdit()
        self._log_count_edit.setText(str(self._config.get("log_retention_count", 30)))
        row.addWidget(label)
        row.addWidget(self._log_count_edit)
        layout.addLayout(row)

        layout.addWidget(
            body_label("超出天数或数量的历史日志会自动删除，当前日志不受影响。")
        )
        return card

    def _build_autostart_card(self, parent) -> CardWidget:
        card = CardWidget(parent)
        layout = QHBoxLayout(card)
        text_layout = QVBoxLayout()
        text_layout.addWidget(body_label("开机自启"))
        text_layout.addWidget(body_label("登录 Windows 后自动在托盘运行"))
        layout.addLayout(text_layout)
        layout.addStretch(1)
        self._autostart_switch = SwitchButton()
        self._autostart_switch.setChecked(autostart.is_enabled())
        self._autostart_switch.checkedChanged.connect(self._on_autostart_toggled)
        layout.addWidget(self._autostart_switch)
        return card

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._autostart_switch.blockSignals(True)
        self._autostart_switch.setChecked(autostart.is_enabled())
        self._autostart_switch.blockSignals(False)

    def _on_theme_changed(self, index: int) -> None:
        if index == 0:
            setTheme(Theme.AUTO)
        elif index == 1:
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)

        self._config.set("theme", index)
        self._config.save()
        self.theme_changed.emit()

    def _on_report_toggled(self, state: bool) -> None:
        self._config.set("report_enabled", bool(state))
        self._config.save()

    def _on_autostart_toggled(self, state: bool) -> None:
        try:
            if state:
                autostart.enable()
            else:
                autostart.disable()
        except RuntimeError as exc:
            self._autostart_switch.blockSignals(True)
            self._autostart_switch.setChecked(not state)
            self._autostart_switch.blockSignals(False)
            InfoBar.error(title="设置失败", content=str(exc), parent=self.window())
            return

        self._config.set("auto_start", bool(state))
        self._config.save()
        InfoBar.success(
            title="开机自启",
            content="已启用" if state else "已关闭",
            parent=self.window(),
            duration=2000,
        )

    def _test_connection(self) -> None:
        url = self._api_url_edit.text().strip()
        try:
            validate_api_url(url)
        except ValueError as exc:
            InfoBar.error(title="地址无效", content=str(exc), parent=self.window())
            return
        if not url:
            InfoBar.error(title="地址为空", content="请先填写 API 地址", parent=self.window())
            return
        if url != str(self._config.get("api_url", "")).strip():
            InfoBar.warning(
                title="尚未保存",
                content="请先保存配置，再测试连接",
                parent=self.window(),
                duration=3000,
            )
            return
        if self._test_task is not None and self._test_task.isRunning():
            return

        self._test_button.setEnabled(False)
        self._status_label.setText("正在测试连接…")
        self._test_started = time.monotonic()
        task = ApiTask(partial(self._server_api.test_connection), self)
        task.finished_ok.connect(self._on_test_ok)
        task.failed.connect(self._on_test_failed)
        task.finished.connect(lambda: self._test_button.setEnabled(True))
        self._test_task = task
        task.start()

    def _on_test_ok(self, data) -> None:
        data = data or {}
        latency = (time.monotonic() - self._test_started) * 1000
        ip = data.get("ip", "未知")
        message = f"连接成功，服务端 IP: {ip}，延迟 {latency:.0f} ms"
        self._status_label.setText(message)
        InfoBar.success(title="连接成功", content=message, parent=self.window())

    def _on_test_failed(self, message: str) -> None:
        self._status_label.setText(message)
        InfoBar.error(title="连接失败", content=message, parent=self.window())

    def _save_config(self) -> None:
        url = self._api_url_edit.text().strip()
        try:
            validate_api_url(url)
            interval = validate_interval(self._interval_edit.text())
            log_days, log_count = validate_log_retention(
                self._log_days_edit.text(), self._log_count_edit.text()
            )
        except ValueError as exc:
            InfoBar.error(title="配置无效", content=str(exc), parent=self.window())
            return

        device_id = self._device_edit.text().strip()
        if not device_id:
            device_id = self._config.ensure_device_id()
            self._device_edit.setText(device_id)

        self._config.set("api_url", url)
        self._config.set("secret_key", self._secret_edit.text().strip())
        self._config.set("device_id", device_id)
        self._config.set("monitor_interval", interval)
        self._config.set("report_enabled", self._report_switch.isChecked())
        self._config.set("log_retention_days", log_days)
        self._config.set("log_retention_count", log_count)

        if not self._config.save():
            InfoBar.error(
                title="保存失败",
                content="写入配置失败，请检查目录权限",
                parent=self.window(),
            )
            return

        self.config_saved.emit()
        InfoBar.success(title="配置已保存", content="所有配置已保存到本地", parent=self.window())
