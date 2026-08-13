from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gas_sensor_daq.ui.widgets.cards import compact_section_card


class MFCMonitorPanel:
    """Read-only monitor for the six MFC channels and their live flows."""

    def __init__(self, zero_all_callback):
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(4)

        self.rack_status_label = QLabel("Read-only | rack not connected")
        self.rack_status_label.setObjectName("mfcRackStatus")
        content.addWidget(self.rack_status_label)
        content.addLayout(self._table_header())

        self.channel_monitor = {}
        for index in range(1, 7):
            row, widgets = self._channel_row(index)
            content.addWidget(row)
            self.channel_monitor[index] = widgets

        self.zero_setpoints_button = QPushButton("Zero all setpoints")
        self.zero_setpoints_button.setObjectName("mfcZeroButton")
        self.zero_setpoints_button.setToolTip(
            "Set all MFC setpoints to zero when no experiment is running"
        )
        self.zero_setpoints_button.clicked.connect(zero_all_callback)
        content.addSpacing(4)
        content.addWidget(self.zero_setpoints_button)

        self.card = compact_section_card("MFC Monitor", content)

    @staticmethod
    def _table_header():
        header = QGridLayout()
        header.setContentsMargins(4, 2, 4, 1)
        header.setHorizontalSpacing(8)
        for column in range(3):
            header.setColumnMinimumWidth(column, 0)
            header.setColumnStretch(column, 1)
        for column, text in enumerate(("Channel", "Actual\n(mln/min)", "Setpoint\n(mln/min)")):
            label = QLabel(text)
            label.setObjectName("mfcMonitorHeader")
            if column in (1, 2):
                label.setAlignment(Qt.AlignCenter)
            header.addWidget(label, 0, column)
        return header

    @staticmethod
    def _channel_row(index):
        row = QFrame()
        row.setObjectName("mfcChannelMonitorRow")
        row.setFixedHeight(42)

        layout = QGridLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setHorizontalSpacing(8)
        for column in range(3):
            layout.setColumnMinimumWidth(column, 0)
            layout.setColumnStretch(column, 1)

        channel_cell = QWidget()
        channel_layout = QVBoxLayout(channel_cell)
        channel_layout.setContentsMargins(0, 0, 0, 0)
        channel_layout.setSpacing(0)
        channel_line = QHBoxLayout()
        channel_line.setContentsMargins(0, 0, 0, 0)
        channel_line.setSpacing(5)
        channel_label = QLabel(f"MFC {index}")
        channel_label.setObjectName("mfcChannelName")
        channel_label.setProperty("channel", str(index))
        channel_line.addWidget(channel_label)
        channel_line.addStretch()
        detail_label = QLabel()
        detail_label.setObjectName("mfcChannelSerial")
        detail_label.setProperty("state", "serial")
        detail_label.setVisible(False)
        channel_layout.addLayout(channel_line)
        channel_layout.addWidget(detail_label)

        actual_label = QLabel("--")
        actual_label.setObjectName("mfcChannelValue")
        actual_label.setAlignment(Qt.AlignCenter)
        setpoint_label = QLabel("--")
        setpoint_label.setObjectName("mfcChannelValue")
        setpoint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(channel_cell, 0, 0)
        layout.addWidget(actual_label, 0, 1)
        layout.addWidget(setpoint_label, 0, 2)
        return row, {
            "row": row,
            "actual": actual_label,
            "setpoint": setpoint_label,
            "detail": detail_label,
        }
