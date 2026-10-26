"""日志页：增量查看、导出与主题适配。"""

import shutil
from pathlib import Path
from typing import List

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CardWidget,
    ComboBox,
    InfoBar,
    PrimaryPushButton,
    TitleLabel,
    isDarkTheme,
)

from app.logging_setup import LOG_BASENAME
from ui.theme import body_label


class LogPage(QWidget):
    def __init__(self, log_dir: Path, parent=None):
        super().__init__(parent)
        self.setObjectName("logPage")
        self._log_dir = Path(log_dir)
        self._paths: List[Path] = []
        self._current_path: Path = None
        self._position = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.addWidget(TitleLabel("日志查看"))

        file_card = CardWidget(self)
        file_layout = QHBoxLayout(file_card)
        file_layout.addWidget(body_label("选择日志文件:"))
        self._file_combo = ComboBox()
        self._file_combo.setMinimumWidth(260)
        file_layout.addWidget(self._file_combo)
        file_layout.addStretch(1)
        self._file_status = body_label("")
        file_layout.addWidget(self._file_status)
        layout.addWidget(file_card)

        content_card = CardWidget(self)
        content_layout = QVBoxLayout(content_card)
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.apply_theme()
        content_layout.addWidget(self._text_edit)
        layout.addWidget(content_card, 1)

        buttons = QHBoxLayout()
        self._refresh_button = PrimaryPushButton("刷新")
        self._export_button = PrimaryPushButton("导出")
        buttons.addWidget(self._refresh_button)
        buttons.addWidget(self._export_button)
        layout.addLayout(buttons)

        self._file_combo.currentIndexChanged.connect(self._on_file_changed)
        self._refresh_button.clicked.connect(self._reload_current)
        self._export_button.clicked.connect(self._export_log)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._append_new_content)
        self._timer.setInterval(2000)

        self.refresh_log_files()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()
        self.refresh_log_files()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def apply_theme(self) -> None:
        if isDarkTheme():
            self._text_edit.setStyleSheet("background-color: #1e1e1e; color: #f0f0f0;")
        else:
            self._text_edit.setStyleSheet("background-color: #ffffff; color: #000000;")

    def refresh_log_files(self) -> None:
        files = self._collect_files()
        current_name = self._current_path.name if self._current_path else None

        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        self._paths = files
        for path in files:
            label = path.name + ("（当前）" if path.name == LOG_BASENAME else "")
            self._file_combo.addItem(label)
        index = 0
        if current_name:
            for position, path in enumerate(files):
                if path.name == current_name:
                    index = position
                    break
        if files:
            self._file_combo.setCurrentIndex(index)
        self._file_combo.blockSignals(False)

        if files:
            self._load_file(files[index])
        else:
            self._current_path = None
            self._text_edit.clear()
            self._file_status.setText("暂无日志文件")

    def _collect_files(self) -> List[Path]:
        if not self._log_dir.exists():
            return []
        files = []
        for path in self._log_dir.iterdir():
            if not path.is_file():
                continue
            if path.name == LOG_BASENAME or path.name.startswith(LOG_BASENAME + "."):
                files.append(path)
        files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        return files

    def _on_file_changed(self, index: int) -> None:
        if 0 <= index < len(self._paths):
            self._load_file(self._paths[index])

    def _load_file(self, path: Path) -> None:
        self._current_path = path
        self._position = 0
        self._text_edit.clear()
        data = self._read_bytes(path)
        self._text_edit.setPlainText(data.decode("utf-8", errors="replace"))
        self._position = len(data)
        self._file_status.setText(str(path))
        self._scroll_to_bottom()

    def _reload_current(self) -> None:
        self.refresh_log_files()

    def _append_new_content(self) -> None:
        if self._current_path is None or not self._current_path.exists():
            return

        try:
            size = self._current_path.stat().st_size
        except OSError:
            return
        if size < self._position:
            self._load_file(self._current_path)
            return
        if size == self._position:
            return

        data = self._read_bytes(self._current_path, self._position)
        text = data.decode("utf-8", errors="replace")
        self._position += len(data)

        scrollbar = self._text_edit.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        previous_value = scrollbar.value()

        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._text_edit.setTextCursor(cursor)
        self._text_edit.insertPlainText(text)

        if at_bottom:
            self._scroll_to_bottom()
        else:
            scrollbar.setValue(previous_value)

    @staticmethod
    def _read_bytes(path: Path, offset: int = 0) -> bytes:
        try:
            with open(path, "rb") as handle:
                if offset:
                    handle.seek(offset)
                return handle.read()
        except OSError:
            return b""

    def _scroll_to_bottom(self) -> None:
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._text_edit.setTextCursor(cursor)
        self._text_edit.ensureCursorVisible()

    def _export_log(self) -> None:
        if self._current_path is None or not self._current_path.exists():
            InfoBar.error(title="导出失败", content="请先选择一个日志文件", parent=self.window())
            return

        export_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出日志文件",
            self._current_path.name,
            "日志文件 (*.log);;所有文件 (*.*)",
        )
        if not export_path:
            return

        try:
            shutil.copy2(self._current_path, export_path)
        except OSError as exc:
            InfoBar.error(
                title="导出失败",
                content=f"导出日志文件失败: {exc}",
                parent=self.window(),
            )
            return

        InfoBar.success(
            title="导出成功",
            content=f"日志已导出到: {export_path}",
            parent=self.window(),
        )

