"""关于页。"""

from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    CardWidget,
    HyperlinkButton,
    TitleLabel,
)

from ui.theme import body_label
from app import __version__


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aboutPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.addWidget(TitleLabel("关于"))
        layout.addSpacing(10)

        info_card = CardWidget(self)
        info_layout = QVBoxLayout(info_card)
        info_layout.addWidget(TitleLabel("运行时间跟踪器"))
        info_layout.addWidget(body_label(f"版本: {__version__}"))
        info_layout.addWidget(body_label("开发者: CSSQY"))
        info_layout.addSpacing(8)
        description = body_label(
            "一个设备使用情况监控工具，可以实时跟踪设备上运行的应用程序，"
            "查看使用统计与设备状态，并将数据上报到服务器进行分析。"
        )
        description.setWordWrap(True)
        info_layout.addWidget(description)
        layout.addWidget(info_card)
        layout.addSpacing(16)

        project_card = CardWidget(self)
        project_layout = QVBoxLayout(project_card)
        project_layout.addWidget(TitleLabel("项目链接"))
        project_layout.addWidget(
            HyperlinkButton(
                "https://github.com/CSSQY/RunTime_Tracker_Client_Windows",
                "GitHub - RunTime_Tracker_Client_Windows",
            )
        )
        project_layout.addWidget(
            HyperlinkButton(
                "https://github.com/1812z/RunTime_Tracker",
                "GitHub - RunTime_Tracker (服务端)",
            )
        )
        project_layout.addWidget(
            HyperlinkButton(
                "https://github.com/1812z/Tracker_Client",
                "GitHub - Tracker_Client (客户端)",
            )
        )
        project_layout.addWidget(
            HyperlinkButton(
                "https://github.com/zhiyiYo/PyQt-Fluent-Widgets",
                "GitHub - PyQt-Fluent-Widgets (UI框架)",
            )
        )
        layout.addWidget(project_card)
        layout.addSpacing(16)

        license_card = CardWidget(self)
        license_layout = QVBoxLayout(license_card)
        license_layout.addWidget(TitleLabel("开源许可"))
        license_layout.addWidget(body_label("本项目采用 MIT 许可证。"))
        layout.addWidget(license_card)
        layout.addStretch(1)
