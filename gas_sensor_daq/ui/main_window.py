import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QFrame,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
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

        self.setWindowTitle("Gas Sensor DAQ & MFC Control Prototype")
        self.setMinimumSize(960, 600)

        self.manager = AcquisitionManager(self)
        self.time_data = []
        self.resistance_data = []
        self.temperature_data = []
        self.completed_experiment_exists = False
        self.max_log_preview_rows = 50
        self.data_directory = self.manager.data_directory

        self.setup_ui()
        self.connect_manager_signals()
        self.refresh_state_label(self.manager.current_state())

    def setup_ui(self):
        self.status_label = QLabel("IDLE")
        self.status_label.setObjectName("statusBadge")
        self.status_label.setProperty("state", "idle")
        self.status_label.setFixedSize(86, 20)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.file_label = QLabel("No file open")
        self.file_label.setObjectName("mutedLabel")
        self.elapsed_label = QLabel("00:00:00")
        self.elapsed_label.setObjectName("toolbarValue")
        self.rate_label = QLabel("0.5 Hz")
        self.rate_label.setObjectName("toolbarValue")

        self.format_selector = QComboBox()
        self.format_selector.addItems(["CSV", "Excel"])
        self.format_selector.setFixedWidth(128)
        self.format_selector.setFixedHeight(30)
        self.data_folder_label = QLabel(self.data_directory)
        self.data_folder_label.setObjectName("mutedLabel")
        self.data_folder_label.setToolTip(self.data_directory)
        self.data_folder_label.setFixedWidth(220)
        self.data_folder_button = QPushButton("Folder")
        self.data_folder_button.setToolTip("Select data folder")
        self.data_folder_button.setFixedWidth(96)
        self.data_folder_button.setFixedHeight(30)
        self.data_folder_button.clicked.connect(self.choose_data_folder)

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
        self.connect_multimeter_button = QPushButton("Connect")
        self.scan_visa_button.setFixedWidth(52)
        self.connect_multimeter_button.setFixedWidth(68)
        self.multimeter_status_label = QLabel(self.manager.multimeter_status_text())
        self.multimeter_status_label.setObjectName("connectedLabel")
        self.multimeter_status_label.setWordWrap(True)
        self.multimeter_status_label.setMaximumHeight(34)
        self.mfc_status_label = QLabel("Connected: simulated")
        self.mfc_status_label.setObjectName("connectedLabel")
        self.mfc_status_label.setWordWrap(True)
        self.mfc_status_label.setMaximumHeight(40)
        self.mfc_note_label = QLabel("Real MFC mode is read-only until gas testing is approved.")
        self.mfc_note_label.setObjectName("mutedLabel")
        self.mfc_note_label.setWordWrap(True)
        self.mfc_note_label.setMaximumHeight(28)
        self.mfc_mode_selector = QComboBox()
        self.mfc_mode_selector.addItems(["Simulated", "Real MFC"])
        self.mfc_port_selector = QComboBox()
        self.mfc_port_selector.addItem(self.manager.mfc_port, self.manager.mfc_port)
        self.scan_mfc_button = QPushButton("Scan")
        self.connect_mfc_button = QPushButton("Connect")
        self.scan_mfc_button.setFixedWidth(52)
        self.connect_mfc_button.setFixedWidth(68)

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.start_button.setFixedWidth(58)
        self.stop_button.setFixedWidth(58)
        self.start_button.setFixedHeight(34)
        self.stop_button.setFixedHeight(34)
        self.start_button.setObjectName("startButton")
        self.stop_button.setObjectName("stopButton")
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

        self.nh3_control = Stepper(0, 100, 0, " sccm")
        self.air_control = Stepper(0, 500, 100, " sccm")
        self.nh3_duration = Stepper(0, 24 * 60 * 60, 0, " s")
        self.air_duration = Stepper(0, 24 * 60 * 60, 0, " s")
        self.humidity_duration = Stepper(0, 24 * 60 * 60, 0, " s")
        self.heating_duration = Stepper(0, 24 * 60 * 60, 0, " s")

        self.apply_nh3_button = QPushButton("Apply NH3")
        self.apply_air_button = QPushButton("Apply Air")
        self.air_purge_button = QPushButton("Air Purge")
        self.humidity_on_button = QPushButton("Humidity ON")
        self.humidity_off_button = QPushButton("Humidity OFF")
        self.heating_on_button = QPushButton("Heating ON")
        self.heating_off_button = QPushButton("Heating OFF")

        self.apply_nh3_button.setObjectName("primaryButton")
        self.apply_air_button.setObjectName("primaryButton")

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
            "deg C",
            "#dc2626",
        )
        self.temperature_curve = self.temperature_plot.plot(
            pen=pg.mkPen(color="#dc2626", width=2)
        )

        self.log_table = QTableWidget(0, 7)
        self.log_table.setHorizontalHeaderLabels([
            "Time",
            "Elapsed",
            "Resistance",
            "Temp",
            "NH3",
            "Air",
            "Event",
        ])
        self.configure_log_table()

        root = QWidget()
        root.setObjectName("appBackground")
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(10, 8, 10, 10)
        root_layout.setSpacing(8)

        root_layout.addWidget(self.create_toolbar())

        # Side panels are scrollable and the center pane is resizable so the
        # app stays usable on lab laptops that are not running fullscreen.
        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setObjectName("bodySplitter")
        body_splitter.setChildrenCollapsible(False)
        body_splitter.setHandleWidth(3)
        body_splitter.addWidget(self.scroll_panel(self.create_left_panel()))
        body_splitter.addWidget(self.create_center_panel())
        body_splitter.addWidget(self.scroll_panel(self.create_right_panel()))
        body_splitter.setStretchFactor(0, 0)
        body_splitter.setStretchFactor(1, 1)
        body_splitter.setStretchFactor(2, 0)
        body_splitter.setSizes([320, 760, 320])

        root_layout.addWidget(body_splitter, 1)
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
        toolbar.setFixedHeight(62)

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        layout.addWidget(self.toolbar_status_block(), 0)
        layout.addSpacing(8)
        layout.addWidget(self.toolbar_inline_label("Save"))
        layout.addWidget(self.format_selector)
        layout.addSpacing(12)
        layout.addWidget(self.data_folder_button)
        layout.addSpacing(10)
        layout.addWidget(self.start_button, 0)
        layout.addWidget(self.stop_button, 0)
        layout.addStretch(1)
        layout.addWidget(self.toolbar_block("Elapsed", self.elapsed_label), 0)
        layout.addWidget(self.toolbar_block("Rate", self.rate_label), 0)

        toolbar.setLayout(layout)
        return toolbar

    def toolbar_inline_label(self, text):
        label = QLabel(text)
        label.setObjectName("caption")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setFixedWidth(42)
        return label

    def toolbar_status_block(self):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setMinimumWidth(360)
        block.setFixedHeight(50)

        layout = QGridLayout()
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(1)

        title_label = QLabel("Status")
        title_label.setObjectName("caption")
        layout.addWidget(title_label, 0, 0)
        layout.addWidget(self.status_label, 0, 1)
        layout.addWidget(self.file_label, 1, 0, 1, 2)
        layout.setColumnStretch(2, 1)

        block.setLayout(layout)
        return block

    def toolbar_block(self, title, value_label, detail_label=None):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setMinimumWidth(125)
        block.setMaximumWidth(140)
        block.setFixedHeight(50)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 4, 10, 4)
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
        block.setFixedWidth(170)
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        label = QLabel("Save")
        label.setObjectName("caption")
        layout.addWidget(label)
        layout.addWidget(self.format_selector)

        block.setLayout(layout)
        return block

    def toolbar_data_folder_block(self):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setFixedHeight(50)
        block.setFixedWidth(112)
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        layout.addWidget(self.data_folder_button)

        block.setLayout(layout)
        return block

    def create_left_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(305)
        panel.setMaximumWidth(380)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        state_group = self.group("Current State", "blueGroup")
        state_layout = QVBoxLayout()
        state_layout.setSpacing(6)
        state_layout.addWidget(self.metric_row("NH3 actual", self.nh3_value_label))
        state_layout.addWidget(self.metric_row("Air actual", self.air_value_label))
        state_layout.addWidget(self.metric_row("Humidity", self.humidity_value_label))
        state_layout.addWidget(self.metric_row("Heating", self.heating_value_label))
        state_group.setLayout(state_layout)

        devices_group = self.group("Devices", "greenGroup")
        devices_layout = QVBoxLayout()
        devices_layout.setSpacing(6)
        devices_layout.addWidget(self.create_multimeter_control())
        devices_layout.addWidget(self.create_mfc_control())
        devices_group.setLayout(devices_layout)

        readings_group = self.group("Live Readings", "purpleGroup")
        readings_layout = QVBoxLayout()
        readings_layout.setSpacing(6)
        readings_layout.addWidget(self.metric_row("Resistance", self.resistance_value_label))
        readings_layout.addWidget(self.metric_row("Temperature", self.temperature_value_label))
        readings_layout.addWidget(self.metric_row("NH3 actual", self.nh3_actual_label))
        readings_layout.addWidget(self.metric_row("Air actual", self.air_actual_label))
        readings_group.setLayout(readings_layout)

        layout.addWidget(state_group)
        layout.addWidget(readings_group)
        layout.addWidget(devices_group)
        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def create_center_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(0)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        resistance_group = self.group("Resistance vs Time", "blueGroup")
        resistance_layout = QVBoxLayout()
        resistance_layout.setContentsMargins(8, 10, 8, 8)
        resistance_layout.addWidget(self.resistance_plot)
        resistance_group.setLayout(resistance_layout)

        temperature_group = self.group("Temperature vs Time", "orangeGroup")
        temperature_layout = QVBoxLayout()
        temperature_layout.setContentsMargins(8, 10, 8, 8)
        temperature_layout.addWidget(self.temperature_plot)
        temperature_group.setLayout(temperature_layout)

        log_group = self.group("Log Preview", "greenGroup")
        log_group.setMinimumHeight(130)
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(8, 10, 8, 8)
        log_layout.addWidget(self.log_table)
        log_group.setLayout(log_layout)

        center_splitter = QSplitter(Qt.Vertical)
        # Operators can give more space to graphs or to the log preview during
        # long runs without changing the acquisition logic.
        center_splitter.setObjectName("centerSplitter")
        center_splitter.setChildrenCollapsible(False)
        center_splitter.setHandleWidth(5)
        center_splitter.addWidget(resistance_group)
        center_splitter.addWidget(temperature_group)
        center_splitter.addWidget(log_group)
        center_splitter.setStretchFactor(0, 2)
        center_splitter.setStretchFactor(1, 2)
        center_splitter.setStretchFactor(2, 1)
        center_splitter.setSizes([260, 260, 180])

        layout.addWidget(center_splitter, 1)
        panel.setLayout(layout)
        return panel

    def create_right_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(305)
        panel.setMaximumWidth(380)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        gas_group = self.group("Gas Controls", "tealGroup")
        gas_layout = QGridLayout()
        gas_layout.setContentsMargins(10, 12, 10, 10)
        gas_layout.setHorizontalSpacing(8)
        gas_layout.setVerticalSpacing(7)
        gas_layout.addWidget(QLabel("NH3 flow"), 0, 0)
        gas_layout.addWidget(self.nh3_control, 0, 1)
        gas_layout.addWidget(QLabel("NH3 duration"), 1, 0)
        gas_layout.addWidget(self.nh3_duration, 1, 1)
        gas_layout.addWidget(self.apply_nh3_button, 2, 0, 1, 2)
        gas_layout.addWidget(QLabel("Air flow"), 3, 0)
        gas_layout.addWidget(self.air_control, 3, 1)
        gas_layout.addWidget(QLabel("Air duration"), 4, 0)
        gas_layout.addWidget(self.air_duration, 4, 1)
        gas_layout.addWidget(self.apply_air_button, 5, 0, 1, 2)
        gas_layout.addWidget(self.air_purge_button, 6, 0, 1, 2)
        gas_layout.setColumnStretch(1, 1)
        gas_group.setLayout(gas_layout)

        env_group = self.group("Environment", "yellowGroup")
        env_layout = QGridLayout()
        env_layout.setContentsMargins(10, 12, 10, 10)
        env_layout.setHorizontalSpacing(8)
        env_layout.setVerticalSpacing(7)
        env_layout.addWidget(QLabel("Humidity"), 0, 0)
        env_layout.addWidget(self.humidity_off_button, 0, 1)
        env_layout.addWidget(self.humidity_on_button, 0, 2)
        env_layout.addWidget(QLabel("Duration"), 1, 0)
        env_layout.addWidget(self.humidity_duration, 1, 1, 1, 2)
        env_layout.addWidget(QLabel("Heating"), 2, 0)
        env_layout.addWidget(self.heating_off_button, 2, 1)
        env_layout.addWidget(self.heating_on_button, 2, 2)
        env_layout.addWidget(QLabel("Duration"), 3, 0)
        env_layout.addWidget(self.heating_duration, 3, 1, 1, 2)
        env_group.setLayout(env_layout)

        layout.addWidget(gas_group)
        layout.addWidget(env_group)
        layout.addStretch()
        panel.setLayout(layout)
        return panel

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

    def group(self, title, object_name):
        group = QGroupBox(title)
        group.setObjectName(object_name)
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        return group

    def metric_value(self, text):
        label = QLabel(text)
        label.setObjectName("metricValue")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return label

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

    def device_row(self, name, status):
        row = QFrame()
        row.setObjectName("deviceRow")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        name_label = QLabel(name)
        layout.addWidget(name_label)
        layout.addWidget(self.mfc_status_label)
        layout.addWidget(self.mfc_note_label)

        row.setLayout(layout)
        return row

    def create_multimeter_control(self):
        row = QFrame()
        row.setObjectName("deviceRow")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(3)

        title = QLabel("Multimeter")
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(5)
        mode_layout.addWidget(self.multimeter_mode_selector, 1)
        mode_layout.addWidget(self.scan_visa_button, 0)
        mode_layout.addWidget(self.connect_multimeter_button, 0)

        connect_layout = QHBoxLayout()
        connect_layout.setContentsMargins(0, 0, 0, 0)
        connect_layout.setSpacing(5)
        connect_layout.addWidget(self.visa_device_selector, 1)

        layout.addWidget(title)
        layout.addLayout(mode_layout)
        layout.addLayout(connect_layout)
        layout.addWidget(self.multimeter_resource_input)
        layout.addWidget(self.multimeter_status_label)

        row.setLayout(layout)
        return row

    def create_mfc_control(self):
        row = QFrame()
        row.setObjectName("deviceRow")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(3)

        title = QLabel("MFC Controller")

        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(5)
        mode_layout.addWidget(self.mfc_mode_selector, 1)
        mode_layout.addWidget(self.scan_mfc_button, 0)
        mode_layout.addWidget(self.connect_mfc_button, 0)

        port_layout = QHBoxLayout()
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.setSpacing(5)
        port_layout.addWidget(self.mfc_port_selector, 1)

        layout.addWidget(title)
        layout.addLayout(mode_layout)
        layout.addLayout(port_layout)
        layout.addWidget(self.mfc_status_label)
        layout.addWidget(self.mfc_note_label)

        row.setLayout(layout)
        return row

    def create_plot(self, title, left_label, units, color):
        plot = pg.PlotWidget(title=title)
        plot.setBackground("w")
        plot.setLabel("left", left_label, units=units)
        plot.setLabel("bottom", "Time", units="s")
        plot.showGrid(x=True, y=True, alpha=0.22)
        plot.setMinimumSize(0, 120)
        plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot.getAxis("left").setPen(pg.mkPen("#64748b"))
        plot.getAxis("bottom").setPen(pg.mkPen("#64748b"))
        plot.getAxis("left").setTextPen(pg.mkPen("#334155"))
        plot.getAxis("bottom").setTextPen(pg.mkPen("#334155"))
        plot.setTitle(
            f"<span style='color: #0f172a; font-weight: 700;'>{title}</span>",
            size="10pt",
        )
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

        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setMinimumSectionSize(58)
        self.log_table.verticalHeader().setDefaultSectionSize(26)

    def duration_ms(self, duration_input):
        return duration_input.value() * 1000

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
        self.log_table.setRowCount(0)

        self.resistance_curve.setData([], [])
        self.temperature_curve.setData([], [])

        self.manager.start_experiment(
            self.format_selector.currentText(),
            self.data_directory,
        )

    def choose_data_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select data folder",
            self.data_directory,
        )
        if not folder:
            return

        self.data_directory = folder
        self.data_folder_label.setText(self.compact_path(folder))
        self.data_folder_label.setToolTip(folder)
        self.file_label.setText(f"Data folder: {folder}")

    @staticmethod
    def compact_path(path, max_length=28):
        if len(path) <= max_length:
            return path
        return "..." + path[-(max_length - 3):]

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
        self.format_selector.setEnabled(False)
        self.data_folder_button.setEnabled(False)
        self.status_label.setText("RUNNING")
        self.set_status_badge_state("running")
        self.file_label.setText(filename)

    def on_experiment_stopped(self, message):
        self.completed_experiment_exists = True
        self.format_selector.setEnabled(True)
        self.data_folder_button.setEnabled(True)
        self.status_label.setText("STOPPED")
        self.set_status_badge_state("stopped")
        self.reset_duration_controls()
        self.file_label.setText(message)

    def on_device_error(self, message):
        self.status_label.setText("ERROR")
        self.set_status_badge_state("error")
        self.file_label.setText(message)

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

    def on_multimeter_mode_changed(self, text):
        is_real = text == "Real multimeter"
        self.visa_device_selector.setEnabled(is_real)
        self.multimeter_resource_input.setEnabled(is_real)
        self.scan_visa_button.setEnabled(is_real)
        self.connect_multimeter_button.setText("Connect" if is_real else "Use")

    def scan_visa_devices(self):
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
            self.visa_device_selector.setEnabled(True)
            self.scan_visa_button.setEnabled(True)

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

    def on_multimeter_changed(self, mode, status):
        if mode == "real":
            self.multimeter_status_label.setText("Connected: real multimeter")
            self.multimeter_status_label.setToolTip(status)
        else:
            self.multimeter_status_label.setText("Connected: simulated")
            self.multimeter_status_label.setToolTip(status)

    def on_mfc_mode_changed(self, text):
        is_real = text == "Real MFC"
        self.mfc_port_selector.setEnabled(is_real)
        self.scan_mfc_button.setEnabled(is_real)
        self.connect_mfc_button.setText("Connect" if is_real else "Use")
        self.set_mfc_write_controls_enabled(not is_real)

        if is_real:
            self.mfc_note_label.setText(
                "Flow writes disabled."
            )
        else:
            self.mfc_note_label.setText(
                "Simulated MFC: gas controls affect only the software model."
            )

    def scan_mfc_ports(self):
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

    def on_mfc_changed(self, mode, status):
        if mode == "real":
            self.mfc_status_label.setText(self.compact_mfc_status(status))
            self.mfc_status_label.setToolTip(status)
            self.set_mfc_write_controls_enabled(False)
        else:
            self.mfc_status_label.setText("Connected: simulated")
            self.mfc_status_label.setToolTip(status)
            self.set_mfc_write_controls_enabled(True)

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

    def apply_nh3(self):
        self.manager.apply_nh3(
            self.nh3_control.value(),
            self.duration_ms(self.nh3_duration),
        )

    def apply_air(self):
        self.manager.apply_air(self.air_control.value())

    def set_humidity(self, enabled):
        self.manager.set_humidity(
            enabled,
            self.duration_ms(self.humidity_duration),
        )

    def set_heating(self, enabled):
        self.manager.set_heating(
            enabled,
            self.duration_ms(self.heating_duration),
        )

    def refresh_state_label(self, state):
        humidity = "ON" if state.humidity_on else "OFF"
        heating = "ON" if state.heating_on else "OFF"

        self.nh3_value_label.setText(f"{state.nh3_actual_sccm:g} sccm")
        self.air_value_label.setText(f"{state.air_actual_sccm:g} sccm")
        self.humidity_value_label.setText(humidity)
        self.heating_value_label.setText(heating)

        self.nh3_control.setValue(state.nh3_setpoint_sccm)
        self.air_control.setValue(state.air_setpoint_sccm)

    def on_data_acquired(self, data, event):
        self.time_data.append(data["elapsed_s"])
        self.resistance_data.append(data["resistance_ohm"])
        self.temperature_data.append(data["temperature_c"])

        self.resistance_curve.setData(self.time_data, self.resistance_data)
        self.temperature_curve.setData(self.time_data, self.temperature_data)
        self.update_plot_ranges()

        self.resistance_value_label.setText(
            self.format_number(data["resistance_ohm"], suffix=" Ohm", precision=2)
        )
        self.temperature_value_label.setText(
            self.format_number(data["temperature_c"], suffix=" deg C", precision=2)
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

    def closeEvent(self, event):
        self.manager.close()
        event.accept()

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget#appBackground {
                background: #f3f6fa;
            }
            QFrame#toolbar {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QSplitter#bodySplitter::handle {
                background: #edf2f7;
                width: 3px;
                margin: 8px 0;
                border-radius: 1px;
            }
            QSplitter#centerSplitter::handle {
                background: #e2e8f0;
                height: 5px;
                margin: 3px 0;
                border-radius: 2px;
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
            QGroupBox {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-top: 3px solid #64748b;
                border-radius: 0;
                margin-top: 20px;
                padding: 9px;
                font-weight: 700;
                color: #102033;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                top: 1px;
                padding: 0 10px 2px 10px;
                background: #f3f6fa;
                color: #334155;
                font-size: 12px;
            }
            QGroupBox#blueGroup {
                border-top-color: #64748b;
            }
            QGroupBox#greenGroup {
                border-top-color: #64748b;
            }
            QGroupBox#purpleGroup {
                border-top-color: #64748b;
            }
            QGroupBox#orangeGroup {
                border-top-color: #64748b;
            }
            QGroupBox#tealGroup {
                border-top-color: #64748b;
            }
            QGroupBox#yellowGroup {
                border-top-color: #64748b;
            }
            QFrame#metricRow,
            QFrame#deviceRow {
                background: #f8fafc;
                border: 1px solid #edf2f7;
                border-radius: 6px;
            }
            QFrame#metricRow {
                min-height: 32px;
                max-height: 36px;
            }
            QLabel {
                color: #233244;
                font-size: 12px;
            }
            QLabel#caption,
            QLabel#metricName,
            QLabel#mutedLabel {
                color: #64748b;
                font-size: 11px;
                font-weight: 500;
            }
            QLabel#toolbarSectionLabel {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#metricValue,
            QLabel#toolbarValue {
                color: #0f172a;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#statusBadge {
                background: #dcfce7;
                color: #15803d;
                border-radius: 10px;
                padding: 3px 8px;
                font-weight: 700;
            }
            QLabel#statusBadge[state="running"] {
                background: #dbeafe;
                color: #1d4ed8;
            }
            QLabel#statusBadge[state="error"] {
                background: #fee2e2;
                color: #dc2626;
            }
            QLabel#statusBadge[state="stopped"] {
                background: #fee2e2;
                color: #dc2626;
            }
            QLabel#connectedLabel {
                color: #16a34a;
                font-size: 11px;
                font-weight: 600;
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
                border-radius: 5px;
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
                image: url(gas_sensor_daq/ui/assets/chevron_down.svg);
                width: 12px;
                height: 12px;
            }
            QPushButton {
                min-height: 28px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 4px 8px;
                background: #ffffff;
                color: #172033;
            }
            QPushButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton#stepButton {
                min-height: 26px;
                padding: 0;
                font-size: 14px;
                font-weight: 700;
            }
            QGroupBox#greenGroup QComboBox,
            QGroupBox#greenGroup QLineEdit {
                min-height: 24px;
                font-size: 11px;
            }
            QGroupBox#greenGroup QPushButton {
                min-height: 24px;
                padding: 2px 5px;
                font-size: 11px;
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
        """)
