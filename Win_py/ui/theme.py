"""主题相关的小工具：让文字颜色跟随浅色/深色主题。"""

from typing import Optional

from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import BodyLabel

PRIMARY_COLOR = (QColor("#1a1a1a"), QColor("#ffffff"))
SECONDARY_COLOR = (QColor("#6b6b6b"), QColor("#a8a8a8"))


def body_label(
    text: str = "",
    parent: Optional[QWidget] = None,
    secondary: bool = False,
    size: Optional[int] = None,
    bold: bool = False,
) -> BodyLabel:
    """创建跟随主题的 BodyLabel。

    字号与字重通过 QFont 设置，避免用 setStyleSheet 覆盖掉主题文字颜色。
    """
    label = BodyLabel(text, parent)
    if size or bold:
        font = QFont(label.font())
        if size:
            font.setPixelSize(size)
        font.setBold(bold)
        label.setFont(font)
    return restyle(label, secondary)


def restyle(label: BodyLabel, secondary: bool = False) -> BodyLabel:
    """为已存在的 BodyLabel 设置主题自适应颜色。"""
    label.setTextColor(*(SECONDARY_COLOR if secondary else PRIMARY_COLOR))
    return label


def set_status_color(label: BodyLabel, running: bool) -> BodyLabel:
    """设置状态文字颜色（不依赖背景样式，切换主题后依然生效）。"""
    if running:
        label.setTextColor(QColor("#15803d"), QColor("#4ade80"))
    else:
        label.setTextColor(QColor("#6b7280"), QColor("#9ca3af"))
    return label
