"""应用映射管理页：增删改即保存。"""

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CardWidget,
    InfoBar,
    PrimaryPushButton,
    PushButton,
    TableWidget,
    TitleLabel,
)


class MappingPage(QWidget):
    def __init__(self, mapping, parent=None):
        super().__init__(parent)
        self.setObjectName("appMappingPage")
        self._mapping = mapping

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.addWidget(TitleLabel("应用映射管理"))
        layout.addSpacing(10)

        card = CardWidget(self)
        card_layout = QVBoxLayout(card)

        buttons = QHBoxLayout()
        self._add_button = PrimaryPushButton("新增")
        self._edit_button = PushButton("编辑")
        self._delete_button = PushButton("删除")
        buttons.addWidget(self._add_button)
        buttons.addWidget(self._edit_button)
        buttons.addWidget(self._delete_button)
        buttons.addStretch(1)
        self._open_button = PushButton("打开配置文件")
        self._open_button.setToolTip(str(self._mapping.user_path))
        buttons.addWidget(self._open_button)
        card_layout.addLayout(buttons)

        self._table = TableWidget(self)
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["可执行文件名", "映射名称"])
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        card_layout.addWidget(self._table)

        layout.addWidget(card, 1)

        self._add_button.clicked.connect(self._add_mapping)
        self._edit_button.clicked.connect(self._edit_mapping)
        self._delete_button.clicked.connect(self._delete_mapping)
        self._open_button.clicked.connect(self._open_mapping_file)

        self._reload()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._mapping.load()
        self._reload()

    def _open_mapping_file(self) -> None:
        path = self._mapping.user_path
        if not path.exists():
            InfoBar.error(
                title="打开失败",
                content=f"映射文件不存在：{path}",
                parent=self.window(),
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            InfoBar.error(
                title="打开失败",
                content=f"系统无法打开文件：{path}",
                parent=self.window(),
            )

    def _reload(self) -> None:
        self._table.setRowCount(0)
        for exe_name, display_name in self._mapping.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            for column, text in enumerate((exe_name, display_name)):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._table.setItem(row, column, item)

    def _selected_row(self) -> int:
        items = self._table.selectedItems()
        if not items:
            InfoBar.warning(title="提示", content="请先选择一条映射", parent=self.window(), duration=2000)
            return -1
        return items[0].row()

    def _ask_mapping(self, title: str, exe_name: str = "", display_name: str = ""):
        dialog = QDialog(self.window())
        dialog.setWindowTitle(title)
        dialog_layout = QVBoxLayout(dialog)

        form = QFormLayout()
        exe_edit = QLineEdit(exe_name)
        name_edit = QLineEdit(display_name)
        form.addRow("可执行文件名:", exe_edit)
        form.addRow("映射名称:", name_edit)
        dialog_layout.addLayout(form)

        buttons = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        buttons.addStretch(1)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        dialog_layout.addLayout(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return None
        return exe_edit.text().strip(), name_edit.text().strip()

    def _confirm_overwrite(self, exe_name: str) -> bool:
        reply = QMessageBox.question(
            self,
            "确认覆盖",
            f"可执行文件名 {exe_name} 已存在（不区分大小写），是否覆盖？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _add_mapping(self) -> None:
        values = self._ask_mapping("新增应用映射")
        if not values:
            return
        exe_name, display_name = values
        if not exe_name or not display_name:
            InfoBar.error(title="新增失败", content="可执行文件名和映射名称不能为空", parent=self.window())
            return
        if self._mapping.has_key(exe_name) and not self._confirm_overwrite(exe_name):
            return

        try:
            saved = self._mapping.add(exe_name, display_name)
        except ValueError as exc:
            InfoBar.error(title="新增失败", content=str(exc), parent=self.window())
            return
        self._finish(saved, f"已添加映射: {exe_name} → {display_name}")

    def _edit_mapping(self) -> None:
        row = self._selected_row()
        if row < 0:
            return

        old_exe = self._table.item(row, 0).text()
        old_name = self._table.item(row, 1).text()
        values = self._ask_mapping("编辑应用映射", old_exe, old_name)
        if not values:
            return
        new_exe, new_name = values
        if not new_exe or not new_name:
            InfoBar.error(title="编辑失败", content="可执行文件名和映射名称不能为空", parent=self.window())
            return
        if new_exe.lower() != old_exe.lower() and self._mapping.has_key(new_exe):
            if not self._confirm_overwrite(new_exe):
                return

        try:
            saved = self._mapping.update(old_exe, new_exe, new_name)
        except ValueError as exc:
            InfoBar.error(title="编辑失败", content=str(exc), parent=self.window())
            return
        self._finish(saved, f"已更新映射: {new_exe} → {new_name}")

    def _delete_mapping(self) -> None:
        row = self._selected_row()
        if row < 0:
            return

        exe_name = self._table.item(row, 0).text()
        display_name = self._table.item(row, 1).text()
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除映射: {exe_name} → {display_name} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._finish(self._mapping.remove(exe_name), f"已删除映射: {exe_name} → {display_name}")

    def _finish(self, saved: bool, message: str) -> None:
        self._reload()
        if saved:
            InfoBar.success(title="已保存", content=message, parent=self.window(), duration=2000)
        else:
            InfoBar.error(
                title="保存失败",
                content="写入应用映射文件失败，请检查目录权限",
                parent=self.window(),
                duration=3000,
            )
