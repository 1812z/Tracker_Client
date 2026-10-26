"""统计仪表盘：总览、日/周/月图表与应用使用明细。"""

from functools import partial
from typing import Any, Dict, List, Tuple

from PyQt5.QtChart import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QValueAxis,
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CardWidget,
    ComboBox,
    InfoBar,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    SegmentedWidget,
    SubtitleLabel,
    TitleLabel,
    isDarkTheme,
)

from ui.theme import body_label
from ui.workers import ApiTask

COLOR_BLUE = "#2563eb"
COLOR_GREEN = "#16a34a"
COLOR_ORANGE = "#d97706"
COLOR_PURPLE = "#7c3aed"
COLOR_BAR = "#3b82f6"
COLOR_BAR_LIGHT = "#60a5fa"
COLOR_ACCENT = "#22d3ee"
COLOR_ACCENT_LIGHT = "#0891b2"
DONUT_COLORS = [
    "#f97316",
    "#60a5fa",
    "#22c55e",
    "#a855f7",
    "#facc15",
    "#14b8a6",
    "#94a3b8",
]
WEEK_LABELS = ["本周", "上周", "上上周", "3 周前"]
MONTH_LABELS = ["本月", "上月", "上上月", "3 月前"]


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_minutes(minutes: float) -> str:
    total = int(round(minutes))
    if total < 60:
        return f"{total} 分钟"
    return f"{total // 60} 小时 {total % 60} 分钟"


