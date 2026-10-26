"""设备总览页：设备卡片列表。"""

from functools import partial
from typing import Any, Dict, List

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    InfoBar,
    PrimaryPushButton,
    TitleLabel,
)

from ui.pages.recent import format_local_time
from ui.theme import body_label, set_status_color
from ui.workers import ApiTask


def _battery_text(device: Dict[str, Any]) -> str:
    level = device.get("batteryLevel")
    if level in (None, "", 0, "0"):
        return "—"
    charging = "（充电中）" if device.get("isCharging") else ""
    return f"{level}%{charging}"


class DeviceCard(CardWidget):
    def __init__(self, device: Dict[str, Any], is_current: bool, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMinimumHeight(150)

        name = str(device.get("device", "未知设备"))
        if is_current:
            name = f"{name}（本机）"

        running = bool(device.get("running"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        name_label = body_label(name, size=15, bold=True)
        name_label.setWordWrap(True)
        badge = BodyLabel("运行中" if running else "已停止")
        set_status_color(badge, running)
        header.addWidget(name_label, 1)
        header.addWidget(badge)
        layout.addLayout(header)

        layout.addWidget(body_label(f"当前应用：{device.get('currentApp') or '—'}"))
        layout.addWidget(body_label(f"电量：{_battery_text(device)}"))
        layout.addWidget(
            body_label(f"运行开始：{format_local_time(device.get('runningSince')) or '—'}")
        )
        layout.addWidget(
            body_label(f"电量更新：{format_local_time(device.get('batteryTimestamp')) or '—'}")
        )


class DevicesPage(QWidget):
    def __init__(self, config, server_api, parent=None):
        super().__init__(parent)
        self.setObjectName("devicesPage")
        self._config = config
        self._server_api = server_api
        self._task = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)
        layout.addWidget(TitleLabel("设备总览"))

        toolbar = CardWidget(self)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 10, 16, 10)
        self._status_label = body_label("尚未加载")
        self._refresh_button = PrimaryPushButton("刷新")
        toolbar_layout.addWidget(self._status_label)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self._refresh_button)
        layout.addWidget(toolbar)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("background: transparent;")
        container = QWidget()
        self._scroll.setWidget(container)
        self._grid = QGridLayout(container)
        self._grid.setContentsMargins(0, 0, 8, 0)
        self._grid.setSpacing(12)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(1, 1)
        layout.addWidget(self._scroll, 1)

        self._refresh_button.clicked.connect(self.load_devices)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.load_devices)
        self._timer.setInterval(30000)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()
        self.load_devices()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def load_devices(self) -> None:
        if not self._config.is_query_configured():
            self._status_label.setText("请先在配置中填写 API 地址与设备 ID")
            return
        if self._task is not None and self._task.isRunning():
            return

        self._refresh_button.setEnabled(False)
        self._status_label.setText("加载中…")
        task = ApiTask(partial(self._server_api.fetch_devices), self)
        task.finished_ok.connect(self._render)
        task.failed.connect(self._on_error)
        task.finished.connect(lambda: self._refresh_button.setEnabled(True))
        self._task = task
        task.start()

    def _clear_cards(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render(self, devices: List[Dict[str, Any]]) -> None:
        devices = devices or []
        current = str(self._config.get("device_id", ""))
        self._clear_cards()

        if not devices:
            empty = body_label("暂无设备", secondary=True)
            self._grid.addWidget(empty, 0, 0, 1, 2)
            self._status_label.setText("暂无设备")
            return

        for index, device in enumerate(devices):
            if not isinstance(device, dict):
                continue
            card = DeviceCard(device, str(device.get("device", "")) == current)
            self._grid.addWidget(card, index // 2, index % 2)

        self._grid.setRowStretch((len(devices) + 1) // 2, 1)
        self._status_label.setText(f"共 {len(devices)} 台设备")

    def _on_error(self, message: str) -> None:
        self._status_label.setText(message)
        InfoBar.error(title="加载失败", content=message, parent=self.window(), duration=3000)
