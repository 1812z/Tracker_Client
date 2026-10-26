"""主页：当前应用、电池、设备信息。"""

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import CardWidget, TitleLabel

from app.battery import get_battery_status
from ui.theme import body_label


class HomePage(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addWidget(TitleLabel("设备使用情况"))

        card = CardWidget(self)
        card_layout = QVBoxLayout(card)

        self._app_label = body_label("当前应用: 初始化中...")
        self._battery_label = body_label("电池状态: 初始化中...")
        self._device_label = body_label(f"设备ID: {config.get('device_id', '')}")

        card_layout.addWidget(self._app_label)
        card_layout.addWidget(self._battery_label)
        card_layout.addWidget(self._device_label)

        layout.addWidget(card)
        layout.addStretch(1)

        self._battery_timer = QTimer(self)
        self._battery_timer.timeout.connect(self.refresh_battery)
        self._battery_timer.start(60000)

        self.refresh_battery()

    def set_app(self, app_name: str) -> None:
        self._app_label.setText(f"当前应用: {app_name}")

    def refresh_battery(self) -> None:
        battery_level, is_charging = get_battery_status()
        if battery_level is None:
            text = "电池状态: 未知"
        elif battery_level == -1:
            text = "电池状态: 无电池"
        else:
            suffix = "（充电中）" if is_charging else ""
            text = f"电池状态: {battery_level}%{suffix}"
        self._battery_label.setText(text)

    def on_config_saved(self) -> None:
        self._device_label.setText(f"设备ID: {self._config.get('device_id', '')}")

