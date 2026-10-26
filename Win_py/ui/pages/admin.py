"""服务器管理页：登录、分组配置编辑、AI 任务与账户设置。"""

from functools import partial
from typing import Any, Dict, Tuple

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
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
    SpinBox,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
    TitleLabel,
)

from app.admin_api import is_transport_secure
from app.server_api import ApiError
from ui.theme import body_label
from ui.workers import ApiTask

BOOL_DEFAULTS = {
    "AI_SUMMARY_ENABLED": True,
    "PUBLISH_ENABLED": False,
    "WEB_DEVICE_COUNT": True,
    "WEB_COMMENT": True,
    "WEB_SUMMARY": True,
    "GISCUS_REACTIONSENABLED": True,
    "GISCUS_EMITMETADATA": False,
}

SPIN_RANGES = {
    "PORT": (1, 65535),
    "AI_MAX_TOKENS": (1, 1000000),
    "DEFAULT_TIMEZONE_OFFSET": (-12, 14),
}

SPIN_DEFAULTS = {
    "PORT": 3000,
    "AI_MAX_TOKENS": 1000,
    "DEFAULT_TIMEZONE_OFFSET": 8,
}

COMBO_OPTIONS = {
    "GISCUS_MAPPING": ["pathname", "url", "title", "og:title"],
    "GISCUS_INPUTPOSITION": ["bottom", "top"],
    "GISCUS_THEME": ["light", "dark", "preferred"],
}

COMBO_DEFAULTS = {
    "GISCUS_MAPPING": "pathname",
    "GISCUS_INPUTPOSITION": "bottom",
    "GISCUS_THEME": "light",
}

WRITE_ONLY_KEYS = {"SECRET", "AI_API_KEY"}
PASSWORD_KEYS = {"SECRET", "AI_API_KEY", "PUBLISH_API_KEY"}
READONLY_KEYS = {"ADMIN_USER", "JWT_SECRET_MODE"}


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1", "yes", "on"):
            return True
        if text in ("false", "0", "no", "off"):
            return False
    return default


def _to_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


