from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)


def scroll_panel(widget):
    area = QScrollArea()
    area.setObjectName("panelScroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    area.setWidget(widget)
    area.setMinimumWidth(widget.minimumWidth())
    area.setMaximumWidth(widget.maximumWidth())
    area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
    return area


def section_card(title, icon, content_layout, expanding=False, header_widget=None):
    card = QFrame()
    card.setObjectName("sectionCard")
    vertical_policy = QSizePolicy.Expanding if expanding else QSizePolicy.Preferred
    card.setSizePolicy(QSizePolicy.Preferred, vertical_policy)

    layout = QVBoxLayout()
    layout.setContentsMargins(10, 8, 10, 10)
    layout.setSpacing(8)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(8)

    title_label = QLabel(title)
    title_label.setObjectName("sectionTitle")

    if icon is not None:
        icon_label = QLabel()
        icon_label.setObjectName("sectionIcon")
        icon_label.setPixmap(icon.pixmap(16, 16))
        header.addWidget(icon_label)
    header.addWidget(title_label)
    header.addStretch()
    if header_widget is not None:
        header.addWidget(header_widget)

    layout.addLayout(header)
    content_frame = QFrame()
    content_frame.setObjectName("logContentFrame")
    content_frame.setLayout(content_layout)
    layout.addWidget(content_frame, 1)
    card.setLayout(layout)
    return card


def compact_section_card(title, content_layout):
    card = QFrame()
    card.setObjectName("compactSectionCard")
    card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    layout = QVBoxLayout()
    layout.setContentsMargins(10, 9, 10, 10)
    layout.setSpacing(8)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(0)

    title_label = QLabel(title)
    title_label.setObjectName("sectionTitle")

    header.addWidget(title_label)
    header.addStretch()

    layout.addLayout(header)
    layout.addLayout(content_layout)
    card.setLayout(layout)
    return card


def graph_card(title, color, content_layout):
    card = QFrame()
    card.setObjectName("graphCard")
    card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

    layout = QVBoxLayout()
    layout.setContentsMargins(14, 11, 14, 12)
    layout.setSpacing(8)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(8)

    dot = QLabel()
    dot.setObjectName("graphDot")
    dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
    dot.setFixedSize(10, 10)

    title_label = QLabel(title)
    title_label.setObjectName("graphTitle")

    header.addWidget(dot)
    header.addWidget(title_label)
    header.addStretch()

    content_frame = QFrame()
    content_frame.setObjectName("logContentFrame")
    content_frame.setLayout(content_layout)
    content_layout.setContentsMargins(0, 0, 0, 12)

    layout.addLayout(header)
    layout.addWidget(content_frame, 1)
    card.setLayout(layout)
    return card


def metric_value(text):
    label = QLabel(text)
    label.setObjectName("metricValue")
    label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return label


def reading_row(name, value_label, color):
    row = QFrame()
    row.setObjectName("compactReadingRow")

    layout = QHBoxLayout()
    layout.setContentsMargins(8, 7, 8, 7)
    layout.setSpacing(8)

    dot = QLabel()
    dot.setObjectName("compactDot")
    dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
    dot.setFixedSize(6, 6)

    name_label = QLabel(name)
    name_label.setObjectName("metricName")

    value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    layout.addWidget(dot)
    layout.addWidget(name_label)
    layout.addStretch()
    layout.addWidget(value_label)

    row.setLayout(layout)
    return row


def state_row(name, value_label):
    row = QFrame()
    row.setObjectName("compactStateRow")

    layout = QHBoxLayout()
    layout.setContentsMargins(8, 7, 8, 7)
    layout.setSpacing(8)

    name_label = QLabel(name)
    name_label.setObjectName("metricName")

    value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    layout.addWidget(name_label)
    layout.addStretch()
    layout.addWidget(value_label)

    row.setLayout(layout)
    return row


def device_status_summary_row(name, status_dot, status_label):
    row = QFrame()
    row.setObjectName("compactStateRow")

    layout = QHBoxLayout()
    layout.setContentsMargins(8, 7, 8, 7)
    layout.setSpacing(8)

    name_label = QLabel(name)
    name_label.setObjectName("sectionLabel")
    layout.addWidget(name_label)
    layout.addStretch()
    layout.addWidget(status_dot)
    layout.addWidget(status_label)

    row.setLayout(layout)
    return row
