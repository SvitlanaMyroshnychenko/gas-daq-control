from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from gas_sensor_daq.ui.widgets.cards import section_card


class DeviceStatusPanel:
    """Visual container for multimeter and MFC rack connection controls."""

    def __init__(
        self,
        *,
        multimeter_mode,
        multimeter_device,
        multimeter_resource,
        connect_multimeter,
        scan_multimeter,
        multimeter_status,
        multimeter_summary,
        mfc_mode,
        mfc_port,
        connect_mfc,
        scan_mfc,
        mfc_status,
        mfc_note,
        mfc_summary,
        toggle_setup,
    ):
        self.setup_bodies = []
        self.control_rows = []

        multimeter_row, self.multimeter_status_dot = self._device_row(
            "Multimeter",
            multimeter_summary,
            (
                ("Mode", multimeter_mode, connect_multimeter),
                ("Device", multimeter_device, scan_multimeter),
            ),
            (multimeter_resource, multimeter_status),
        )
        mfc_row, self.mfc_status_dot = self._device_row(
            "MFC Rack (6 nodes)",
            mfc_summary,
            (
                ("Mode", mfc_mode, connect_mfc),
                ("Rack", mfc_port, scan_mfc),
            ),
            (mfc_status, mfc_note),
        )

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(6)
        content.addWidget(multimeter_row)
        content.addWidget(mfc_row)

        self.chevron = QPushButton()
        self.chevron.setObjectName("sectionChevron")
        self.chevron.setFixedSize(24, 22)
        self.chevron.setCheckable(True)
        self.chevron.setChecked(False)
        self.chevron.clicked.connect(toggle_setup)

        self.card = section_card("Device Status", None, content, header_widget=self.chevron)

    def _device_row(self, title, summary_label, settings, detail_widgets):
        row = QFrame()
        row.setObjectName("deviceRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(6)

        header, status_dot = self._header(title, summary_label)
        layout.addLayout(header)

        body = QFrame()
        body.setObjectName("deviceSetupPanel")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 5, 0, 0)
        body_layout.setSpacing(6)
        for label, selector, button in settings:
            body_layout.addLayout(self._setting_row(label, selector, button))
        for widget in detail_widgets:
            body_layout.addWidget(widget)
        body.setVisible(False)

        self.setup_bodies.append(body)
        self.control_rows.append(row)
        row.setFixedHeight(46)
        layout.addWidget(body)
        return row, status_dot

    @staticmethod
    def _header(title, status_label):
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("sectionLabel")
        status_dot = QLabel()
        status_dot.setObjectName("deviceStatusDot")
        status_dot.setProperty("state", "connected")
        status_dot.setFixedSize(8, 8)
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(status_dot)
        header.addWidget(status_label)
        return header, status_dot

    @staticmethod
    def _setting_row(label_text, selector, button):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("metricName")
        label.setFixedWidth(42)
        selector.setFixedWidth(130)
        row.addWidget(label)
        row.addWidget(selector, 1)
        row.addWidget(button)
        return row
