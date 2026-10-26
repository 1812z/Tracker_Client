"""最近记录页：应用切换时间线。"""

from datetime import datetime
from functools import partial
from typing import Any

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QFrame,
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

from ui.theme import body_label, set_status_color
from ui.workers import ApiTask


def format_local_time(value: Any) -> str:
    if not value:
        return ""
    text = str(value).replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return str(value)
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    return moment.strftime("%Y-%m-%d %H:%M:%S")


class RecentCard(CardWidget):
    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        running = bool(record.get("running"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        dot = QFrame()
        dot.setFixedSize(9, 9)
        dot.setStyleSheet(
            "background-color: #22c55e; border-radius: 4px;"
            if running
            else "background-color: #9ca3af; border-radius: 4px;"
        )

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        app_label = body_label(str(record.get("appName") or "—"), size=14, bold=True)
        time_label = body_label(
            format_local_time(record.get("timestamp")), secondary=True, size=12
        )
        text_layout.addWidget(app_label)
        text_layout.addWidget(time_label)

        badge = BodyLabel("运行中" if running else "已停止")
        set_status_color(badge, running)

        layout.addWidget(dot)
        layout.addLayout(text_layout, 1)
        layout.addWidget(badge)


class RecentPage(QWidget):
    def __init__(self, config, server_api, parent=None):
        super().__init__(parent)
        self.setObjectName("recentPage")
        self._config = config
        self._server_api = server_api
        self._task = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)
        layout.addWidget(TitleLabel("最近记录"))

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
        self._list_layout = QVBoxLayout(container)
        self._list_layout.setContentsMargins(0, 0, 8, 0)
        self._list_layout.setSpacing(8)
        layout.addWidget(self._scroll, 1)

        self._refresh_button.clicked.connect(self.load_records)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.load_records)
        self._timer.setInterval(30000)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()
        self.load_records()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def load_records(self) -> None:
        if not self._config.is_query_configured():
            self._status_label.setText("请先在配置中填写 API 地址与设备 ID")
            return
        if self._task is not None and self._task.isRunning():
            return

        self._refresh_button.setEnabled(False)
        self._status_label.setText("加载中…")
        task = ApiTask(partial(self._server_api.fetch_recent, None), self)
        task.finished_ok.connect(self._render)
        task.failed.connect(self._on_error)
        task.finished.connect(lambda: self._refresh_button.setEnabled(True))
        self._task = task
        task.start()

    def _clear_rows(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render(self, records) -> None:
        records = records or []
        self._clear_rows()

        if not records:
            empty = body_label("暂无最近使用记录", secondary=True)
            self._list_layout.addWidget(empty)
            self._status_label.setText("暂无记录")
            self._list_layout.addStretch(1)
            return

        for record in records:
            if isinstance(record, dict):
                self._list_layout.addWidget(RecentCard(record))

        self._list_layout.addStretch(1)
        self._status_label.setText(f"最近 {len(records)} 条应用切换")

    def _on_error(self, message: str) -> None:
        self._status_label.setText(message)
        InfoBar.error(title="加载失败", content=message, parent=self.window(), duration=3000)