class AdminPage(QWidget):
    def __init__(self, config, admin_api, parent=None):
        super().__init__(parent)
        self.setObjectName("adminPage")
        self._config = config
        self._api = admin_api
        self._task = None
        self._busy = False
        self._login_allowed = False
        self._pending_updates = set()
        self._action_buttons = []
        self._field_widgets: Dict[str, QWidget] = {}
        self._spin_ranges: Dict[str, Tuple[int, int]] = {}
        self._initial_ui: Dict[str, Any] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.addWidget(TitleLabel("服务器管理"))

        self._stack = QStackedWidget(self)
        self._login_page = self._build_login_page()
        self._manage_page = self._build_manage_page()
        self._stack.addWidget(self._login_page)
        self._stack.addWidget(self._manage_page)
        self._stack.setCurrentWidget(self._login_page)
        layout.addWidget(self._stack, 1)

        self._update_server_info()

    # ------------------------------------------------------------------ login

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)

        card = CardWidget(page)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.addWidget(TitleLabel("管理员登录"))

        self._server_label = body_label("服务端：—")
        self._secure_warning = body_label("")
        self._secure_warning.setWordWrap(True)
        self._secure_warning.setStyleSheet("color: #d13438;")
        card_layout.addWidget(self._server_label)
        card_layout.addWidget(self._secure_warning)

        row = QHBoxLayout()
        label = body_label("用户名:")
        label.setMinimumWidth(90)
        self._login_username = LineEdit()
        row.addWidget(label)
        row.addWidget(self._login_username)
        card_layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("密码:")
        label.setMinimumWidth(90)
        self._login_password = LineEdit()
        self._login_password.setEchoMode(QLineEdit.Password)
        row.addWidget(label)
        row.addWidget(self._login_password)
        card_layout.addLayout(row)

        self._login_button = PrimaryPushButton("登录")
        self._login_button.clicked.connect(self._login)
        card_layout.addWidget(self._login_button)

        self._login_status = body_label("")
        card_layout.addWidget(self._login_status)
        card_layout.addWidget(
            body_label("管理员凭据仅用于本次会话，不会写入配置文件；退出或关闭应用后需重新登录。")
        )

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _update_server_info(self) -> None:
        try:
            base = self._api.admin_base_url()
        except ApiError as exc:
            self._server_label.setText("服务端：未配置")
            self._secure_warning.setText(str(exc))
            self._secure_warning.setVisible(True)
            self._login_allowed = False
        else:
            self._server_label.setText(f"服务端：{base}")
            secure = is_transport_secure(base)
            self._login_allowed = secure
            if secure:
                self._secure_warning.setVisible(False)
            else:
                self._secure_warning.setText(
                    "当前为 HTTP 连接，管理凭据会明文传输；仅允许本机回环地址登录。"
                )
                self._secure_warning.setVisible(True)

        self._login_button.setEnabled(self._login_allowed and not self._busy)

    def _login(self) -> None:
        username = self._login_username.text().strip()
        password = self._login_password.text()
        if not username or not password:
            InfoBar.error(
                title="登录失败",
                content="用户名和密码不能为空",
                parent=self.window(),
            )
            return

        self._login_status.setText("正在登录…")
        self._run(partial(self._api.login, username, password), self._on_login_ok)

    def _on_login_ok(self, _data) -> None:
        self._login_password.clear()
        self._login_status.setText("")
        self._account_label.setText(f"已登录：{self._api.username}")
        self._stack.setCurrentWidget(self._manage_page)
        if not self._trigger_device.text().strip():
            self._trigger_device.setText(str(self._config.get("device_id", "")))
        QTimer.singleShot(50, self._load_config)

    def _logout(self) -> None:
        self._api.logout()
        self._stack.setCurrentWidget(self._login_page)
        self._login_password.clear()
        for key in PASSWORD_KEYS:
            widget = self._field_widgets.get(key)
            if isinstance(widget, QLineEdit):
                widget.clear()
        self._initial_ui = {}
        self._pending_updates = set()
        self._account_label.setText("")
        self._login_status.setText("已退出登录")
        self._update_server_info()

    def _on_auth_failed(self, message: str) -> None:
        self._logout()
        InfoBar.error(title="登录已失效", content=message, parent=self.window())

    # ----------------------------------------------------------------- manage

    def _build_manage_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        self._account_label = body_label("")
        self._password_button = PushButton("修改密码")
        self._logout_button = PushButton("退出登录")
        self._restart_button = PushButton("重启服务")
        top_row.addWidget(self._account_label)
        top_row.addStretch(1)
        top_row.addWidget(self._password_button)
        top_row.addWidget(self._logout_button)
        top_row.addWidget(self._restart_button)
        outer.addLayout(top_row)

        body = QHBoxLayout()
        body.setContentsMargins(0, 10, 0, 0)
        body.setSpacing(16)

        left_panel = QWidget()
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)
        self._build_config_section(left)

        right_panel = QWidget()
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)

        self._right_scroll = QScrollArea(right_panel)
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setFrameShape(QFrame.NoFrame)
        self._right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._right_scroll.setStyleSheet("background: transparent;")
        right_container = QWidget()
        self._right_scroll.setWidget(right_container)
        right_content = QVBoxLayout(right_container)
        right_content.setContentsMargins(0, 0, 8, 0)
        right_content.setSpacing(12)
        self._build_service_card(right_content)
        self._build_account_card(right_content)
        right_content.addStretch(1)
        right.addWidget(self._right_scroll, 1)

        body.addWidget(left_panel, 3)
        body.addWidget(right_panel, 2)
        outer.addLayout(body, 1)

        self._password_button.clicked.connect(self._focus_account)
        self._logout_button.clicked.connect(self._logout)
        self._restart_button.clicked.connect(self._restart_service)
        self._action_buttons.extend(
            [
                self._password_button,
                self._logout_button,
                self._restart_button,
                self._config_refresh_button,
                self._config_save_button,
                self._ai_start_button,
                self._ai_stop_button,
                self._trigger_button,
                self._account_update_button,
            ]
        )
        return page

    def _build_config_section(self, layout: QVBoxLayout) -> None:
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("配置信息"))
        header.addStretch(1)
        self._config_refresh_button = PushButton("刷新配置")
        self._config_save_button = PrimaryPushButton("保存修改")
        header.addWidget(self._config_refresh_button)
        header.addWidget(self._config_save_button)
        layout.addLayout(header)

        self._config_scroll = QScrollArea(self)
        self._config_scroll.setWidgetResizable(True)
        self._config_scroll.setFrameShape(QFrame.NoFrame)
        self._config_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._config_scroll.setStyleSheet("background: transparent;")
        container = QWidget()
        self._config_scroll.setWidget(container)
        cards = QVBoxLayout(container)
        cards.setContentsMargins(0, 0, 8, 0)
        cards.setSpacing(12)
        cards.addWidget(self._build_basic_card())
        cards.addWidget(self._build_ai_card())
        cards.addWidget(self._build_publish_card())
        cards.addWidget(self._build_website_card())
        cards.addWidget(self._build_giscus_card())
        cards.addStretch(1)
        layout.addWidget(self._config_scroll, 1)

        self._config_refresh_button.clicked.connect(self._load_config)
        self._config_save_button.clicked.connect(self._save_config_values)

    def _new_card(self, title: str, description: str = "") -> Tuple[CardWidget, QVBoxLayout]:
        card = CardWidget(self)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel(title))
        if description:
            hint = body_label(description, secondary=True, size=12)
            hint.setWordWrap(True)
            layout.addWidget(hint)
        return card, layout

    def _build_basic_card(self) -> CardWidget:
        card, layout = self._new_card(
            "基础设置", "服务端口、数据库、时区与上报密钥。修改后点击右上角“保存修改”。"
        )
        self._add_spin(layout, "PORT", "服务端口", "服务运行的端口号")
        self._add_line(
            layout,
            "MONGODB_URI",
            "MongoDB 连接地址",
            "MongoDB 数据库连接字符串，包含数据库凭据",
            full_width=True,
        )
        self._add_spin(layout, "DEFAULT_TIMEZONE_OFFSET", "默认时区偏移", "默认时区偏移量（小时）")
        self._add_line(
            layout,
            "SECRET",
            "上报密钥",
            "用于客户端上报验证；留空表示不修改当前密钥",
            password=True,
            placeholder="留空表示不修改",
        )
        self._add_line(layout, "ADMIN_USER", "管理员账户", "管理员用户名，请在账户设置中修改", readonly=True)
        self._add_line(
            layout,
            "JWT_SECRET_MODE",
            "JWT 密钥模式",
            "random_on_restart 表示重启服务后需要重新登录",
            readonly=True,
        )
        return card

    def _build_ai_card(self) -> CardWidget:
        card, layout = self._new_card("AI 配置", "AI 总结服务与提示词配置。")
        self._add_switch(layout, "AI_SUMMARY_ENABLED", "AI 总结总开关", "是否启用 AI 自动总结功能")
        self._add_line(layout, "AI_API_URL", "AI API 地址", "AI 服务的 API 地址", full_width=True)
        self._add_line(
            layout,
            "AI_API_KEY",
            "AI API 密钥",
            "AI 服务的认证密钥；留空表示不修改当前密钥",
            password=True,
            placeholder="留空表示不修改",
        )
        self._add_line(layout, "AI_MODEL", "AI 模型", "使用的 AI 模型名称")
        self._add_spin(layout, "AI_MAX_TOKENS", "AI 最大 Token 数", "AI 生成内容的最大 Token 数量")
        self._add_textarea(layout, "AI_PROMPT", "AI 提示词", "用于自定义 AI 总结风格与内容")
        return card

    def _build_publish_card(self) -> CardWidget:
        card, layout = self._new_card("AI 总结发布配置", "AI 总结发布开关与发布接口。")
        self._add_switch(layout, "PUBLISH_ENABLED", "发布开关", "是否发布 AI 总结")
        self._add_line(
            layout,
            "PUBLISH_API_URL",
            "发布 API 地址",
            "内容发布的 API 地址",
            full_width=True,
        )
        self._add_line(
            layout,
            "PUBLISH_API_KEY",
            "发布 API 密钥",
            "内容发布的认证密钥；留空表示不修改当前密钥",
            password=True,
            placeholder="留空表示不修改",
        )
        return card

    def _build_website_card(self) -> CardWidget:
        card, layout = self._new_card("网站功能", "控制网页端展示与评论功能。")
        self._add_switch(layout, "WEB_DEVICE_COUNT", "显示设备数量", "是否在网站显示设备数量统计")
        self._add_switch(layout, "WEB_COMMENT", "评论功能", "是否在网站显示评论功能")
        self._add_switch(layout, "WEB_SUMMARY", "总览功能", "是否在网站显示总览统计数据")
        return card

    def _build_giscus_card(self) -> CardWidget:
        card, layout = self._new_card("Giscus 评论", "网页端评论系统的 Giscus 配置。")
        self._add_line(layout, "GISCUS_REPO", "Giscus 仓库", "例如 owner/repo")
        self._add_line(layout, "GISCUS_REPOID", "Giscus Repo ID", "Giscus 仓库 ID")
        self._add_line(layout, "GISCUS_CATEGORY", "Giscus 分类", "讨论分类名称")
        self._add_line(layout, "GISCUS_CATEGORYID", "Giscus 分类 ID", "讨论分类 ID")
        self._add_combo(layout, "GISCUS_MAPPING", "Giscus 映射", "评论与页面路径的映射方式")
        self._add_switch(layout, "GISCUS_REACTIONSENABLED", "Giscus 表情回应", "是否启用表情回应")
        self._add_switch(layout, "GISCUS_EMITMETADATA", "Giscus 元数据", "是否发送页面元数据")
        self._add_combo(layout, "GISCUS_INPUTPOSITION", "Giscus 输入框位置", "评论输入框的位置")
        self._add_combo(layout, "GISCUS_THEME", "Giscus 主题", "评论组件主题")
        self._add_line(layout, "GISCUS_LANG", "Giscus 语言", "例如 zh-CN")
        return card

    def _add_row(
        self,
        layout: QVBoxLayout,
        key: str,
        title: str,
        widget: QWidget,
        description: str = "",
        wide: bool = True,
    ) -> None:
        row = QHBoxLayout()
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.addWidget(body_label(title))
        if description:
            hint = body_label(description, secondary=True, size=12)
            hint.setWordWrap(True)
            text_layout.addWidget(hint)
        row.addLayout(text_layout, 1)
        if wide:
            widget.setMinimumWidth(240)
        row.addWidget(widget, 0, Qt.AlignTop)
        layout.addLayout(row)
        self._field_widgets[key] = widget

    def _add_line(
        self,
        layout: QVBoxLayout,
        key: str,
        title: str,
        description: str = "",
        password: bool = False,
        readonly: bool = False,
        placeholder: str = "",
        full_width: bool = False,
    ) -> None:
        widget = LineEdit()
        widget.setPlaceholderText(placeholder)
        if password:
            widget.setEchoMode(QLineEdit.Password)
        if readonly:
            widget.setReadOnly(True)

        if full_width:
            layout.addWidget(body_label(title))
            if description:
                hint = body_label(description, secondary=True, size=12)
                hint.setWordWrap(True)
                layout.addWidget(hint)
            layout.addWidget(widget)
            self._field_widgets[key] = widget
            return

        self._add_row(layout, key, title, widget, description)

    def _add_spin(
        self,
        layout: QVBoxLayout,
        key: str,
        title: str,
        description: str = "",
    ) -> None:
        minimum, maximum = SPIN_RANGES[key]
        widget = SpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(SPIN_DEFAULTS[key])
        self._spin_ranges[key] = (minimum, maximum)
        self._add_row(layout, key, title, widget, description, wide=False)
        widget.setMinimumWidth(160)

    def _add_switch(
        self,
        layout: QVBoxLayout,
        key: str,
        title: str,
        description: str = "",
    ) -> None:
        widget = SwitchButton()
        widget.setOnText("开")
        widget.setOffText("关")
        self._add_row(layout, key, title, widget, description, wide=False)

    def _add_combo(
        self,
        layout: QVBoxLayout,
        key: str,
        title: str,
        description: str = "",
    ) -> None:
        widget = ComboBox()
        widget.addItems(COMBO_OPTIONS[key])
        widget.setCurrentText(COMBO_DEFAULTS[key])
        self._add_row(layout, key, title, widget, description)
        widget.setMinimumWidth(240)

    def _add_textarea(
        self,
        layout: QVBoxLayout,
        key: str,
        title: str,
        description: str = "",
    ) -> None:
        label = body_label(title)
        hint = body_label(description, secondary=True, size=12)
        hint.setWordWrap(True)
        widget = TextEdit()
        widget.setMinimumHeight(90)
        layout.addWidget(label)
        layout.addWidget(hint)
        layout.addWidget(widget)
        self._field_widgets[key] = widget

    # ------------------------------------------------------------------ service

    def _build_service_card(self, layout: QVBoxLayout) -> None:
        card, card_layout = self._new_card("AI 任务控制", "启动/停止定时任务，或手动触发单个设备的 AI 总结。")

        self._ai_start_button = PrimaryPushButton("启动 AI 任务")
        self._ai_stop_button = PushButton("停止 AI 任务")
        card_layout.addWidget(self._ai_start_button)
        card_layout.addWidget(self._ai_stop_button)

        card_layout.addWidget(body_label("手动触发 AI 总结"))
        row = QHBoxLayout()
        label = body_label("设备 ID:")
        label.setMinimumWidth(80)
        self._trigger_device = LineEdit()
        self._trigger_device.setText(str(self._config.get("device_id", "")))
        row.addWidget(label)
        row.addWidget(self._trigger_device)
        card_layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("日期:")
        label.setMinimumWidth(80)
        self._trigger_date = LineEdit()
        self._trigger_date.setPlaceholderText("YYYY-MM-DD，留空为默认日期")
        row.addWidget(label)
        row.addWidget(self._trigger_date)
        card_layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("时区偏移:")
        label.setMinimumWidth(80)
        self._trigger_timezone = SpinBox()
        self._trigger_timezone.setRange(-12, 14)
        self._trigger_timezone.setValue(8)
        self._trigger_button = PrimaryPushButton("触发总结")
        row.addWidget(label)
        row.addWidget(self._trigger_timezone)
        row.addStretch(1)
        row.addWidget(self._trigger_button)
        card_layout.addLayout(row)

        self._ai_start_button.clicked.connect(self._start_ai)
        self._ai_stop_button.clicked.connect(self._stop_ai)
        self._trigger_button.clicked.connect(self._trigger_ai)
        layout.addWidget(card)

    def _build_account_card(self, layout: QVBoxLayout) -> None:
        card, card_layout = self._new_card("账户设置", "修改管理员用户名或密码；修改后可能需要重新登录。")
        self._account_card = card

        row = QHBoxLayout()
        label = body_label("新用户名:")
        label.setMinimumWidth(80)
        self._new_username = LineEdit()
        self._new_username.setPlaceholderText("留空表示不修改")
        row.addWidget(label)
        row.addWidget(self._new_username)
        card_layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("新密码:")
        label.setMinimumWidth(80)
        self._new_password = LineEdit()
        self._new_password.setEchoMode(QLineEdit.Password)
        self._new_password.setPlaceholderText("留空表示不修改")
        row.addWidget(label)
        row.addWidget(self._new_password)
        card_layout.addLayout(row)

        row = QHBoxLayout()
        label = body_label("确认密码:")
        label.setMinimumWidth(80)
        self._confirm_password = LineEdit()
        self._confirm_password.setEchoMode(QLineEdit.Password)
        row.addWidget(label)
        row.addWidget(self._confirm_password)
        card_layout.addLayout(row)

        self._account_update_button = PrimaryPushButton("更新账户")
        self._account_update_button.clicked.connect(self._update_account)
        card_layout.addWidget(self._account_update_button)
        layout.addWidget(card)

    def _focus_account(self) -> None:
        self._right_scroll.ensureWidgetVisible(self._account_card)
        self._new_password.setFocus()

    # ------------------------------------------------------------------- data

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_server_info()

    def _load_config(self) -> None:
        if not self._api.is_authenticated:
            return
        self._run(partial(self._api.get_config), self._render_config)

    def _render_config(self, config: Dict[str, Any]) -> None:
        config = config or {}
        for key, widget in self._field_widgets.items():
            if key in WRITE_ONLY_KEYS:
                if isinstance(widget, QLineEdit):
                    widget.clear()
                continue

            value = config.get(key)

            if isinstance(widget, SwitchButton):
                widget.setChecked(_to_bool(value, BOOL_DEFAULTS.get(key, False)))
            elif isinstance(widget, SpinBox):
                minimum, maximum = self._spin_ranges[key]
                widget.setValue(_to_int(value, SPIN_DEFAULTS[key], minimum, maximum))
            elif isinstance(widget, TextEdit):
                widget.setPlainText("" if value is None else str(value))
            elif isinstance(widget, ComboBox):
                text = str(value or COMBO_DEFAULTS.get(key, ""))
                if widget.findText(text) < 0:
                    widget.addItem(text)
                widget.setCurrentText(text)
            elif isinstance(widget, QLineEdit):
                text = "" if value is None else str(value)
                widget.setText(text)
                widget.setCursorPosition(0)
                if key in PASSWORD_KEYS or key == "MONGODB_URI":
                    widget.setToolTip("")
                else:
                    widget.setToolTip(text)

        self._initial_ui = {
            key: self._widget_value(widget)
            for key, widget in self._field_widgets.items()
        }

    def _widget_value(self, widget: QWidget) -> Any:
        if isinstance(widget, SwitchButton):
            return bool(widget.isChecked())
        if isinstance(widget, SpinBox):
            return int(widget.value())
        if isinstance(widget, TextEdit):
            return widget.toPlainText()
        if isinstance(widget, ComboBox):
            return widget.currentText()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        return ""

    def _collect_updates(self) -> Dict[str, Any]:
        updates: Dict[str, Any] = {}
        for key, widget in self._field_widgets.items():
            if key in READONLY_KEYS:
                continue

            value = self._widget_value(widget)
            if key in PASSWORD_KEYS and not value:
                continue
            if value == self._initial_ui.get(key):
                continue

            if isinstance(widget, SwitchButton):
                updates[key] = "true" if value else "false"
            else:
                updates[key] = value
        return updates

    def _save_config_values(self) -> None:
        updates = self._collect_updates()
        if not updates:
            InfoBar.info(title="没有修改", content="配置未发生变化", parent=self.window())
            return

        self._pending_updates = set(updates)
        self._run(partial(self._api.update_config, updates), self._on_config_saved)

    def _on_config_saved(self, data: Dict[str, Any]) -> None:
        data = data or {}
        updated = data.get("updatedKeys") or sorted(self._pending_updates)
        message = data.get("message") or "配置已更新"
        notice = data.get("notice") or data.get("details") or ""
        content = f"{message}：{', '.join(map(str, updated))}" if updated else message
        if notice:
            content = f"{content}（{notice}）"
        InfoBar.success(title="已保存", content=content, parent=self.window(), duration=4000)
        if "PORT" in updated or "PORT" in self._pending_updates:
            InfoBar.warning(
                title="需要重启",
                content="PORT 修改需要重启服务后生效",
                parent=self.window(),
                duration=4000,
            )
        QTimer.singleShot(300, self._load_config)

    # --------------------------------------------------------------- service

    def _restart_service(self) -> None:
        reply = QMessageBox.question(
            self,
            "确认重启服务",
            "重启服务会中断所有客户端上报，且所有用户需要重新登录。确定继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._run(partial(self._api.restart), self._on_restart_ok)

    def _on_restart_ok(self, data: Dict[str, Any]) -> None:
        data = data or {}
        InfoBar.success(
            title="重启已触发",
            content=data.get("message") or "服务重启指令已发送",
            parent=self.window(),
            duration=5000,
        )
        QTimer.singleShot(100, self._logout)

    def _start_ai(self) -> None:
        self._run(partial(self._api.ai_start), self._on_service_ok)

    def _stop_ai(self) -> None:
        reply = QMessageBox.question(
            self,
            "确认停止 AI 任务",
            "停止后所有设备的定时 AI 总结将不再生成，确定继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._run(partial(self._api.ai_stop), self._on_service_ok)

    def _on_service_ok(self, data: Dict[str, Any]) -> None:
        data = data or {}
        InfoBar.success(
            title="操作成功",
            content=data.get("message") or "操作已完成",
            parent=self.window(),
        )

    def _trigger_ai(self) -> None:
        device = self._trigger_device.text().strip() or str(self._config.get("device_id", ""))
        date = self._trigger_date.text().strip() or None
        timezone = int(self._trigger_timezone.value())
        self._run(
            partial(self._api.ai_trigger, device, date, timezone),
            self._on_trigger_ok,
        )

    def _on_trigger_ok(self, data: Dict[str, Any]) -> None:
        data = data or {}
        content = data.get("message") or "AI 总结任务已触发"
        task_id = data.get("taskId")
        if task_id:
            content = f"{content}（任务 ID: {task_id}）"
        InfoBar.success(title="已触发", content=content, parent=self.window(), duration=4000)

    def _update_account(self) -> None:
        username = self._new_username.text().strip() or None
        password = self._new_password.text()
        confirm = self._confirm_password.text()

        if not username and not password:
            InfoBar.error(
                title="无法更新",
                content="请填写新用户名或新密码",
                parent=self.window(),
            )
            return
        if password and password != confirm:
            InfoBar.error(
                title="无法更新",
                content="两次输入的密码不一致",
                parent=self.window(),
            )
            return

        self._run(
            partial(self._api.update_account, username, password or None),
            self._on_account_updated,
        )

    def _on_account_updated(self, data: Dict[str, Any]) -> None:
        data = data or {}
        InfoBar.success(
            title="账户已更新",
            content=data.get("message") or "账户信息已更新",
            parent=self.window(),
        )
        self._new_username.clear()
        self._new_password.clear()
        self._confirm_password.clear()
        if data.get("requireRelogin"):
            self._logout()
            InfoBar.warning(
                title="需要重新登录",
                content="账户信息已变更，请使用新凭据重新登录",
                parent=self.window(),
            )

    # ------------------------------------------------------------------ infra

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in self._action_buttons:
            button.setEnabled(not busy)
        for widget in self._field_widgets.values():
            widget.setEnabled(not busy)
        self._login_button.setEnabled(not busy and self._login_allowed)

    def _run(self, fn, on_ok) -> None:
        if self._busy:
            return
        self._set_busy(True)
        task = ApiTask(fn, self)
        task.finished_ok.connect(on_ok)
        task.failed.connect(self._on_request_failed)
        task.auth_failed.connect(self._on_auth_failed)
        task.finished.connect(lambda: self._set_busy(False))
        self._task = task
        task.start()

    def _on_request_failed(self, message: str) -> None:
        if not self._api.is_authenticated:
            self._login_status.setText(message)
        InfoBar.error(title="操作失败", content=message, parent=self.window())