class StatCard(QFrame):
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"QFrame {{ background-color: {color}; border-radius: 10px; }}")
        self.setMinimumHeight(88)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._title = body_label(title)
        self._title.setStyleSheet("color: rgba(255,255,255,0.82); font-size: 12px;")
        self._value = body_label("—")
        self._value.setWordWrap(True)
        self._value.setStyleSheet(
            "color: white; font-size: 20px; font-weight: 600;"
        )
        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class StatsPage(QWidget):
    def __init__(self, config, server_api, parent=None):
        super().__init__(parent)
        self.setObjectName("statsPage")
        self._config = config
        self._server_api = server_api
        self._mode = "day"
        self._task = None
        self._loaded = False
        self._expanded = False
        self._apps_sorted: List[Tuple[str, float]] = []
        self._apps_total = 0.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        outer.addWidget(scroll)
        self._scroll = scroll

        container = QWidget()
        scroll.setWidget(container)
        self._container = container

        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)
        layout.addWidget(TitleLabel("使用统计"))

        layout.addWidget(self._build_toolbar())
        layout.addLayout(self._build_overview())
        layout.addWidget(self._build_main_chart_card())
        layout.addLayout(self._build_chart_row())
        layout.addWidget(self._build_usage_card())
        layout.addStretch(1)

        self._range.currentItemChanged.connect(self._on_mode_changed)
        self._date_edit.dateChanged.connect(lambda _date: self._load())
        self._period_combo.currentIndexChanged.connect(lambda _index: self._load())
        self._refresh_button.clicked.connect(self._load)
        self._expand_button.clicked.connect(self._toggle_expanded)

    # ------------------------------------------------------------------- ui

    def _build_toolbar(self) -> CardWidget:
        card = CardWidget(self._container)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        self._range = SegmentedWidget()
        self._range.addItem("day", "日")
        self._range.addItem("week", "周")
        self._range.addItem("month", "月")
        self._range.setCurrentItem("day")
        layout.addWidget(self._range)

        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_edit.setMaximumDate(QDate.currentDate())
        layout.addWidget(self._date_edit)

        self._period_combo = ComboBox()
        self._period_combo.addItems(WEEK_LABELS)
        self._period_combo.setVisible(False)
        layout.addWidget(self._period_combo)

        self._refresh_button = PrimaryPushButton("刷新")
        layout.addWidget(self._refresh_button)
        layout.addStretch(1)

        self._status_label = body_label("")
        layout.addWidget(self._status_label)
        return card

    def _build_overview(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        self._card_apps = StatCard("应用总数", COLOR_BLUE, self._container)
        self._card_total = StatCard("使用总时长", COLOR_GREEN, self._container)
        self._card_top = StatCard("最常用应用", COLOR_ORANGE, self._container)
        self._card_active = StatCard("最活跃时段", COLOR_PURPLE, self._container)
        for card in (
            self._card_apps,
            self._card_total,
            self._card_top,
            self._card_active,
        ):
            row.addWidget(card, 1)
        return row

    def _new_card(self, title: str) -> Tuple[CardWidget, QVBoxLayout, SubtitleLabel]:
        card = CardWidget(self._container)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        title_label = SubtitleLabel(title)
        layout.addWidget(title_label)
        return card, layout, title_label

    def _create_chart_view(self, min_height: int = 220) -> QChartView:
        chart = QChart()
        chart.setBackgroundVisible(False)
        chart.legend().setVisible(False)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTheme(QChart.ChartThemeDark if isDarkTheme() else QChart.ChartThemeLight)
        view = QChartView(chart)
        view.setRenderHint(QPainter.Antialiasing)
        view.setMinimumHeight(min_height)
        return view

    def _build_main_chart_card(self) -> CardWidget:
        card, layout, self._main_title = self._new_card("24 小时使用时长")
        self._main_view = self._create_chart_view(230)
        layout.addWidget(self._main_view)
        return card

    def _build_chart_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        donut_card, donut_layout, _ = self._new_card("应用使用占比")
        self._donut_view = self._create_chart_view(250)
        self._donut_view.chart().legend().setVisible(True)
        self._donut_view.chart().legend().setAlignment(Qt.AlignRight)
        donut_layout.addWidget(self._donut_view)
        row.addWidget(donut_card, 1)

        app_card, app_layout, self._app_title = self._new_card("应用使用时段")
        self._app_view = self._create_chart_view(250)
        app_layout.addWidget(self._app_view)
        row.addWidget(app_card, 1)
        return row

    def _build_usage_card(self) -> CardWidget:
        card = CardWidget(self._container)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("应用使用明细"))
        header.addStretch(1)
        self._expand_button = PushButton("展开查看全部")
        self._expand_button.setVisible(False)
        header.addWidget(self._expand_button)
        layout.addLayout(header)

        self._usage_layout = QVBoxLayout()
        self._usage_layout.setSpacing(10)
        layout.addLayout(self._usage_layout)
        return card

    # ----------------------------------------------------------------- data

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._load()

    def on_config_saved(self) -> None:
        self._loaded = False
        if self.isVisible():
            self._loaded = True
            self._load()

    def apply_theme(self) -> None:
        theme = QChart.ChartThemeDark if isDarkTheme() else QChart.ChartThemeLight
        for view in (self._main_view, self._donut_view, self._app_view):
            view.chart().setTheme(theme)
        # 主题切换后重建明细行，让文字与进度条颜色跟随主题。
        if self._apps_sorted:
            self._rebuild_usage_rows()

    def _on_mode_changed(self, route_key: str) -> None:
        self._mode = route_key
        is_day = route_key == "day"
        self._date_edit.setVisible(is_day)
        self._period_combo.setVisible(not is_day)

        if route_key == "week":
            self._set_period_items(WEEK_LABELS)
        elif route_key == "month":
            self._set_period_items(MONTH_LABELS)

        self._load()

    def _set_period_items(self, labels: List[str]) -> None:
        self._period_combo.blockSignals(True)
        self._period_combo.clear()
        self._period_combo.addItems(labels)
        self._period_combo.setCurrentIndex(0)
        self._period_combo.blockSignals(False)

    def _load(self) -> None:
        if not self._config.is_query_configured():
            self._status_label.setText("请先在配置中填写 API 地址与设备 ID")
            return
        if self._task is not None and self._task.isRunning():
            return

        if self._mode == "day":
            date_text = self._date_edit.date().toString("yyyy-MM-dd")
            fn = partial(self._server_api.fetch_stats, None, date_text)
        elif self._mode == "week":
            offset = -self._period_combo.currentIndex()
            fn = partial(self._server_api.fetch_weekly, None, offset, None)
        else:
            offset = -self._period_combo.currentIndex()
            fn = partial(self._server_api.fetch_monthly, None, offset, None)

        self._set_busy(True)
        task = ApiTask(fn, self)
        task.finished_ok.connect(self._render)
        task.failed.connect(self._on_error)
        task.finished.connect(lambda: self._set_busy(False))
        self._task = task
        task.start()

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self._range,
            self._date_edit,
            self._period_combo,
            self._refresh_button,
        ):
            widget.setEnabled(not busy)
        if busy:
            self._status_label.setText("加载中…")

    def _on_error(self, message: str) -> None:
        self._status_label.setText(message)
        InfoBar.error(title="加载失败", content=message, parent=self.window(), duration=3000)

    def _render(self, data: Dict[str, Any]) -> None:
        if self._mode == "day":
            self._render_day(data or {})
        else:
            self._render_period(data or {})

    def _render_day(self, data: Dict[str, Any]) -> None:
        total = _to_float(data.get("totalUsage", data.get("total", 0)))
        raw_apps = data.get("appStats")
        if not isinstance(raw_apps, dict):
            raw_apps = data.get("apps") if isinstance(data.get("apps"), dict) else {}
        apps = {str(key): _to_float(value) for key, value in raw_apps.items()}

        raw_hours = data.get("hourlyStats")
        if not isinstance(raw_hours, list):
            raw_hours = data.get("hours") if isinstance(data.get("hours"), list) else []
        hours = [_to_float(value) for value in raw_hours][:24]
        hours.extend([0.0] * (24 - len(hours)))

        raw_app_hours = data.get("appHourlyStats")
        if not isinstance(raw_app_hours, dict):
            raw_app_hours = data.get("appHours") if isinstance(data.get("appHours"), dict) else {}

        labels = [f"{hour}时" for hour in range(24)]
        top_app = max(apps, key=apps.get) if apps else ""
        active_hour = max(range(24), key=lambda index: hours[index]) if any(hours) else -1
        active_label = f"{active_hour}时" if active_hour >= 0 else "—"

        self._card_active.set_title("最活跃时段")
        self._set_overview(apps, total, top_app, active_label)

        date_text = self._date_edit.date().toString("yyyy-MM-dd")
        if not apps and total <= 0:
            self._status_label.setText(f"{date_text} · 暂无数据")
        else:
            self._status_label.setText(f"{date_text} · 共 {len(apps)} 个应用")

        self._main_title.setText("24 小时使用时长")
        self._render_bar(self._main_view, labels, hours, COLOR_BAR)

        self._render_donut(apps)

        app_values = []
        if top_app and isinstance(raw_app_hours.get(top_app), list):
            app_values = [_to_float(value) for value in raw_app_hours.get(top_app, [])][:24]
        app_values.extend([0.0] * (24 - len(app_values)))
        self._app_title.setText(
            f"24 小时应用使用统计：{top_app}" if top_app else "24 小时应用使用统计"
        )
        self._render_bar(self._app_view, labels, app_values, COLOR_BAR_LIGHT)

        self._render_usage(apps, total)

    def _render_period(self, data: Dict[str, Any]) -> None:
        raw_daily = data.get("dailyTotals")
        if not isinstance(raw_daily, dict):
            raw_daily = data.get("dailyStats") if isinstance(data.get("dailyStats"), dict) else {}
        daily = {str(key): _to_float(value) for key, value in raw_daily.items()}
        days = sorted(daily)

        raw_app_daily = data.get("appDailyStats")
        if not isinstance(raw_app_daily, dict):
            raw_app_daily = {}
        app_daily: Dict[str, Dict[str, float]] = {}
        for app, per_day in raw_app_daily.items():
            if isinstance(per_day, dict):
                app_daily[str(app)] = {
                    str(day): _to_float(value) for day, value in per_day.items()
                }

        apps = {
            app: sum(per_day.values())
            for app, per_day in app_daily.items()
            if per_day
        }
        total = sum(daily.values())
        labels = [day[5:] if len(day) >= 10 else day for day in days]
        values = [daily[day] for day in days]
        top_app = max(apps, key=apps.get) if apps else ""

        if days:
            active_day = max(days, key=lambda day: daily[day])
            active_label = active_day[5:] if len(active_day) >= 10 else active_day
        else:
            active_label = "—"

        self._card_active.set_title("最活跃日期")
        self._set_overview(apps, total, top_app, active_label)

        range_info = data.get("weekRange") or data.get("monthRange") or {}
        if isinstance(range_info, dict) and range_info.get("start") and range_info.get("end"):
            range_label = f"{range_info['start']} ~ {range_info['end']}"
        elif days:
            range_label = f"{days[0]} ~ {days[-1]}"
        else:
            range_label = "—"

        if not apps and total <= 0:
            self._status_label.setText(f"{range_label} · 暂无数据")
        else:
            self._status_label.setText(f"{range_label} · 共 {len(apps)} 个应用")

        period_title = "每周每日使用时长" if self._mode == "week" else "每月每日使用时长"
        self._main_title.setText(period_title)
        self._render_bar(self._main_view, labels, values, COLOR_BAR)

        self._render_donut(apps)

        app_values = []
        if top_app:
            per_day = app_daily.get(top_app, {})
            app_values = [per_day.get(day, 0.0) for day in days]
        self._app_title.setText(
            f"每日应用使用统计：{top_app}" if top_app else "每日应用使用统计"
        )
        self._render_bar(self._app_view, labels, app_values, COLOR_BAR_LIGHT)

        self._render_usage(apps, total)

    def _set_overview(
        self,
        apps: Dict[str, float],
        total: float,
        top_app: str,
        active_label: str,
    ) -> None:
        self._card_apps.set_value(str(len(apps)))
        self._card_total.set_value(format_minutes(total))
        self._card_top.set_value(top_app or "—")
        self._card_active.set_value(active_label or "—")

    # ---------------------------------------------------------------- charts

    def _render_bar(
        self,
        view: QChartView,
        labels: List[str],
        values: List[float],
        color: str,
    ) -> None:
        chart = view.chart()
        chart.removeAllSeries()
        for axis in chart.axes():
            chart.removeAxis(axis)
        if not values:
            return

        display_labels = labels
        if len(labels) > 24:
            step = 5
        elif len(labels) > 12:
            step = 3
        else:
            step = 1
        if step > 1:
            display_labels = [
                label if index % step == 0 else ""
                for index, label in enumerate(labels)
            ]

        bar_set = QBarSet("分钟")
        bar_set.setColor(QColor(color))
        for value in values:
            bar_set.append(float(value))
        series = QBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(False)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(display_labels)
        axis_x.setLabelsFont(QFont("Segoe UI", 8))
        if len(labels) > 24:
            axis_x.setLabelsVisible(False)
        elif step > 1:
            axis_x.setLabelsAngle(-45)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setRange(0, max(1.0, max(values)))
        axis_y.setLabelFormat("%.0f")
        axis_y.setTitleText("分钟")
        axis_y.setLabelsFont(QFont("Segoe UI", 8))
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

    def _render_donut(self, apps: Dict[str, float]) -> None:
        chart = self._donut_view.chart()
        chart.removeAllSeries()
        if not apps:
            chart.legend().setVisible(False)
            return

        items = sorted(apps.items(), key=lambda item: item[1], reverse=True)
        shown = items[:6]
        other = sum(value for _name, value in items[6:])
        if other > 0:
            shown.append(("其他", other))

        series = QPieSeries()
        series.setHoleSize(0.45)
        series.setPieSize(0.85)
        for index, (name, value) in enumerate(shown):
            slice_item = series.append(name, value)
            slice_item.setColor(QColor(DONUT_COLORS[index % len(DONUT_COLORS)]))
            slice_item.setBorderColor(QColor("transparent"))
            slice_item.setLabelVisible(False)

        chart.addSeries(series)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignRight)
        chart.legend().setFont(QFont("Segoe UI", 8))

    # ----------------------------------------------------------------- usage

    def _render_usage(self, apps: Dict[str, float], total: float) -> None:
        self._apps_sorted = sorted(apps.items(), key=lambda item: item[1], reverse=True)
        self._apps_total = total
        self._expanded = False
        self._rebuild_usage_rows()

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self._rebuild_usage_rows()

    def _rebuild_usage_rows(self) -> None:
        while self._usage_layout.count():
            item = self._usage_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        total_count = len(self._apps_sorted)
        visible_count = total_count if self._expanded else min(8, total_count)
        for app, minutes in self._apps_sorted[:visible_count]:
            self._usage_layout.addWidget(
                self._usage_row(app, minutes, self._apps_total)
            )

        if total_count == 0:
            empty = body_label("暂无使用数据", secondary=True)
            self._usage_layout.addWidget(empty)
            self._expand_button.setVisible(False)
            return

        self._expand_button.setVisible(total_count > 8)
        self._expand_button.setText(
            "收起" if self._expanded else f"展开查看全部（{total_count}）"
        )

    @staticmethod
    def _usage_row(app: str, minutes: float, total: float) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(4)

        header = QHBoxLayout()
        name = body_label(app, bold=True)
        time_label = body_label(format_minutes(minutes))
        percent = body_label(
            f"{minutes / total * 100:.0f}%" if total > 0 else "—", secondary=True
        )

        header.addWidget(name)
        header.addStretch(1)
        header.addWidget(time_label)
        header.addSpacing(12)
        header.addWidget(percent)
        layout.addLayout(header)

        bar = ProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(round(minutes / total * 100)) if total > 0 else 0)
        bar.setFixedHeight(5)
        bar.setCustomBackgroundColor(QColor(0, 0, 0, 32), QColor(255, 255, 255, 40))
        bar.setCustomBarColor(QColor(COLOR_ACCENT_LIGHT), QColor(COLOR_ACCENT))
        layout.addWidget(bar)
        return row
