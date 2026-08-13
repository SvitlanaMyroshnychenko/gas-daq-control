from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)


class ApplicationToolbar(QFrame):
    """Top-level file controls and the persistent application message bar."""

    def __init__(
        self,
        filename_input: QLineEdit,
        choose_location_button: QPushButton,
        format_selector: QComboBox,
        start_button: QPushButton,
        stop_button: QPushButton,
        message_label: QLabel,
        dismiss_message: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toolbar")
        self.filename_input = filename_input
        self.choose_location_button = choose_location_button
        self.format_selector = format_selector
        self.start_button = start_button
        self.stop_button = stop_button
        self.message_label = message_label
        self._dismiss_message = dismiss_message

        self._build_ui()
        self.reflow()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.controls = QFrame()
        self.controls.setObjectName("toolbarControls")
        self.controls_layout = QGridLayout(self.controls)
        self.controls_layout.setContentsMargins(12, 10, 12, 10)
        self.controls_layout.setHorizontalSpacing(6)
        self.controls_layout.setVerticalSpacing(8)

        save_location = self._save_location_control()
        save_location.setFixedWidth(300)
        self.save_group = self._inline_group("File:", save_location, 341)
        format_control = self._format_control()
        format_control.setFixedWidth(120)
        self.format_group = self._inline_group("Format:", format_control, 177)
        self.storage_group = self._cluster(self.save_group, self.format_group)
        self.actions_group = self._cluster(self.start_button, self.stop_button)
        self.rows = [self._control_row() for _ in range(3)]

        self.file_path_label = QLabel()
        self.file_path_label.setObjectName("toolbarFilePath")
        self.file_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.message_bar = self._message_bar()
        layout.addWidget(self.controls)
        layout.addWidget(self.message_bar)

    def reflow(self) -> None:
        while self.controls_layout.count():
            self.controls_layout.takeAt(0)
        for row in self.rows:
            row.hide()

        self.controls.setFixedHeight(80)
        self._populate_row(self.rows[0], (self.storage_group,), (self.actions_group,))
        self.controls_layout.addWidget(self.rows[0], 0, 0, 1, 10)
        self.controls_layout.addWidget(self.file_path_label, 1, 0, 1, 10)
        self.adjust_height()

    def adjust_height(self) -> None:
        message_height = self.message_bar.height() + 6 if not self.message_bar.isHidden() else 0
        self.setFixedHeight(self.controls.height() + message_height)

    def _inline_group(self, title: str, content: QWidget, width: int) -> QWidget:
        group = QWidget()
        group.setObjectName("toolbarInlineGroup")
        group.setFixedSize(width, 32)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel(title)
        label.setObjectName("toolbarInlineLabel")
        label.setFixedWidth(52 if title == "Format:" else 36)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(label)
        layout.addWidget(content)
        return group

    @staticmethod
    def _cluster(*widgets: QWidget) -> QWidget:
        cluster = QWidget()
        cluster.setObjectName("toolbarCluster")
        cluster.setFixedHeight(32)
        layout = QHBoxLayout(cluster)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for widget in widgets:
            layout.addWidget(widget)
        return cluster

    @staticmethod
    def _control_row() -> QWidget:
        row = QWidget()
        row.setObjectName("toolbarControlRow")
        row.setFixedHeight(32)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        return row

    @staticmethod
    def _populate_row(
        row: QWidget,
        leading_widgets: tuple[QWidget, ...],
        trailing_widgets: tuple[QWidget, ...],
    ) -> None:
        layout = row.layout()
        while layout.count():
            layout.takeAt(0)
        for widget in leading_widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        for widget in trailing_widgets:
            layout.addWidget(widget)
        row.show()

    def _save_location_control(self) -> QFrame:
        control = QFrame()
        control.setObjectName("fileLocationControl")
        control.setFixedHeight(32)
        layout = QHBoxLayout(control)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(7)

        icon_label = QLabel()
        icon_label.setObjectName("fileLocationIcon")
        icon_label.setFixedSize(18, 18)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(
            self.style().standardIcon(QStyle.SP_FileIcon).pixmap(QSize(16, 16))
        )

        self.choose_location_button.setObjectName("fileLocationBrowseButton")
        layout.addWidget(icon_label)
        layout.addWidget(self.filename_input, 1)
        layout.addWidget(self.choose_location_button)
        return control

    def _format_control(self) -> QFrame:
        control = QFrame()
        control.setObjectName("formatControl")
        control.setFixedHeight(32)
        layout = QHBoxLayout(control)
        layout.setContentsMargins(8, 0, 2, 0)
        layout.setSpacing(5)

        icon_label = QLabel()
        icon_label.setObjectName("formatControlIcon")
        icon_label.setFixedSize(16, 16)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(
            self.style().standardIcon(QStyle.SP_FileIcon).pixmap(QSize(14, 14))
        )
        layout.addWidget(icon_label)
        layout.addWidget(self.format_selector, 1)
        return control

    def _message_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("systemMessageBar")
        bar.setFixedHeight(34)
        bar.setProperty("state", "idle")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(7)

        self.message_icon = QLabel("i")
        self.message_icon.setObjectName("systemMessageIcon")
        self.message_icon.setProperty("state", "idle")
        self.message_icon.setAlignment(Qt.AlignCenter)
        self.message_icon.setFixedSize(14, 14)
        self.message_label.setProperty("state", "idle")

        dismiss_button = QPushButton("x")
        dismiss_button.setObjectName("systemMessageDismissButton")
        dismiss_button.setFixedSize(18, 18)
        dismiss_button.setToolTip("Dismiss message")
        dismiss_button.clicked.connect(self._dismiss_message)
        layout.addWidget(self.message_icon)
        layout.addWidget(self.message_label, 1)
        layout.addWidget(dismiss_button)
        return bar
