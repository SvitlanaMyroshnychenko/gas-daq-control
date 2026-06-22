import math
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap, QPolygon, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

from gas_sensor_daq.core.acquisition_manager import AcquisitionManager
from gas_sensor_daq.devices.visa_discovery import discover_visa_instruments

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None


class Stepper(QWidget):
    def __init__(self, minimum=0, maximum=100, value=0, suffix="", step=1, parent=None):
        super().__init__(parent)
        self.spinbox = QSpinBox()
        self.spinbox.setRange(minimum, maximum)
        self.spinbox.setSingleStep(step)
        self.spinbox.setValue(value)
        self.spinbox.setSuffix(suffix)
        self.spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinbox.setAlignment(Qt.AlignCenter)

        self.minus_button = QPushButton("-")
        self.plus_button = QPushButton("+")
        self.minus_button.setObjectName("stepButton")
        self.plus_button.setObjectName("stepButton")
        self.minus_button.setFixedWidth(30)
        self.plus_button.setFixedWidth(30)

        self.minus_button.clicked.connect(self.spinbox.stepDown)
        self.plus_button.clicked.connect(self.spinbox.stepUp)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.minus_button)
        layout.addWidget(self.spinbox, 1)
        layout.addWidget(self.plus_button)
        self.setLayout(layout)

    def value(self):
        return self.spinbox.value()

    def setValue(self, value):
        self.spinbox.setValue(int(value))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.assets_dir = Path(__file__).resolve().parent / "assets"
        self.setWindowTitle("Gas Sensor DAQ & MFC Control")
        self.setWindowIcon(QIcon(str(self.assets_dir / "microchip.png")))

        self.setMinimumSize(1280, 720)

        self.manager = AcquisitionManager(self)
        self.time_data = []
        self.resistance_data = []
        self.temperature_data = []
        self.event_markers = []
        self.completed_experiment_exists = False
        self.max_log_preview_rows = 5
        self.adjusting_log_columns = False
        self.data_directory = self.manager.data_directory
        self.current_file_path = ""

        self.setup_ui()
        self.connect_manager_signals()
        self.refresh_state_label(self.manager.current_state())

    def setup_ui(self):
        self.status_label = QLabel("IDLE")
        self.status_label.setObjectName("statusBadge")
        self.status_label.setProperty("state", "idle")
        self.status_label.setFixedSize(100, 28)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.file_label = QLabel("No file open")
        self.file_label.setObjectName("mutedLabel")
        self.elapsed_label = QLabel("00:00:00")
        self.elapsed_label.setObjectName("toolbarValue")
        self.rate_label = QLabel("0.5 Hz")
        self.rate_label.setObjectName("toolbarValue")

        self.format_selector = QComboBox()
        self.format_selector.addItems(["CSV", "Excel"])
        self.format_selector.setFixedWidth(100)
        self.format_selector.setFixedHeight(34)
        self.log_rows_selector = QComboBox()
        self.log_rows_selector.setObjectName("logRowsSelector")
        self.log_rows_selector.addItems(["5", "10", "25", "50"])
        self.log_rows_selector.setFixedWidth(52)
        self.log_rows_selector.setFixedHeight(26)
        self.log_rows_selector.setView(QListView())
        self.log_rows_selector.view().setObjectName("logRowsPopup")
        self.log_rows_selector.currentTextChanged.connect(self.on_log_rows_changed)
        self.open_data_folder_button = QPushButton("Open Folder")
        self.open_data_folder_button.setObjectName("logActionButton")
        self.open_data_folder_button.clicked.connect(self.open_data_folder)
        self.view_full_log_button = QPushButton("Full Log")
        self.view_full_log_button.setObjectName("logActionButton")
        self.view_full_log_button.clicked.connect(self.open_current_log)
        self.view_full_log_button.setEnabled(False)
        self.bottom_acquisition_label = QLabel("Acquisition idle")
        self.bottom_acquisition_label.setObjectName("statusLineLabel")
        self.bottom_mode_label = QLabel("Simulation mode ready")
        self.bottom_mode_label.setObjectName("mutedLabel")
        self.manual_mode_frame = QFrame()
        self.manual_mode_frame.setObjectName("warningFrame")
        manual_mode_layout = QHBoxLayout()
        manual_mode_layout.setContentsMargins(9, 8, 9, 8)
        manual_mode_layout.setSpacing(8)
        self.manual_mode_icon = QLabel()
        self.manual_mode_icon.setObjectName("warningIcon")
        self.manual_mode_icon.setPixmap(QPixmap(str(self.assets_dir / "locker.png")).scaled(
            16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))
        self.manual_mode_icon.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.manual_mode_label = QLabel("Simulated MFC mode")
        self.manual_mode_label.setObjectName("warningLabel")
        self.manual_mode_label.setWordWrap(True)
        manual_mode_layout.addWidget(self.manual_mode_icon, 0, Qt.AlignTop)
        manual_mode_layout.addWidget(self.manual_mode_label, 1)
        self.manual_mode_frame.setLayout(manual_mode_layout)
        self.multimeter_mode_selector = QComboBox()
        self.multimeter_mode_selector.addItems(["Simulated", "Real multimeter"])
        self.visa_device_selector = QComboBox()
        self.visa_device_selector.addItem("No scan yet", "")
        self.visa_device_selector.setMinimumWidth(0)
        self.multimeter_resource_input = QLineEdit()
        self.multimeter_resource_input.setPlaceholderText("USB0::...::INSTR")
        self.multimeter_resource_input.setText(self.manager.multimeter_resource)
        self.multimeter_resource_input.setVisible(False)
        self.scan_visa_button = QPushButton("Scan")
        self.connect_multimeter_button = QPushButton("Use")
        self.scan_visa_button.setFixedWidth(52)
        self.connect_multimeter_button.setFixedWidth(68)
        self.multimeter_status_label = QLabel(self.manager.multimeter_status_text())
        self.multimeter_status_label.setObjectName("connectedLabel")
        self.multimeter_status_label.setWordWrap(True)
        self.multimeter_status_label.setMaximumHeight(34)
        self.mfc_status_label = QLabel("Connected: Simulated")
        self.mfc_status_label.setObjectName("connectedLabel")
        self.mfc_status_label.setWordWrap(True)
        self.mfc_status_label.setMaximumHeight(40)
        self.mfc_note_label = QLabel("Real MFC mode is read-only until gas testing is approved.")
        self.mfc_note_label.setObjectName("mutedLabel")
        self.mfc_note_label.setWordWrap(True)
        self.mfc_note_label.setMaximumHeight(28)
        self.multimeter_summary_label = QLabel("Simulated")
        self.multimeter_summary_label.setObjectName("connectedLabel")
        self.mfc_summary_label = QLabel("Simulated")
        self.mfc_summary_label.setObjectName("connectedLabel")
        self.mfc_mode_selector = QComboBox()
        self.mfc_mode_selector.addItems(["Simulated", "Real MFC"])
        self.mfc_port_selector = QComboBox()
        self.mfc_port_selector.addItem(self.manager.mfc_port, self.manager.mfc_port)
        self.scan_mfc_button = QPushButton("Scan")
        self.connect_mfc_button = QPushButton("Use")
        self.scan_mfc_button.setFixedWidth(52)
        self.connect_mfc_button.setFixedWidth(68)

        self.start_button = QPushButton("  Start")
        self.stop_button = QPushButton("  Stop")
        self.start_button.setFixedSize(78, 32)
        self.stop_button.setFixedSize(78, 32)
        self.start_button.setObjectName("startButton")
        self.stop_button.setObjectName("stopButton")
        self.start_button.setIcon(self.create_play_icon(QColor("#15803d")))
        self.stop_button.setIcon(self.create_stop_icon(QColor("#dc2626")))
        self.start_button.setIconSize(QSize(20, 20))
        self.stop_button.setIconSize(QSize(16, 16))
        self.start_button.clicked.connect(self.start_experiment)
        self.stop_button.clicked.connect(
            lambda _checked=False: self.manager.stop_experiment()
        )

        self.nh3_value_label = self.metric_value("--")
        self.air_value_label = self.metric_value("--")
        self.humidity_value_label = self.metric_value("OFF")
        self.heating_value_label = self.metric_value("OFF")

        self.resistance_value_label = self.metric_value("--")
        self.temperature_value_label = self.metric_value("--")
        self.nh3_actual_label = self.metric_value("--")
        self.air_actual_label = self.metric_value("--")
        self.resistance_value_label.setProperty("metricColor", "blue")
        self.temperature_value_label.setProperty("metricColor", "orange")
        self.nh3_actual_label.setProperty("metricColor", "purple")
        self.air_actual_label.setProperty("metricColor", "teal")
        for value_label in (
            self.resistance_value_label,
            self.temperature_value_label,
            self.nh3_actual_label,
            self.air_actual_label,
            self.humidity_value_label,
            self.heating_value_label,
        ):
            value_label.setProperty("compactMetric", "true")

        self.nh3_control = Stepper(0, 100, 0, " sccm")
        self.air_control = Stepper(0, 500, 100, " sccm")
        self.nh3_duration = Stepper(0, 24 * 60 * 60, 0, " s")
        self.air_duration = Stepper(0, 24 * 60 * 60, 0, " s")
        self.humidity_duration = Stepper(0, 24 * 60 * 60, 0, " s")
        self.heating_duration = Stepper(0, 24 * 60 * 60, 0, " s")
        self.environment_countdowns = {}

        self.apply_nh3_button = QPushButton("Apply")
        self.apply_air_button = QPushButton("Apply")
        self.air_purge_button = QPushButton("Air Purge")
        self.humidity_on_button = QPushButton("ON")
        self.humidity_off_button = QPushButton("OFF")
        self.heating_on_button = QPushButton("ON")
        self.heating_off_button = QPushButton("OFF")
        self.humidity_status_label = QLabel("OFF")
        self.heating_status_label = QLabel("OFF")
        self.humidity_status_label.setObjectName("envStatus")
        self.heating_status_label.setObjectName("envStatus")

        self.apply_nh3_button.setObjectName("primaryButton")
        self.apply_air_button.setObjectName("primaryButton")
        self.air_purge_button.setObjectName("secondaryButton")
        for button in (
            self.humidity_on_button,
            self.humidity_off_button,
            self.heating_on_button,
            self.heating_off_button,
        ):
            button.setObjectName("toggleButton")

        self.apply_nh3_button.clicked.connect(self.apply_nh3)
        self.apply_air_button.clicked.connect(self.apply_air)
        self.air_purge_button.clicked.connect(self.manager.air_purge)
        self.humidity_on_button.clicked.connect(
            lambda _checked=False: self.set_humidity(True)
        )
        self.humidity_off_button.clicked.connect(
            lambda _checked=False: self.set_humidity(False)
        )
        self.heating_on_button.clicked.connect(
            lambda _checked=False: self.set_heating(True)
        )
        self.heating_off_button.clicked.connect(
            lambda _checked=False: self.set_heating(False)
        )
        self.setup_environment_countdowns()
        self.scan_visa_button.clicked.connect(self.scan_visa_devices)
        self.connect_multimeter_button.clicked.connect(self.connect_multimeter)
        self.multimeter_mode_selector.currentTextChanged.connect(self.on_multimeter_mode_changed)
        self.visa_device_selector.currentIndexChanged.connect(self.on_visa_device_selected)
        self.scan_mfc_button.clicked.connect(self.scan_mfc_ports)
        self.connect_mfc_button.clicked.connect(self.connect_mfc)
        self.mfc_mode_selector.currentTextChanged.connect(self.on_mfc_mode_changed)

        self.resistance_plot = self.create_plot(
            "Resistance vs Time",
            "Resistance",
            "Ohm",
            "#2563eb",
        )
        self.resistance_curve = self.resistance_plot.plot(
            pen=pg.mkPen(color="#2563eb", width=2)
        )

        self.temperature_plot = self.create_plot(
            "Temperature vs Time",
            "Temperature",
            "°C",
            "#f97316",
        )
        self.temperature_curve = self.temperature_plot.plot(
            pen=pg.mkPen(color="#f97316", width=2)
        )

        self.log_table = QTableWidget(0, 7)
        self.log_table.setHorizontalHeaderLabels([
            "Time",
            "Elapsed (s)",
            "Resistance (Ohm)",
            "Temperature (°C)",
            "Analyte (sccm)",
            "Air (sccm)",
            "Event",
        ])
        self.configure_log_table()

        root = QWidget()
        root.setObjectName("appBackground")
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(10, 8, 10, 10)
        root_layout.setSpacing(8)

        root_layout.addWidget(self.create_toolbar())

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        body_layout.addWidget(self.scroll_panel(self.create_left_panel()), 0)
        body_layout.addWidget(self.create_center_panel(), 1)
        body_layout.addWidget(self.scroll_panel(self.create_right_panel()), 0)

        root_layout.addLayout(body_layout, 1)
        root.setLayout(root_layout)
        self.setCentralWidget(root)

        self.apply_styles()
        self.on_multimeter_mode_changed(self.multimeter_mode_selector.currentText())
        self.on_mfc_mode_changed(self.mfc_mode_selector.currentText())

    def connect_manager_signals(self):
        self.manager.experiment_started.connect(self.on_experiment_started)
        self.manager.experiment_stopped.connect(self.on_experiment_stopped)
        self.manager.elapsed_changed.connect(self.elapsed_label.setText)
        self.manager.data_acquired.connect(self.on_data_acquired)
        self.manager.state_changed.connect(self.refresh_state_label)
        self.manager.device_error.connect(self.on_device_error)
        self.manager.multimeter_changed.connect(self.on_multimeter_changed)
        self.manager.mfc_changed.connect(self.on_mfc_changed)

    def create_toolbar(self):
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(68)

        layout = QHBoxLayout()
        layout.setContentsMargins(18, 8, 12, 8)
        layout.setSpacing(14)

        layout.addWidget(self.toolbar_status_block(), 1)
        layout.addStretch(1)
        layout.addWidget(self.toolbar_divider())
        layout.addWidget(self.toolbar_block("Elapsed", self.elapsed_label), 0)
        layout.addWidget(self.toolbar_divider())
        layout.addWidget(self.toolbar_block("Rate", self.rate_label), 0)
        layout.addWidget(self.toolbar_divider())
        layout.addWidget(self.toolbar_format_block(), 0)
        layout.addWidget(self.start_button, 0)
        layout.addWidget(self.stop_button, 0)

        toolbar.setLayout(layout)
        return toolbar

    def toolbar_divider(self):
        divider = QFrame()
        divider.setObjectName("toolbarDivider")
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedSize(5, 34)
        return divider

    def create_play_icon(self, color):
        pixmap = QPixmap(22, 22)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygon([QPoint(7, 4), QPoint(17, 11), QPoint(7, 18)]))
        painter.end()
        return QIcon(pixmap)

    def create_stop_icon(self, color):
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(5, 5, 10, 10, 1, 1)
        painter.end()
        return QIcon(pixmap)

    def chevron_icon(self, expanded):
        pixmap = QPixmap(str(self.assets_dir / "chevron_down.svg"))
        if not expanded:
            pixmap = pixmap.transformed(
                QTransform().rotate(-90),
                Qt.SmoothTransformation,
            )
        return QIcon(pixmap)

    def create_bottom_bar(self):
        bar = QFrame()
        bar.setObjectName("bottomBar")
        bar.setFixedHeight(42)

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)
        layout.addWidget(self.bottom_acquisition_label)
        layout.addWidget(self.bottom_mode_label, 1)
        layout.addWidget(self.open_data_folder_button)
        layout.addWidget(self.view_full_log_button)
        bar.setLayout(layout)
        return bar

    def toolbar_inline_label(self, text):
        label = QLabel(text)
        label.setObjectName("caption")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setFixedWidth(42)
        return label

    def toolbar_status_block(self):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setMinimumWidth(500)
        block.setFixedHeight(50)

        layout = QGridLayout()
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(2)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(12)
        title_label = QLabel("Status")
        title_label.setObjectName("caption")
        title_label.setAlignment(Qt.AlignVCenter)
        status_row.addWidget(title_label)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        layout.addLayout(status_row, 0, 0, 2, 2)
        divider = QFrame()
        divider.setObjectName("toolbarDivider")
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedSize(1, 34)
        layout.addWidget(divider, 0, 2, 2, 1)
        file_title = QLabel("File")
        file_title.setObjectName("caption")
        layout.addWidget(file_title, 0, 3)
        layout.addWidget(self.file_label, 1, 3)
        layout.setColumnStretch(3, 1)

        block.setLayout(layout)
        return block

    def toolbar_block(self, title, value_label, detail_label=None):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setMinimumWidth(110)
        block.setMaximumWidth(130)
        block.setFixedHeight(50)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(1)

        title_label = QLabel(title)
        title_label.setObjectName("caption")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        if detail_label is not None:
            layout.addWidget(detail_label)

        block.setLayout(layout)
        return block

    def toolbar_format_block(self):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setFixedHeight(50)
        block.setFixedWidth(172)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        label = QLabel("Save as")
        label.setObjectName("caption")
        layout.addWidget(label)
        layout.addWidget(self.format_selector)

        block.setLayout(layout)
        return block

    def create_left_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(285)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        readings_layout = QVBoxLayout()
        readings_layout.setContentsMargins(0, 0, 0, 0)
        readings_layout.setSpacing(0)
        readings_layout.addWidget(self.reading_row("Resistance", self.resistance_value_label, "#2563eb"))
        readings_layout.addWidget(self.reading_row("Temperature", self.temperature_value_label, "#f97316"))
        readings_layout.addWidget(self.reading_row("Analyte flow", self.nh3_actual_label, "#7c3aed"))
        readings_layout.addWidget(self.reading_row("Air flow", self.air_actual_label, "#0f9f9a"))
        readings_card = self.compact_section_card(
            "Current Readings",
            readings_layout,
        )

        state_layout = QVBoxLayout()
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(0)
        state_layout.addWidget(self.state_row("Humidity", self.humidity_value_label))
        state_layout.addWidget(self.state_row("Heating", self.heating_value_label))
        state_card = self.compact_section_card(
            "Current State",
            state_layout,
        )

        layout.addWidget(readings_card)
        layout.addWidget(state_card)
        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def create_center_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(0)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        resistance_layout = QVBoxLayout()
        resistance_layout.setContentsMargins(0, 0, 0, 0)
        resistance_layout.addWidget(self.resistance_plot)
        resistance_card = self.graph_card(
            "Resistance vs Time",
            "#3b82f6",
            resistance_layout,
        )

        temperature_layout = QVBoxLayout()
        temperature_layout.setContentsMargins(0, 0, 0, 0)
        temperature_layout.addWidget(self.temperature_plot)
        temperature_card = self.graph_card(
            "Temperature vs Time",
            "#f97316",
            temperature_layout,
        )

        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(0, 0, 0, 10)
        log_layout.addWidget(self.log_table)
        log_card = self.log_card(
            "Log Preview",
            log_layout,
        )
        self.log_card_widget = log_card
        log_card.setMinimumHeight(235)
        self.update_log_preview_height()

        layout.addWidget(resistance_card, 2)
        layout.addWidget(temperature_card, 2)
        layout.addWidget(log_card, 2)
        panel.setLayout(layout)
        return panel

    def create_right_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(340)
        panel.setMaximumWidth(370)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        manual_layout = QVBoxLayout()
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(6)
        manual_layout.addWidget(self.manual_mode_frame)
        manual_layout.addWidget(self.gas_channel_row(
            "Analyte",
            "#7c3aed",
            self.nh3_control,
            self.nh3_duration,
            self.apply_nh3_button,
        ))
        manual_layout.addWidget(self.gas_channel_row(
            "Air",
            "#0f9f9a",
            self.air_control,
            self.air_duration,
            self.apply_air_button,
        ))
        manual_layout.addWidget(self.air_purge_button)
        manual_card = self.compact_section_card(
            "Gas Controls",
            manual_layout,
        )

        environment_layout = QVBoxLayout()
        environment_layout.setContentsMargins(0, 0, 0, 0)
        environment_layout.setSpacing(6)
        environment_layout.addWidget(self.environment_control_row(
            "Humidity",
            self.humidity_status_label,
            self.humidity_off_button,
            self.humidity_on_button,
            self.humidity_duration,
        ))
        environment_layout.addWidget(self.environment_control_row(
            "Heating",
            self.heating_status_label,
            self.heating_off_button,
            self.heating_on_button,
            self.heating_duration,
        ))
        environment_card = self.compact_section_card(
            "Environment",
            environment_layout,
        )

        devices_layout = QVBoxLayout()
        devices_layout.setContentsMargins(0, 0, 0, 0)
        devices_layout.setSpacing(6)
        devices_layout.addWidget(self.create_multimeter_control())
        devices_layout.addWidget(self.create_mfc_control())
        self.device_status_chevron = QPushButton()
        self.device_status_chevron.setObjectName("sectionChevron")
        self.device_status_chevron.setFixedSize(24, 22)
        self.device_status_chevron.setIcon(self.chevron_icon(expanded=False))
        self.device_status_chevron.setIconSize(QSize(12, 12))
        self.device_status_chevron.setCheckable(True)
        self.device_status_chevron.setChecked(False)
        self.device_status_chevron.clicked.connect(self.toggle_device_setup)
        devices_card = self.section_card(
            "Device Status",
            None,
            devices_layout,
            header_widget=self.device_status_chevron,
        )

        layout.addWidget(manual_card)
        layout.addWidget(environment_card)
        layout.addWidget(devices_card)
        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def gas_channel_row(self, title, color, flow_widget, duration_widget, action_button):
        row = QFrame()
        row.setObjectName("gasChannelRow")

        layout = QGridLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)

        dot = QLabel()
        dot.setObjectName("compactDot")
        dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
        dot.setFixedSize(6, 6)

        title_label = QLabel(title)
        title_label.setObjectName("sectionLabel")

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(7)
        title_layout.addWidget(dot)
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        flow_label = QLabel("Flow")
        flow_label.setObjectName("metricName")
        duration_label = QLabel("Duration")
        duration_label.setObjectName("metricName")

        action_button.setFixedWidth(78)

        layout.addLayout(title_layout, 0, 0, 1, 2)
        layout.addWidget(flow_label, 1, 0)
        layout.addWidget(flow_widget, 1, 1)
        layout.addWidget(duration_label, 2, 0)
        layout.addWidget(duration_widget, 2, 1)
        layout.addWidget(action_button, 1, 2, 2, 1)
        layout.setColumnStretch(1, 1)

        row.setLayout(layout)
        return row

    def environment_control_row(self, title, status_label, off_button, on_button, duration_widget):
        row = QFrame()
        row.setObjectName("environmentChannelRow")

        layout = QGridLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("sectionLabel")
        duration_label = QLabel("Duration")
        duration_label.setObjectName("metricName")

        toggle_layout = QHBoxLayout()
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(6)
        toggle_layout.addWidget(off_button)
        toggle_layout.addWidget(on_button)

        layout.addWidget(title_label, 0, 0)
        layout.addWidget(status_label, 0, 1, Qt.AlignRight)
        layout.addLayout(toggle_layout, 1, 0, 1, 2)
        layout.addWidget(duration_label, 2, 0)
        layout.addWidget(duration_widget, 2, 1)
        layout.setColumnStretch(1, 1)

        row.setLayout(layout)
        return row

    def control_card(self, title, first_label, first_widget, second_label, second_widget, action_button, extra_button=None):
        card = QFrame()
        card.setObjectName("controlCard")

        layout = QGridLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setHorizontalSpacing(7)
        layout.setVerticalSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("sectionLabel")
        layout.addWidget(title_label, 0, 0, 1, 2)
        layout.addWidget(QLabel(first_label), 1, 0)
        layout.addWidget(first_widget, 1, 1)
        layout.addWidget(QLabel(second_label), 2, 0)
        layout.addWidget(second_widget, 2, 1)
        layout.addWidget(action_button, 3, 0, 1, 2)
        if extra_button is not None:
            layout.addWidget(extra_button, 4, 0, 1, 2)
        layout.setColumnStretch(1, 1)

        card.setLayout(layout)
        return card

    def scroll_panel(self, widget):
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

    def section_card(self, title, icon, content_layout, expanding=False, header_widget=None):
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

    def compact_section_card(self, title, content_layout):
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

    def graph_card(self, title, color, content_layout):
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

    def log_card(self, title, content_layout):
        card = QFrame()
        card.setObjectName("logCard")
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 11, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        icon_label = QLabel()
        icon_label.setObjectName("logIcon")
        icon_label.setPixmap(QIcon(str(self.assets_dir / "list.png")).pixmap(16, 16))

        title_label = QLabel(title)
        title_label.setObjectName("graphTitle")

        header.addWidget(icon_label)
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(self.open_data_folder_button)
        header.addWidget(self.view_full_log_button)

        rows_layout = QHBoxLayout()
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(3)
        rows_label = QLabel("Rows:")
        rows_label.setObjectName("mutedLabel")
        rows_layout.addWidget(rows_label)
        rows_layout.addWidget(self.log_rows_selector)
        header.addLayout(rows_layout)

        layout.addLayout(header)
        layout.addLayout(content_layout, 1)
        card.setLayout(layout)
        return card

    def metric_value(self, text):
        label = QLabel(text)
        label.setObjectName("metricValue")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return label

    def reading_row(self, name, value_label, color):
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

    def state_row(self, name, value_label):
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

    def metric_row(self, name, value_label):
        row = QFrame()
        row.setObjectName("metricRow")
        row.setMinimumHeight(32)
        row.setMaximumHeight(36)
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        name_label = QLabel(name)
        name_label.setObjectName("metricName")
        layout.addWidget(name_label)
        layout.addStretch()
        layout.addWidget(value_label)

        row.setLayout(layout)
        return row

    def reading_card(self, name, value_label):
        card = QFrame()
        card.setObjectName("readingCard")
        card.setMinimumHeight(72)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        name_label = QLabel(name)
        name_label.setObjectName("metricName")
        icon_label = QLabel()
        icon_label.setObjectName("readingIcon")
        icon_label.setPixmap(self.reading_icon(name).pixmap(18, 18))
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(icon_label)

        value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addLayout(header_layout)
        layout.addWidget(value_label)
        layout.addStretch()

        card.setLayout(layout)
        return card

    def reading_icon(self, name):
        if name == "Resistance":
            return QIcon(str(self.assets_dir / "resistance.png"))
        if name == "Temperature":
            return QIcon(str(self.assets_dir / "weather.png"))
        if "Analyte" in name:
            return QIcon(str(self.assets_dir / "curve.png"))
        if name == "Air actual":
            return QIcon(str(self.assets_dir / "air.png"))
        return self.style().standardIcon(QStyle.SP_FileIcon)

    def toggle_device_setup(self, _checked=False):
        setup_bodies = getattr(self, "device_setup_bodies", [])
        visible = not setup_bodies[0].isVisible() if setup_bodies else False
        for body in setup_bodies:
            body.setVisible(visible)
        if hasattr(self, "device_status_chevron"):
            self.device_status_chevron.setIcon(self.chevron_icon(expanded=visible))
            self.device_status_chevron.setChecked(visible)
        if visible:
            self.mfc_mode_selector.setFocus(Qt.OtherFocusReason)

    def create_multimeter_control(self):
        row = QFrame()
        row.setObjectName("deviceRow")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(6)

        layout.addLayout(self.device_card_header(
            "Multimeter",
            self.multimeter_summary_label,
            "multimeter_status_dot",
        ))
        body = self.device_setup_body()
        body.layout().addLayout(self.device_setting_row(
            "Mode",
            self.multimeter_mode_selector,
            self.connect_multimeter_button,
        ))
        body.layout().addLayout(self.device_setting_row(
            "Device",
            self.visa_device_selector,
            self.scan_visa_button,
        ))
        body.layout().addWidget(self.multimeter_resource_input)
        body.layout().addWidget(self.multimeter_status_label)
        body.setVisible(False)
        self.device_setup_bodies = getattr(self, "device_setup_bodies", [])
        self.device_setup_bodies.append(body)
        layout.addWidget(body)

        row.setLayout(layout)
        return row

    def create_mfc_control(self):
        row = QFrame()
        row.setObjectName("deviceRow")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(6)

        layout.addLayout(self.device_card_header(
            "MFC Controller",
            self.mfc_summary_label,
            "mfc_status_dot",
        ))
        body = self.device_setup_body()
        body.layout().addLayout(self.device_setting_row(
            "Mode",
            self.mfc_mode_selector,
            self.connect_mfc_button,
        ))
        body.layout().addLayout(self.device_setting_row(
            "Port",
            self.mfc_port_selector,
            self.scan_mfc_button,
        ))
        body.layout().addWidget(self.mfc_status_label)
        body.layout().addWidget(self.mfc_note_label)
        body.setVisible(False)
        self.device_setup_bodies = getattr(self, "device_setup_bodies", [])
        self.device_setup_bodies.append(body)
        layout.addWidget(body)

        row.setLayout(layout)
        return row

    def device_card_header(self, title, status_label, dot_attribute):
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("sectionLabel")
        status_dot = QLabel()
        status_dot.setObjectName("deviceStatusDot")
        status_dot.setProperty("state", "connected")
        status_dot.setFixedSize(8, 8)
        setattr(self, dot_attribute, status_dot)
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(status_dot)
        header.addWidget(status_label)
        return header

    def device_setup_body(self):
        body = QFrame()
        body.setObjectName("deviceSetupPanel")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(5)
        body.setLayout(layout)
        return body

    def device_setting_row(self, label_text, selector, button):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("metricName")
        label.setFixedWidth(42)
        row.addWidget(label)
        row.addWidget(selector, 1)
        row.addWidget(button, 0)
        return row

    def create_plot(self, title, left_label, units, color):
        plot = pg.PlotWidget()
        plot.setBackground("w")
        plot.setLabel("left", f"{left_label} ({units})", **{"color": "#334155", "font-size": "11px"})
        plot.setLabel("bottom", "Time (s)", **{"color": "#334155", "font-size": "11px"})
        plot.showGrid(x=True, y=True, alpha=0.18)
        plot.setMinimumSize(0, 120)
        plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot.getPlotItem().setContentsMargins(6, 2, 8, 4)
        plot.getPlotItem().layout.setContentsMargins(4, 2, 8, 4)
        plot.getAxis("left").setPen(pg.mkPen("#cbd5e1"))
        plot.getAxis("bottom").setPen(pg.mkPen("#cbd5e1"))
        plot.getAxis("left").setTextPen(pg.mkPen("#475569"))
        plot.getAxis("bottom").setTextPen(pg.mkPen("#475569"))
        plot.getAxis("left").setWidth(58)
        plot.getAxis("bottom").setHeight(42)
        plot.getAxis("left").setStyle(tickTextOffset=7)
        plot.getAxis("bottom").setStyle(tickTextOffset=7)
        plot.getPlotItem().getViewBox().setBorder(None)
        return plot

    def configure_log_table(self):
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setWordWrap(False)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_table.setMinimumHeight(160)

        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(58)
        for column, width in enumerate((70, 85, 125, 135, 110, 105, 95)):
            self.log_table.setColumnWidth(column, width)
        header.sectionResized.connect(self.on_log_section_resized)
        self.log_table.viewport().installEventFilter(self)
        QTimer.singleShot(0, self.apply_default_log_column_widths)
        self.log_table.verticalHeader().setDefaultSectionSize(26)

    def apply_default_log_column_widths(self):
        if self.adjusting_log_columns:
            return

        viewport_width = self.log_table.viewport().width()
        if viewport_width <= 0:
            return

        self.adjusting_log_columns = True
        try:
            minimum_width = self.log_table.horizontalHeader().minimumSectionSize()
            ratios = (0.10, 0.12, 0.17, 0.19, 0.15, 0.15, 0.12)
            used_width = 0
            last_column = self.log_table.columnCount() - 1

            for column, ratio in enumerate(ratios):
                if column == last_column:
                    width = max(minimum_width, viewport_width - used_width)
                else:
                    width = max(minimum_width, round(viewport_width * ratio))
                    used_width += width
                self.log_table.setColumnWidth(column, width)
        finally:
            self.adjusting_log_columns = False

    def eventFilter(self, source, event):
        if source is self.log_table.viewport() and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self.fit_log_columns_to_viewport)
        return super().eventFilter(source, event)

    def on_log_section_resized(self, logical_index, _old_size, _new_size):
        if self.adjusting_log_columns:
            return
        self.fit_log_columns_to_viewport(priority_column=logical_index)

    def fit_log_columns_to_viewport(self, priority_column=None):
        if self.adjusting_log_columns:
            return

        self.adjusting_log_columns = True
        try:
            header = self.log_table.horizontalHeader()
            minimum_width = header.minimumSectionSize()
            columns = range(self.log_table.columnCount())
            viewport_width = self.log_table.viewport().width()
            total_width = sum(self.log_table.columnWidth(column) for column in columns)

            if total_width > viewport_width:
                excess = total_width - viewport_width
                shrink_order = [
                    column for column in reversed(range(self.log_table.columnCount()))
                    if column != priority_column
                ]
                for column in shrink_order:
                    if excess <= 0:
                        break
                    width = self.log_table.columnWidth(column)
                    shrink_by = min(excess, max(0, width - minimum_width))
                    if shrink_by > 0:
                        self.log_table.setColumnWidth(column, width - shrink_by)
                        excess -= shrink_by

                if excess > 0 and priority_column is not None:
                    width = self.log_table.columnWidth(priority_column)
                    shrink_by = min(excess, max(0, width - minimum_width))
                    if shrink_by > 0:
                        self.log_table.setColumnWidth(priority_column, width - shrink_by)
            elif total_width < viewport_width and self.log_table.columnCount() > 0:
                last_column = self.log_table.columnCount() - 1
                self.log_table.setColumnWidth(
                    last_column,
                    self.log_table.columnWidth(last_column) + viewport_width - total_width,
                )
        finally:
            self.adjusting_log_columns = False

    def on_log_rows_changed(self, value):
        self.max_log_preview_rows = int(value)
        self.update_log_preview_height()
        while self.log_table.rowCount() > self.max_log_preview_rows:
            self.log_table.removeRow(0)
        self.log_table.scrollToBottom()

    def update_log_preview_height(self):
        if not hasattr(self, "log_card_widget"):
            return

        if self.max_log_preview_rows <= 5:
            self.log_card_widget.setMaximumHeight(245)
        else:
            self.log_card_widget.setMaximumHeight(16777215)

    def duration_ms(self, duration_input):
        return duration_input.value() * 1000

    def setup_environment_countdowns(self):
        self.environment_countdowns = {
            "humidity": {
                "timer": QTimer(self),
                "duration": self.humidity_duration,
                "on_button": self.humidity_on_button,
                "off_button": self.humidity_off_button,
                "remaining": 0,
                "original": 0,
            },
            "heating": {
                "timer": QTimer(self),
                "duration": self.heating_duration,
                "on_button": self.heating_on_button,
                "off_button": self.heating_off_button,
                "remaining": 0,
                "original": 0,
            },
        }

        for name, countdown in self.environment_countdowns.items():
            countdown["timer"].setInterval(1000)
            countdown["timer"].timeout.connect(
                lambda name=name: self.tick_environment_countdown(name)
            )

    def start_environment_countdown(self, name, seconds):
        if seconds <= 0:
            return

        countdown = self.environment_countdowns[name]
        timer = countdown["timer"]
        if timer.isActive():
            timer.stop()

        countdown["original"] = seconds
        countdown["remaining"] = seconds
        countdown["duration"].setValue(seconds)
        countdown["duration"].setEnabled(False)
        countdown["on_button"].setEnabled(False)
        countdown["off_button"].setEnabled(True)
        timer.start()

    def tick_environment_countdown(self, name):
        countdown = self.environment_countdowns[name]
        countdown["remaining"] = max(0, countdown["remaining"] - 1)
        countdown["duration"].setValue(countdown["remaining"])

        if countdown["remaining"] == 0:
            self.finish_environment_countdown(name, restore=True)

    def finish_environment_countdown(self, name, restore):
        countdown = self.environment_countdowns[name]
        countdown["timer"].stop()

        if restore:
            countdown["duration"].setValue(countdown["original"])

        countdown["remaining"] = 0
        self.apply_environment_countdown_locks()

    def cancel_environment_countdown(self, name, restore=True):
        countdown = self.environment_countdowns[name]
        if not countdown["timer"].isActive():
            return

        self.finish_environment_countdown(name, restore=restore)

    def cancel_all_environment_countdowns(self, restore=True):
        for name in self.environment_countdowns:
            self.cancel_environment_countdown(name, restore=restore)

    def apply_environment_countdown_locks(self):
        controls_enabled = not self.is_real_mfc_mode()
        for countdown in self.environment_countdowns.values():
            active = countdown["timer"].isActive()
            countdown["duration"].setEnabled(controls_enabled and not active)
            countdown["on_button"].setEnabled(controls_enabled and not active)
            countdown["off_button"].setEnabled(controls_enabled)

    def start_experiment(self):
        # UI preview data is deliberately cleared before each run. The manager
        # will create a new CSV/XLSX file for the new experiment.
        if not self.ensure_ready_to_start():
            return

        if self.completed_experiment_exists and not self.confirm_new_experiment():
            return

        self.time_data.clear()
        self.resistance_data.clear()
        self.temperature_data.clear()
        self.clear_event_markers()
        self.log_table.setRowCount(0)

        self.resistance_curve.setData([], [])
        self.temperature_curve.setData([], [])

        self.manager.start_experiment(
            self.format_selector.currentText(),
            self.data_directory,
        )

    def open_data_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.data_directory))

    def open_current_log(self):
        if self.is_experiment_running():
            self.file_label.setText("Stop the experiment before opening the full log")
            return

        if not self.current_file_path:
            self.file_label.setText("No experiment file to open yet")
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_file_path))

    def confirm_new_experiment(self):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Question)
        dialog.setWindowTitle("Start new experiment?")
        dialog.setText("Start a new experiment?")
        dialog.setInformativeText(
            "A new data file will be created. Current graph preview and log preview "
            "will be cleared. Active controls were returned to a safe state after Stop."
        )
        start_button = dialog.addButton("Start New Experiment", QMessageBox.AcceptRole)
        dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.setDefaultButton(start_button)
        dialog.exec()
        return dialog.clickedButton() == start_button

    def ensure_ready_to_start(self):
        # Choosing "Real ..." in the UI is not enough: the device must be
        # connected first so Start cannot silently fall back to simulation.
        if self.is_real_multimeter_mode():
            if self.manager.multimeter_mode != "real":
                self.on_device_error("Select Connect before starting with a real multimeter.")
                return False

        if self.is_real_mfc_mode():
            if self.manager.mfc_mode != "real":
                self.on_device_error("Select Connect before starting with a real MFC controller.")
                return False

        return True

    def is_real_multimeter_mode(self):
        return self.multimeter_mode_selector.currentText() == "Real multimeter"

    def is_real_mfc_mode(self):
        return self.mfc_mode_selector.currentText() == "Real MFC"

    def on_experiment_started(self, filename):
        self.completed_experiment_exists = False
        self.current_file_path = filename
        self.format_selector.setEnabled(False)
        self.view_full_log_button.setEnabled(False)
        self.update_device_setup_controls_enabled()
        self.status_label.setText("RUNNING")
        self.set_status_badge_state("running")
        self.file_label.setText(filename)
        self.bottom_acquisition_label.setText("Acquisition running")

    def on_experiment_stopped(self, message):
        self.completed_experiment_exists = True
        self.format_selector.setEnabled(True)
        self.view_full_log_button.setEnabled(bool(self.current_file_path))
        self.update_device_setup_controls_enabled()
        self.status_label.setText("STOPPED")
        self.set_status_badge_state("stopped")
        self.cancel_all_environment_countdowns(restore=False)
        self.reset_duration_controls()
        self.file_label.setText(message)
        self.bottom_acquisition_label.setText("Acquisition stopped")

    def on_device_error(self, message):
        self.status_label.setText("ERROR")
        self.set_status_badge_state("error")
        self.file_label.setText(message)
        self.bottom_acquisition_label.setText("Acquisition error")

    def set_status_badge_state(self, state):
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def reset_duration_controls(self):
        for duration_control in (
            self.nh3_duration,
            self.air_duration,
            self.humidity_duration,
            self.heating_duration,
        ):
            duration_control.setValue(0)

    def is_experiment_running(self):
        return self.manager.acquisition_timer.isActive()

    def update_device_setup_controls_enabled(self):
        setup_enabled = not self.is_experiment_running()
        multimeter_real = self.is_real_multimeter_mode()
        mfc_real = self.is_real_mfc_mode()

        self.multimeter_mode_selector.setEnabled(setup_enabled)
        self.connect_multimeter_button.setEnabled(setup_enabled)
        self.visa_device_selector.setEnabled(setup_enabled and multimeter_real)
        self.multimeter_resource_input.setEnabled(setup_enabled and multimeter_real)
        self.scan_visa_button.setEnabled(setup_enabled and multimeter_real)

        self.mfc_mode_selector.setEnabled(setup_enabled)
        self.connect_mfc_button.setEnabled(setup_enabled)
        self.mfc_port_selector.setEnabled(setup_enabled and mfc_real)
        self.scan_mfc_button.setEnabled(setup_enabled and mfc_real)

    def on_multimeter_mode_changed(self, text):
        is_real = text == "Real multimeter"
        self.connect_multimeter_button.setText("Connect" if is_real else "Use")
        if is_real:
            self.multimeter_status_label.setText("Not connected")
            self.set_device_summary(
                self.multimeter_summary_label,
                self.multimeter_status_dot,
                "Not Connected",
                "disconnected",
            )
        else:
            self.multimeter_status_label.setText("Connected: Simulated")
            self.set_device_summary(
                self.multimeter_summary_label,
                self.multimeter_status_dot,
                "Simulated",
                "connected",
            )
            if self.manager.multimeter_mode != "simulation":
                self.manager.set_multimeter_mode("simulation", "")
        self.update_device_setup_controls_enabled()

    def scan_visa_devices(self):
        if self.is_experiment_running():
            return

        self.visa_device_selector.clear()
        self.visa_device_selector.addItem("Scanning...", "")
        self.visa_device_selector.setEnabled(False)
        self.scan_visa_button.setEnabled(False)

        try:
            instruments = discover_visa_instruments()
        except Exception as exc:
            self.visa_device_selector.clear()
            self.visa_device_selector.addItem("Scan failed", "")
            self.on_device_error(f"VISA scan failed: {exc}")
            return
        finally:
            self.update_device_setup_controls_enabled()

        self.visa_device_selector.clear()
        if not instruments:
            self.visa_device_selector.addItem("No VISA instruments found", "")
            self.file_label.setText("No VISA instruments found")
            return

        for instrument in instruments:
            self.visa_device_selector.addItem(
                self.compact_instrument_label(instrument.idn, instrument.resource),
                instrument.resource,
            )
            index = self.visa_device_selector.count() - 1
            self.visa_device_selector.setItemData(index, instrument.label, Qt.ToolTipRole)

        self.file_label.setText(f"Found {len(instruments)} VISA instrument(s)")

    def on_visa_device_selected(self):
        resource = self.visa_device_selector.currentData()
        if resource:
            self.multimeter_resource_input.setText(resource)
            self.multimeter_resource_input.setToolTip(resource)

    @staticmethod
    def compact_instrument_label(idn, resource):
        parts = [part.strip() for part in idn.split(",")]
        if len(parts) >= 3:
            return f"Multimeter S/N {parts[2]}"

        if idn and not idn.startswith("No *IDN?"):
            return idn[:38]

        return resource[:38]

    def connect_multimeter(self):
        if self.is_experiment_running():
            return

        if self.is_real_multimeter_mode():
            resource = self.multimeter_resource_input.text().strip()
            if not resource:
                self.on_device_error("Enter multimeter VISA resource before connecting.")
                return

            ok = self.manager.set_multimeter_mode("real", resource)
        else:
            ok = self.manager.set_multimeter_mode("simulation", "")

        if ok:
            self.status_label.setText("IDLE")
            self.set_status_badge_state("idle")
            self.file_label.setText("Multimeter ready")
        elif self.is_real_multimeter_mode():
            self.set_device_summary(
                self.multimeter_summary_label,
                self.multimeter_status_dot,
                "Not Connected",
                "disconnected",
            )

    def on_multimeter_changed(self, mode, status):
        if mode == "real":
            self.multimeter_status_label.setText("Connected: real multimeter")
            self.set_device_summary(
                self.multimeter_summary_label,
                self.multimeter_status_dot,
                "Connected",
                "connected",
            )
            self.multimeter_status_label.setToolTip(status)
        else:
            self.multimeter_status_label.setText("Connected: Simulated")
            self.set_device_summary(
                self.multimeter_summary_label,
                self.multimeter_status_dot,
                "Simulated",
                "connected",
            )
            self.multimeter_status_label.setToolTip(status)

    def on_mfc_mode_changed(self, text):
        is_real = text == "Real MFC"
        self.connect_mfc_button.setText("Connect" if is_real else "Use")
        self.set_mfc_write_controls_enabled(not is_real)

        if is_real:
            self.mfc_status_label.setText("Not connected")
            self.set_device_summary(
                self.mfc_summary_label,
                self.mfc_status_dot,
                "Not Connected",
                "disconnected",
            )
            self.mfc_note_label.setText(
                "Flow writes disabled."
            )
            self.manual_mode_label.setText(
                "Real MFC mode (read-only). Flow control is disabled"
            )
            self.bottom_mode_label.setText(
                "Read-only mode: MFC readings are allowed, flow control is disabled."
            )
        else:
            self.mfc_status_label.setText("Connected: Simulated")
            self.mfc_status_label.setToolTip(self.manager.mfc_status_text())
            self.set_device_summary(
                self.mfc_summary_label,
                self.mfc_status_dot,
                "Simulated",
                "connected",
            )
            if self.manager.mfc_mode != "simulation":
                self.manager.set_mfc_mode("simulation")
            self.mfc_note_label.setText(
                "Simulated MFC: gas controls affect only the software model."
            )
            self.manual_mode_label.setText(
                "Simulated MFC mode. Software model only."
            )
            self.bottom_mode_label.setText("Simulation mode ready")
        self.update_device_setup_controls_enabled()

    def scan_mfc_ports(self):
        if self.is_experiment_running():
            return

        self.mfc_port_selector.clear()

        if list_ports is None:
            self.mfc_port_selector.addItem("pyserial unavailable", "")
            self.on_device_error("COM port scan failed: pyserial is not available.")
            return

        ports = list(list_ports.comports())
        if not ports:
            self.mfc_port_selector.addItem("No COM ports found", "")
            self.file_label.setText("No COM ports found")
            return

        for port in ports:
            label = f"{port.device} - {port.description}"
            self.mfc_port_selector.addItem(label[:48], port.device)
            index = self.mfc_port_selector.count() - 1
            self.mfc_port_selector.setItemData(index, label, Qt.ToolTipRole)

        self.file_label.setText(f"Found {len(ports)} COM port(s)")

    def connect_mfc(self):
        if self.is_experiment_running():
            return

        if self.is_real_mfc_mode():
            port = self.mfc_port_selector.currentData() or self.mfc_port_selector.currentText()
            port = port.strip()
            if not port:
                self.on_device_error("Select MFC COM port before connecting.")
                return

            ok = self.manager.set_mfc_mode("real", port=port)
        else:
            ok = self.manager.set_mfc_mode("simulation")

        if ok:
            self.status_label.setText("IDLE")
            self.set_status_badge_state("idle")
            self.file_label.setText("MFC ready")
        elif self.is_real_mfc_mode():
            self.set_device_summary(
                self.mfc_summary_label,
                self.mfc_status_dot,
                "Not Connected",
                "disconnected",
            )

    def on_mfc_changed(self, mode, status):
        if mode == "real":
            self.mfc_status_label.setText(self.compact_mfc_status(status))
            self.set_device_summary(
                self.mfc_summary_label,
                self.mfc_status_dot,
                "Connected",
                "connected",
            )
            self.mfc_status_label.setToolTip(status)
            self.set_mfc_write_controls_enabled(False)
        else:
            if self.is_real_mfc_mode():
                self.mfc_status_label.setText("Not connected")
                self.set_device_summary(
                    self.mfc_summary_label,
                    self.mfc_status_dot,
                    "Not Connected",
                    "disconnected",
                )
                self.set_mfc_write_controls_enabled(False)
            else:
                self.mfc_status_label.setText("Connected: Simulated")
                self.set_device_summary(
                    self.mfc_summary_label,
                    self.mfc_status_dot,
                    "Simulated",
                    "connected",
                )
                self.set_mfc_write_controls_enabled(True)
            self.mfc_status_label.setToolTip(status)

    @staticmethod
    def set_device_summary(label, dot, text, state):
        label.setText(text)
        label.setProperty("state", state)
        dot.setProperty("state", state)
        for widget in (label, dot):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    @staticmethod
    def compact_mfc_status(status):
        parts = [part.strip() for part in status.split("|")]
        port = ""
        address = ""
        serial = ""
        fluid = ""
        capacity = ""

        for part in parts:
            if part.upper().startswith("COM"):
                port = part
            elif part.startswith("addr "):
                address = part.replace("addr ", "addr ")
            elif part.startswith("S/N "):
                serial = part.replace("S/N ", "")
            elif part.startswith("fluid "):
                fluid = part.replace("fluid ", "")
            elif part.startswith("capacity "):
                capacity = part.replace("capacity ", "")

        first_line = "Real read-only"
        if port or address:
            first_line = f"{first_line}: {port} {address}".strip()

        second_line_parts = []
        if serial:
            second_line_parts.append(f"S/N {serial}")
        if fluid:
            second_line_parts.append(fluid)
        if capacity:
            second_line_parts.append(capacity)

        if second_line_parts:
            return f"{first_line}\n{' | '.join(second_line_parts)}"

        return first_line

    def set_mfc_write_controls_enabled(self, enabled):
        widgets = [
            self.nh3_control,
            self.air_control,
            self.nh3_duration,
            self.air_duration,
            self.apply_nh3_button,
            self.apply_air_button,
            self.air_purge_button,
            self.humidity_duration,
            self.heating_duration,
            self.humidity_on_button,
            self.humidity_off_button,
            self.heating_on_button,
            self.heating_off_button,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)
        self.apply_environment_countdown_locks()

    def apply_nh3(self):
        self.manager.apply_nh3(
            self.nh3_control.value(),
            self.duration_ms(self.nh3_duration),
        )

    def apply_air(self):
        self.manager.apply_air(self.air_control.value())

    def set_humidity(self, enabled):
        duration_seconds = self.humidity_duration.value()
        command_applied = self.manager.set_humidity(
            enabled,
            duration_seconds * 1000,
        )
        if not command_applied:
            return

        if enabled:
            self.start_environment_countdown("humidity", duration_seconds)
        else:
            self.cancel_environment_countdown("humidity", restore=True)

    def set_heating(self, enabled):
        duration_seconds = self.heating_duration.value()
        command_applied = self.manager.set_heating(
            enabled,
            duration_seconds * 1000,
        )
        if not command_applied:
            return

        if enabled:
            self.start_environment_countdown("heating", duration_seconds)
        else:
            self.cancel_environment_countdown("heating", restore=True)

    def refresh_state_label(self, state):
        humidity = "ON" if state.humidity_on else "OFF"
        heating = "ON" if state.heating_on else "OFF"

        self.nh3_value_label.setText(f"{state.nh3_actual_sccm:g} sccm")
        self.air_value_label.setText(f"{state.air_actual_sccm:g} sccm")
        self.humidity_value_label.setText(humidity)
        self.heating_value_label.setText(heating)
        self.humidity_status_label.setText(humidity)
        self.heating_status_label.setText(heating)
        self.set_toggle_active(self.humidity_on_button, state.humidity_on)
        self.set_toggle_active(self.humidity_off_button, not state.humidity_on)
        self.set_toggle_active(self.heating_on_button, state.heating_on)
        self.set_toggle_active(self.heating_off_button, not state.heating_on)
        self.set_label_active(self.humidity_status_label, state.humidity_on)
        self.set_label_active(self.heating_status_label, state.heating_on)
        if not state.humidity_on:
            self.cancel_environment_countdown("humidity", restore=True)
        if not state.heating_on:
            self.cancel_environment_countdown("heating", restore=True)

        self.nh3_control.setValue(state.nh3_setpoint_sccm)
        self.air_control.setValue(state.air_setpoint_sccm)

    @staticmethod
    def set_toggle_active(button, active):
        button.setProperty("active", "true" if active else "false")
        button.style().unpolish(button)
        button.style().polish(button)

    @staticmethod
    def set_label_active(label, active):
        label.setProperty("active", "true" if active else "false")
        label.style().unpolish(label)
        label.style().polish(label)

    def on_data_acquired(self, data, event):
        self.time_data.append(data["elapsed_s"])
        self.resistance_data.append(data["resistance_ohm"])
        self.temperature_data.append(data["temperature_c"])

        self.resistance_curve.setData(self.time_data, self.resistance_data)
        self.temperature_curve.setData(self.time_data, self.temperature_data)
        if event:
            self.add_event_marker(data["elapsed_s"], event)
        self.update_plot_ranges()

        self.resistance_value_label.setText(
            self.format_number(data["resistance_ohm"], suffix=" Ohm", precision=2)
        )
        self.temperature_value_label.setText(
            self.format_number(data["temperature_c"], suffix=" °C", precision=2)
        )
        self.nh3_actual_label.setText(f"{data['nh3_actual_sccm']:.2f} sccm")
        self.air_actual_label.setText(f"{data['air_actual_sccm']:.2f} sccm")

        self.add_log_preview_row(data, event)

    def update_plot_ranges(self):
        resistance_values = self.finite_values(self.resistance_data)
        temperature_values = self.finite_values(self.temperature_data)

        if self.time_data:
            self.resistance_plot.setXRange(self.time_data[0], self.time_data[-1], padding=0.02)
            self.temperature_plot.setXRange(self.time_data[0], self.time_data[-1], padding=0.02)

        if resistance_values:
            low = min(resistance_values)
            high = max(resistance_values)
            padding = max((high - low) * 0.12, 50)
            self.resistance_plot.setYRange(low - padding, high + padding, padding=0)

        if temperature_values:
            low = min(temperature_values)
            high = max(temperature_values)
            padding = max((high - low) * 0.25, 1)
            self.temperature_plot.setYRange(low - padding, high + padding, padding=0)

        self.update_event_marker_labels()

    def add_event_marker(self, elapsed_s, event):
        color = self.event_color(event)
        pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)

        resistance_line = pg.InfiniteLine(pos=elapsed_s, angle=90, movable=False, pen=pen)
        temperature_line = pg.InfiniteLine(pos=elapsed_s, angle=90, movable=False, pen=pen)
        self.resistance_plot.addItem(resistance_line)
        self.temperature_plot.addItem(temperature_line)

        label = pg.TextItem(
            text=self.short_event_label(event),
            color=color,
            anchor=(0.5, 0.0),
            border=pg.mkPen(color),
            fill=pg.mkBrush(255, 255, 255, 225),
        )
        label.setFont(QFont("Segoe UI", 8))
        label.setZValue(20)
        label_plot = self.event_label_plot(event)
        label_plot.addItem(label)
        self.event_markers.append({
            "x": elapsed_s,
            "level": len(self.event_markers) % 3,
            "label": label,
            "label_plot": label_plot,
            "resistance_line": resistance_line,
            "temperature_line": temperature_line,
        })
        self.update_event_marker_labels()

    def update_event_marker_labels(self):
        if not self.event_markers:
            return

        for marker in self.event_markers:
            _x_range, y_range = marker["label_plot"].getViewBox().viewRange()
            y_top = y_range[1]
            y_span = y_range[1] - y_range[0]
            y_offset = y_span * (0.08 + marker["level"] * 0.11)
            marker["label"].setPos(marker["x"], y_top - y_offset)

    def clear_event_markers(self):
        for marker in self.event_markers:
            self.resistance_plot.removeItem(marker["resistance_line"])
            self.temperature_plot.removeItem(marker["temperature_line"])
            marker["label_plot"].removeItem(marker["label"])
        self.event_markers.clear()

    def event_label_plot(self, event):
        if "heating" in event.lower():
            return self.temperature_plot
        return self.resistance_plot

    @staticmethod
    def event_color(event):
        event_lower = event.lower()
        if "heating" in event_lower:
            return "#ef4444"
        if "humidity" in event_lower:
            return "#14b8a6"
        if "air" in event_lower:
            return "#22c55e"
        if "analyte" in event_lower:
            return "#8b5cf6"
        return "#64748b"

    @staticmethod
    def short_event_label(event):
        labels = []
        for part in event.split("; "):
            text = part.strip()
            lower = text.lower()
            if lower.startswith("set analyte flow"):
                value = text.split("=", 1)[-1].strip()
                labels.append(f"Analyte {value}")
            elif lower.startswith("set air flow"):
                value = text.split("=", 1)[-1].strip()
                labels.append(f"Air {value}")
            elif lower == "air purge":
                labels.append("Air Purge")
            elif lower.startswith("humidity"):
                labels.append(text)
            elif lower.startswith("heating"):
                labels.append(text)
            elif lower.endswith("duration ended"):
                labels.append(text.replace(" duration ended", " ended"))
            else:
                labels.append(text)
        return "\n".join(labels)

    @staticmethod
    def finite_values(values):
        return [
            value
            for value in values
            if isinstance(value, (int, float)) and math.isfinite(value)
        ]

    @staticmethod
    def format_number(value, suffix="", precision=2):
        if isinstance(value, (int, float)) and math.isfinite(value):
            return f"{value:.{precision}f}{suffix}"

        return "OPEN" if suffix == " Ohm" else "--"

    def add_log_preview_row(self, data, event):
        # The preview is capped for UI performance. The logger still writes the
        # complete experiment history to disk.
        if self.log_table.rowCount() >= self.max_log_preview_rows:
            self.log_table.removeRow(0)

        row = self.log_table.rowCount()
        self.log_table.insertRow(row)

        values = [
            data["timestamp"],
            f"{data['elapsed_s']:.1f}",
            self.format_number(data["resistance_ohm"], precision=2),
            self.format_number(data["temperature_c"], precision=2),
            f"{data['nh3_flow_sccm']:.2f}",
            f"{data['air_flow_sccm']:.2f}",
            event,
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.log_table.setItem(row, col, item)

        self.log_table.scrollToBottom()

    def closeEvent(self, event):
        self.manager.close()
        event.accept()

    def apply_styles(self):
        chevron_down_path = (self.assets_dir / "chevron_down.svg").as_posix()
        self.setStyleSheet("""
            QWidget#appBackground {
                background: #f6f8fb;
            }
            QFrame#toolbar {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#toolbarDivider {
                background: #e5eaf0;
                border: none;
                min-width: 1px;
                max-width: 1px;
            }
            QFrame#bottomBar {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 7px;
            }
            QSplitter#bodySplitter::handle {
                background: #d7e0eb;
                width: 3px;
                margin: 0;
            }
            QSplitter#centerSplitter::handle {
                background: #d7e0eb;
                height: 3px;
                margin: 0;
            }
            QSplitter#centerSplitter::handle:hover {
                background: #cbd5e1;
            }
            QScrollArea#panelScroll {
                background: transparent;
                border: none;
            }
            QScrollArea#panelScroll > QWidget > QWidget {
                background: transparent;
            }
            QFrame#toolbarBlock {
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QFrame#sectionCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#compactSectionCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#graphCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#logCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#logContentFrame {
                border: none;
                background: transparent;
                padding-bottom: 8px;
            }
            QLabel#graphTitle {
                color: #0f172a;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#graphDot {
                min-width: 10px;
                max-width: 10px;
                min-height: 10px;
                max-height: 10px;
            }
            QLabel#graphAction {
                color: #475569;
                font-size: 16px;
                font-weight: 700;
                min-width: 22px;
                max-width: 22px;
            }
            QLabel#logIcon {
                min-width: 16px;
                max-width: 16px;
            }
            QLabel#sectionTitle {
                color: #0f172a;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#sectionIcon {
                min-width: 16px;
                max-width: 16px;
            }
            QPushButton#sectionChevron {
                background: transparent;
                border: none;
                color: #475569;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                min-height: 20px;
            }
            QPushButton#sectionChevron:hover {
                background: #eef2f7;
                border-radius: 4px;
            }
            QFrame#metricRow,
            QFrame#deviceRow,
            QFrame#deviceStatusRow,
            QFrame#readingCard,
            QFrame#controlCard,
            QFrame#gasChannelRow,
            QFrame#environmentChannelRow {
                background: #fbfcfe;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
            QFrame#deviceSetupPanel {
                background: transparent;
                border: none;
            }
            QFrame#metricRow {
                min-height: 34px;
                max-height: 38px;
            }
            QFrame#compactReadingRow,
            QFrame#compactStateRow {
                background: transparent;
                border: none;
                border-bottom: 1px solid #edf2f7;
                min-height: 36px;
                max-height: 40px;
            }
            QLabel#compactDot {
                min-width: 6px;
                max-width: 6px;
                min-height: 6px;
                max-height: 6px;
            }
            QLabel {
                color: #233244;
                font-size: 12px;
            }
            QLabel#caption,
            QLabel#metricName,
            QLabel#mutedLabel {
                color: #64748b;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel#toolbarSectionLabel {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#sectionLabel,
            QLabel#statusLineLabel {
                color: #0f172a;
                font-size: 12px;
                font-weight: 700;
            }
            QFrame#warningFrame {
                background: #fffbeb;
                border: 1px solid #facc15;
                border-radius: 7px;
                min-height: 34px;
            }
            QLabel#warningLabel {
                color: #92400e;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#warningIcon {
                min-width: 16px;
                max-width: 16px;
                min-height: 16px;
                max-height: 16px;
            }
            QLabel#envStatus {
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#envStatus[active="true"] {
                color: #15803d;
            }
            QLabel#metricValue,
            QLabel#toolbarValue {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#metricValue[metricColor="blue"] {
                color: #2563eb;
                font-size: 20px;
            }
            QLabel#metricValue[metricColor="orange"] {
                color: #f97316;
                font-size: 20px;
            }
            QLabel#metricValue[metricColor="purple"] {
                color: #7c3aed;
                font-size: 20px;
            }
            QLabel#metricValue[metricColor="teal"] {
                color: #0f9f9a;
                font-size: 20px;
            }
            QLabel#metricValue[compactMetric="true"] {
                color: #0f172a;
                font-size: 14px;
                font-weight: 600;
            }
            QLabel#statusBadge {
                background: #dcfce7;
                color: #15803d;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 3px 8px;
                font-weight: 700;
            }
            QLabel#statusBadge[state="running"] {
                background: #dcfce7;
                color: #15803d;
                border-color: #86efac;
            }
            QLabel#statusBadge[state="error"] {
                background: #fee2e2;
                color: #dc2626;
                border-color: #fca5a5;
            }
            QLabel#statusBadge[state="stopped"] {
                background: #fee2e2;
                color: #dc2626;
                border-color: #fca5a5;
            }
            QLabel#connectedLabel {
                color: #16a34a;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#connectedLabel[state="disconnected"] {
                color: #dc2626;
            }
            QLabel#deviceStatusDot {
                background: #16a34a;
                border-radius: 4px;
                min-width: 8px;
                max-width: 8px;
                min-height: 8px;
                max-height: 8px;
            }
            QLabel#deviceStatusDot[state="disconnected"] {
                background: #dc2626;
            }
            QLabel#readingIcon {
                color: #64748b;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 7px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 3px;
                min-height: 36px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
                background: transparent;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QComboBox,
            QSpinBox,
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 2px 7px;
                background: #ffffff;
                color: #172033;
                min-height: 26px;
            }
            QComboBox:disabled,
            QSpinBox:disabled,
            QLineEdit:disabled {
                color: #94a3b8;
                background: #f1f5f9;
            }
            QComboBox {
                padding-right: 28px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
                border-left: 1px solid transparent;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox::drop-down:hover {
                background: #f1f5f9;
                border-left-color: #e2e8f0;
            }
            QComboBox::down-arrow {
                image: url("__CHEVRON_DOWN__");
                width: 12px;
                height: 12px;
            }
            QComboBox#logRowsSelector {
                border: none;
                background: transparent;
                padding: 0 18px 0 0;
                min-height: 22px;
                color: #334155;
                font-weight: 600;
            }
            QComboBox#logRowsSelector::drop-down {
                width: 18px;
                border: none;
            }
            QComboBox#logRowsSelector::drop-down:hover {
                background: transparent;
                border: none;
            }
            QComboBox#logRowsSelector::down-arrow {
                image: url("__CHEVRON_DOWN__");
                width: 10px;
                height: 10px;
            }
            QListView#logRowsPopup {
                background: #ffffff;
                color: #172033;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                outline: none;
                padding: 2px;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
            }
            QListView#logRowsPopup::item {
                min-height: 22px;
                padding: 3px 8px;
                background: #ffffff;
            }
            QListView#logRowsPopup::item:hover,
            QListView#logRowsPopup::item:selected {
                background: #dbeafe;
                color: #0f172a;
            }
            QPushButton {
                min-height: 24px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 10px;
                background: #ffffff;
                color: #172033;
            }
            QPushButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton#logActionButton {
                min-height: 24px;
                padding: 2px 9px;
                border-radius: 6px;
                color: #172033;
                background: #ffffff;
            }
            QPushButton#logActionButton:disabled {
                color: #94a3b8;
                background: #f1f5f9;
                border-color: #dbe3ee;
            }
            QPushButton#stepButton {
                min-height: 24px;
                border-radius: 5px;
                padding: 0;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#startButton,
            QPushButton#primaryButton {
                color: #15803d;
                border-color: #22c55e;
                background: #ecfdf3;
                font-weight: 700;
            }
            QPushButton#startButton:hover,
            QPushButton#primaryButton:hover {
                background: #dcfce7;
                border-color: #16a34a;
            }
            QPushButton#secondaryButton {
                color: #334155;
                border-color: #cbd5e1;
                background: #ffffff;
                font-weight: 600;
            }
            QPushButton#secondaryButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton#toggleButton {
                min-height: 28px;
                font-weight: 600;
            }
            QPushButton#toggleButton[active="true"] {
                color: #15803d;
                border-color: #22c55e;
                background: #ecfdf3;
                font-weight: 700;
            }
            QPushButton#stopButton {
                color: #dc2626;
                border-color: #ef4444;
                background: #fef2f2;
                font-weight: 700;
            }
            QPushButton#stopButton:hover {
                background: #fee2e2;
                border-color: #dc2626;
            }
            QPushButton:disabled {
                color: #9ca3af;
                background: #eef2f7;
                border-color: #e5e7eb;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                gridline-color: #e2e8f0;
                color: #102033;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background: #eef2f7;
                color: #334155;
                border: 0;
                border-right: 1px solid #dbe3ee;
                border-bottom: 1px solid #dbe3ee;
                padding: 4px;
                font-weight: 700;
                font-size: 11px;
            }
        """.replace("__CHEVRON_DOWN__", chevron_down_path))
