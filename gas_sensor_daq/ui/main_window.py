import math
import re
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPixmap, QTransform
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

from gas_sensor_daq.core.acquisition_manager import AcquisitionManager
from gas_sensor_daq.core.experiment_design import (
    DEFAULT_TARGET_TOTAL_FLOW,
    calculate_mixture_setpoints,
    flow_matches_target,
    parse_duration_seconds,
    rack_capacity,
)
from gas_sensor_daq.devices.visa_discovery import discover_visa_instruments
from gas_sensor_daq.ui.recipe_table import (
    add_recipe_step,
    clear_recipe_steps,
    configure_recipe_table,
    duplicate_recipe_step,
    recipe_event,
    remove_recipe_step,
    set_recipe_editable,
    set_recipe_event,
    style_recipe_rh_item,
    style_recipe_total_item,
)
from gas_sensor_daq.ui.log_preview import LogPreviewTable
from gas_sensor_daq.ui.experiment_schedule import ExperimentSchedulePanel
from gas_sensor_daq.ui.device_status import DeviceStatusPanel
from gas_sensor_daq.ui.experiment_status import ExperimentStatusPanel
from gas_sensor_daq.ui.mfc_monitor import MFCMonitorPanel
from gas_sensor_daq.ui.current_readings import CurrentReadingsPanel
from gas_sensor_daq.ui.live_measurement import LiveMeasurementPanel
from gas_sensor_daq.ui.toolbar import ApplicationToolbar
from gas_sensor_daq.ui.styles import application_style

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.assets_dir = Path(__file__).resolve().parent / "assets"
        self.setWindowTitle("Gas Sensor DAQ & MFC Control")
        self.setWindowIcon(QIcon(str(self.assets_dir / "signal_sensor.svg")))

        self.setMinimumSize(1280, 720)

        self.manager = AcquisitionManager(self)
        self.time_data = []
        self.resistance_data = []
        self.mfc_flow_data = {index: [] for index in range(1, 7)}
        self.mfc_channel_colors = {
            1: "#2563eb",
            2: "#f97316",
            3: "#16a34a",
            4: "#7c3aed",
            5: "#dc2626",
            6: "#0f9f9a",
        }
        self.event_markers = []
        self.completed_experiment_exists = False
        self.max_log_preview_rows = 5
        self.log_preview_expanded = False
        self.recipe_to_run = ()
        self.validating_recipe = False
        self.data_directory = self.manager.data_directory
        self.current_file_path = ""
        self.experiment_status_step_index = -1
        self.experiment_step_deadline = None
        self.experiment_status_state = "idle"
        self.experiment_last_step_index = -1
        self.experiment_status_timer = QTimer(self)
        self.experiment_status_timer.setInterval(1000)
        self.experiment_status_timer.timeout.connect(self.update_experiment_status)

        self.setup_ui()
        self.connect_manager_signals()
        self.refresh_state_label(self.manager.current_state())

    def setup_ui(self):
        self.status_label = QLabel("IDLE")
        self.status_label.setObjectName("statusBadge")
        self.status_label.setProperty("state", "idle")
        self.status_label.setFixedSize(88, 32)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.file_label = QLabel("No file open")
        self.file_label.setObjectName("mutedLabel")
        self.file_label.setMaximumWidth(100)
        self.file_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.file_label.setFixedHeight(32)
        self.file_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.elapsed_label = QLabel("00:00:00")
        self.elapsed_label.setObjectName("toolbarValue")
        self.elapsed_label.setFixedHeight(32)
        self.rate_input = QDoubleSpinBox()
        self.rate_input.setRange(0.1, 10.0)
        self.rate_input.setDecimals(1)
        self.rate_input.setSingleStep(0.1)
        self.rate_input.setValue(1000 / self.manager.acquisition_interval_ms)
        self.rate_input.setAlignment(Qt.AlignCenter)
        self.rate_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.rate_input.setObjectName("rateInput")
        self.rate_input.setFixedSize(38, 22)
        self.rate_input.valueChanged.connect(self.on_rate_changed)
        self.rate_minus_button = QPushButton()
        self.rate_plus_button = QPushButton()
        self.rate_minus_button.setIcon(QIcon(str(self.assets_dir / "minus-small.png")))
        self.rate_plus_button.setIcon(QIcon(str(self.assets_dir / "plus-small.png")))
        for button, callback in (
            (self.rate_minus_button, self.rate_input.stepDown),
            (self.rate_plus_button, self.rate_input.stepUp),
        ):
            button.setObjectName("rateStepButton")
            button.setFixedSize(38, 22)
            button.setIconSize(QSize(14, 14))
            button.clicked.connect(callback)
        self.rate_minus_button.setToolTip("Decrease sampling rate")
        self.rate_plus_button.setToolTip("Increase sampling rate")

        self.rate_unit_label = QLabel("Hz")
        self.rate_unit_label.setObjectName("rateUnitBox")
        self.rate_unit_label.setFixedSize(26, 22)
        self.rate_unit_label.setAlignment(Qt.AlignCenter)
        self.rate_control = QWidget()
        self.rate_control.setFixedHeight(22)
        rate_layout = QHBoxLayout()
        rate_layout.setContentsMargins(0, 0, 0, 0)
        rate_layout.setSpacing(2)
        rate_layout.addWidget(self.rate_minus_button)
        rate_layout.addWidget(self.rate_input)
        rate_layout.addWidget(self.rate_unit_label)
        rate_layout.addWidget(self.rate_plus_button)
        self.rate_control.setLayout(rate_layout)
        self.rate_control.setFixedWidth(146)

        self.save_location_input = QLineEdit()
        self.save_location_input.setObjectName("saveLocationInput")
        self.save_location_input.setMinimumWidth(0)
        self.filename_stem = "experiment"
        self.save_location_input.setToolTip(
            "Edit the file name. Use the folder button to change the save location."
        )
        self.save_location_input.editingFinished.connect(self.on_filename_stem_changed)
        self.update_save_location_display()
        self.choose_save_location_button = QPushButton()
        self.choose_save_location_button.setObjectName("folderButton")
        self.choose_save_location_button.setFixedSize(32, 32)
        self.choose_save_location_button.setIcon(QIcon(str(self.assets_dir / "folder.png")))
        self.choose_save_location_button.setIconSize(QSize(16, 16))
        self.choose_save_location_button.setToolTip("Choose save location")
        self.choose_save_location_button.clicked.connect(self.choose_save_location)
        self.system_message_label = QLabel("All systems normal. Ready.")
        self.system_message_label.setObjectName("systemMessageText")

        self.format_selector = QComboBox()
        self.format_selector.setObjectName("toolbarFormatSelector")
        self.format_selector.addItems(["CSV", "Excel"])
        self.format_selector.setView(QListView())
        self.format_selector.view().setObjectName("toolbarFormatPopup")
        self.format_selector.setMinimumWidth(0)
        self.format_selector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.format_selector.setFixedHeight(32)
        self.format_selector.currentTextChanged.connect(self.on_save_format_changed)
        self.update_save_location_display(preview=True)
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
        self.multimeter_mode_selector = QComboBox()
        self.multimeter_mode_selector.addItem("Simulated", "simulation")
        self.multimeter_mode_selector.addItem("Real", "real")
        self.multimeter_mode_selector.setItemData(0, "Simulated multimeter mode", Qt.ToolTipRole)
        self.multimeter_mode_selector.setItemData(1, "Real multimeter mode", Qt.ToolTipRole)
        self.visa_device_selector = QComboBox()
        self.visa_device_selector.addItem("Not scanned", "")
        self.visa_device_selector.setItemData(
            0, "Scan to search for VISA instruments.", Qt.ToolTipRole
        )
        self.visa_device_selector.setMinimumWidth(0)
        self.multimeter_resource_input = QLineEdit()
        self.multimeter_resource_input.setPlaceholderText("USB0::...::INSTR")
        self.multimeter_resource_input.setText(self.manager.multimeter_resource)
        self.multimeter_resource_input.setVisible(False)
        self.scan_visa_button = QPushButton("Scan")
        self.connect_multimeter_button = QPushButton("Use")
        self.scan_visa_button.setFixedWidth(76)
        self.connect_multimeter_button.setFixedWidth(76)
        self.multimeter_status_label = QLabel(self.manager.multimeter_status_text())
        self.multimeter_status_label.setObjectName("connectedLabel")
        self.multimeter_status_label.setWordWrap(True)
        self.multimeter_status_label.setMaximumHeight(34)
        self.mfc_status_label = QLabel("Connected: Simulated")
        self.mfc_status_label.setObjectName("connectedLabel")
        self.mfc_status_label.setWordWrap(True)
        self.mfc_status_label.setMaximumHeight(40)
        self.mfc_note_label = QLabel("Read-only. Scan verifies all 6 MFC nodes before connection.")
        self.mfc_note_label.setObjectName("mutedLabel")
        self.mfc_note_label.setWordWrap(True)
        self.mfc_note_label.setMaximumHeight(28)
        self.multimeter_summary_label = QLabel("Simulated")
        self.multimeter_summary_label.setObjectName("connectedLabel")
        self.mfc_summary_label = QLabel("Simulated")
        self.mfc_summary_label.setObjectName("connectedLabel")
        self.mfc_mode_selector = QComboBox()
        self.mfc_mode_selector.addItem("Simulated", "simulation")
        self.mfc_mode_selector.addItem("Real", "real")
        self.mfc_mode_selector.setItemData(0, "Simulated MFC rack mode", Qt.ToolTipRole)
        self.mfc_mode_selector.setItemData(1, "Real MFC rack mode", Qt.ToolTipRole)
        self.mfc_port_selector = QComboBox()
        self.mfc_port_selector.addItem("Not scanned", "")
        self.mfc_port_selector.setItemData(
            0, "Scan to find and verify the six-node MFC rack.", Qt.ToolTipRole
        )
        self.mfc_verified_ports = set()
        self.scan_mfc_button = QPushButton("Scan Rack")
        self.connect_mfc_button = QPushButton("Use")
        self.scan_mfc_button.setFixedWidth(76)
        self.connect_mfc_button.setFixedWidth(76)

        self.start_button = QPushButton("START")
        self.stop_button = QPushButton("STOP")
        self.start_button.setFixedSize(84, 32)
        self.stop_button.setFixedSize(84, 32)
        self.start_button.setObjectName("startButton")
        self.stop_button.setObjectName("stopButton")
        self.start_button.clicked.connect(self.start_experiment)
        self.stop_button.clicked.connect(
            lambda _checked=False: self.manager.stop_experiment()
        )

        self.resistance_value_label = self.metric_value("--")
        self.max_total_flow_label = self.metric_value("--")
        self.total_actual_label = self.metric_value("--")
        self.total_setpoint_label = self.metric_value("--")
        self.resistance_value_label.setProperty("metricColor", "blue")
        self.max_total_flow_label.setProperty("metricColor", "slate")
        self.total_actual_label.setProperty("metricColor", "purple")
        self.total_setpoint_label.setProperty("metricColor", "teal")
        for value_label in (
            self.resistance_value_label,
            self.max_total_flow_label,
            self.total_actual_label,
            self.total_setpoint_label,
        ):
            value_label.setProperty("compactMetric", "true")
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
            "Î©",
            "#2563eb",
        )
        self.resistance_curve = self.resistance_plot.plot(
            pen=pg.mkPen(color="#2563eb", width=2)
        )

        self.flow_plot = self.create_plot(
            "MFC Flow vs Time",
            "Flow",
            "mln/min",
            "#16a34a",
        )
        self.flow_curves = {
            index: self.flow_plot.plot(
                pen=pg.mkPen(color=color, width=2),
            )
            for index, color in self.mfc_channel_colors.items()
        }

        self.log_table = LogPreviewTable()
        self.recipe_table = QTableWidget(5, 10)
        self.recipe_table.setObjectName("recipeTable")
        self.recipe_table.setHorizontalHeaderLabels([
            "Step",
            "Step Total\n(mln/min)",
            "Duration\n(s/min)",
            "RH\n(%)",
            "MFC 1",
            "MFC 2",
            "MFC 3",
            "MFC 4",
            "MFC 5",
            "MFC 6",
        ])
        for index in range(1, 7):
            capacity = self.manager.mfc_channel_capacity_sccm(index)
            self.recipe_table.horizontalHeaderItem(index + 3).setToolTip(
                f"MFC {index} limit: {capacity:g} mln/min"
            )
        configure_recipe_table(self.recipe_table)
        self.recipe_table.setMouseTracking(True)
        self.recipe_table.viewport().setMouseTracking(True)
        self.recipe_table.setToolTip(
            "All MFC flow values in this schedule are mln/min."
        )
        # Keep five rows visible while leaving room for the two-line header.
        self.recipe_table.setFixedHeight(196)
        self.recipe_table.itemChanged.connect(self.update_recipe_total)
        self.recipe_table.itemChanged.connect(self.validate_recipe_live)
        self.recipe_table.itemChanged.connect(self.update_experiment_status)
        self.recipe_table.cellEntered.connect(self.show_recipe_row_event_tooltip)

        self.recipe_add_button = QPushButton("Add Step")
        self.recipe_duplicate_button = QPushButton("Duplicate")
        self.recipe_remove_button = QPushButton("Remove")
        self.recipe_clear_button = QPushButton("Clear all")
        self.recipe_add_button.setObjectName("recipeAddButton")
        self.recipe_duplicate_button.setObjectName("recipeDuplicateButton")
        self.recipe_remove_button.setObjectName("recipeRemoveButton")
        self.recipe_clear_button.setObjectName("recipeClearButton")
        self.recipe_event_input = QLineEdit()
        self.recipe_event_input.setObjectName("recipeEventInput")
        self.recipe_event_input.setPlaceholderText("Event for selected step")
        self.recipe_event_input.setFixedWidth(250)
        self.recipe_event_input.setFixedHeight(28)
        self.recipe_event_input.setToolTip(
            "Event recorded in the log when the selected step begins."
        )
        self.recipe_event_input.editingFinished.connect(self.commit_recipe_event)
        self.recipe_duration_input = QLineEdit()
        self.recipe_duration_input.setObjectName("recipeDurationInput")
        self.recipe_duration_input.setPlaceholderText("30 s or 2 min")
        self.recipe_duration_input.setFixedWidth(56)
        self.recipe_duration_input.setFixedHeight(24)
        self.recipe_duration_input.setToolTip(
            "Duration for the selected step. Use an explicit unit, for example 30 s or 2 min."
        )
        self.recipe_duration_input.editingFinished.connect(self.commit_recipe_duration)
        self.recipe_rh_input = self.recipe_mixture_input(0.0, 100.0, 0.0)
        self.recipe_rh_input.setSuffix(" %")
        self.recipe_gas_inputs = {
            index: self.recipe_mixture_input(
                0.0,
                self.manager.mfc_channel_capacity_sccm(index),
                0.0,
            )
            for index in range(1, 4)
        }
        self.recipe_dry_mfc5_input = self.recipe_mixture_input(
            0.0,
            self.manager.mfc_channel_capacity_sccm(5),
            0.0,
        )
        self.recipe_mfc6_remainder_label = QLabel("0.0 mln/min")
        self.recipe_mfc6_remainder_label.setObjectName("recipeMixtureValue")
        self.recipe_mfc6_remainder_label.setMinimumWidth(76)
        self.recipe_apply_mixture_button = QPushButton("Calculate mixture")
        self.recipe_apply_mixture_button.setObjectName("recipeMixtureButton")
        self.recipe_apply_mixture_button.setFixedHeight(28)
        self.recipe_apply_mixture_button.clicked.connect(self.apply_recipe_mixture)
        self.recipe_mixture_inputs = (
            self.recipe_rh_input,
            *self.recipe_gas_inputs.values(),
            self.recipe_dry_mfc5_input,
        )
        for input_widget in self.recipe_mixture_inputs:
            input_widget.valueChanged.connect(self.update_recipe_mfc6_remainder)
        self.recipe_target_total_label = QLabel("Target total:")
        self.recipe_target_total_label.setObjectName("recipeMaxTotal")
        self.recipe_target_total_input = QDoubleSpinBox()
        self.recipe_target_total_input.setObjectName("recipeTargetTotal")
        self.recipe_target_total_input.setRange(
            0.1,
            rack_capacity(self.manager.settings.mfc_nodes),
        )
        self.recipe_target_total_input.setDecimals(1)
        self.recipe_target_total_input.setSingleStep(5.0)
        self.recipe_target_total_input.setValue(DEFAULT_TARGET_TOTAL_FLOW)
        self.recipe_target_total_input.setFixedWidth(74)
        self.recipe_target_total_input.setFixedHeight(22)
        self.recipe_target_total_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self._last_recipe_target_total = self.recipe_target_total_input.value()
        self.recipe_target_total_input.editingFinished.connect(
            self.rescale_recipe_for_target_total
        )
        self.recipe_target_total_input.valueChanged.connect(self.update_recipe_mfc6_remainder)
        self.recipe_target_total_unit_label = QLabel("mln/min")
        self.recipe_target_total_unit_label.setObjectName("recipeTargetUnit")
        self.recipe_issues_label = QLabel()
        self.recipe_issues_label.setObjectName("recipeIssues")
        self.recipe_issues_label.hide()
        self.recipe_action_buttons = (
            self.recipe_add_button,
            self.recipe_duplicate_button,
            self.recipe_remove_button,
            self.recipe_clear_button,
        )
        for button in self.recipe_action_buttons:
            button.setFixedHeight(28)
        self.recipe_add_button.clicked.connect(lambda: add_recipe_step(self.recipe_table))
        self.recipe_duplicate_button.clicked.connect(
            lambda: duplicate_recipe_step(self.recipe_table)
        )
        self.recipe_remove_button.clicked.connect(
            lambda: remove_recipe_step(self.recipe_table)
        )
        self.recipe_clear_button.clicked.connect(self.clear_recipe_schedule)
        self.recipe_table.itemSelectionChanged.connect(self.on_recipe_selection_changed)
        self.recipe_table.selectRow(0)
        self.on_recipe_selection_changed()

        root = QWidget()
        root.setObjectName("appBackground")
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(10, 8, 10, 10)
        root_layout.setSpacing(8)

        root_layout.addWidget(self.create_toolbar())

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        body_layout.addWidget(self.scroll_panel(self.create_left_panel()), 1)
        body_layout.addWidget(self.scroll_panel(self.create_center_panel()), 2)
        body_layout.addWidget(self.scroll_panel(self.create_right_panel()), 1)

        root_layout.addLayout(body_layout, 1)
        root.setLayout(root_layout)
        self.setCentralWidget(root)

        self.apply_styles()
        self.on_multimeter_mode_changed(self.multimeter_mode_selector.currentText())
        self.on_mfc_mode_changed(self.mfc_mode_selector.currentText())
        self.update_experiment_status()

    def connect_manager_signals(self):
        self.manager.experiment_started.connect(self.on_experiment_started)
        self.manager.experiment_stopped.connect(self.on_experiment_stopped)
        self.manager.elapsed_changed.connect(self.elapsed_label.setText)
        self.manager.elapsed_changed.connect(
            lambda _elapsed: self.update_experiment_status()
        )
        self.manager.data_acquired.connect(self.on_data_acquired)
        self.manager.state_changed.connect(self.refresh_state_label)
        self.manager.device_error.connect(self.on_device_error)
        self.manager.multimeter_changed.connect(self.on_multimeter_changed)
        self.manager.mfc_changed.connect(self.on_mfc_changed)
        self.manager.recipe_step_changed.connect(self.on_recipe_step_changed)
        self.manager.flow_warning.connect(self.on_flow_warning)

    def create_toolbar(self):
        toolbar = ApplicationToolbar(
            self.save_location_input,
            self.choose_save_location_button,
            self.format_selector,
            self.start_button,
            self.stop_button,
            self.system_message_label,
            self.dismiss_system_message,
        )
        self.toolbar = toolbar
        self.toolbar_controls = toolbar.controls
        self.toolbar_file_path_label = toolbar.file_path_label
        self.system_message_bar = toolbar.message_bar
        self.system_message_icon = toolbar.message_icon
        self.update_save_location_display(preview=True)
        return toolbar

    def reflow_toolbar_controls(self, width):
        if hasattr(self, "toolbar"):
            self.toolbar.reflow()

    def update_toolbar_height(self):
        if not hasattr(self, "toolbar"):
            return
        self.toolbar.adjust_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow_toolbar_controls(event.size().width())

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

    def toolbar_message_bar(self):
        bar = QFrame()
        bar.setObjectName("systemMessageBar")
        bar.setFixedHeight(34)
        bar.setProperty("state", "idle")
        self.system_message_bar = bar
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(7)
        icon = QLabel("i")
        icon.setObjectName("systemMessageIcon")
        icon.setProperty("state", "idle")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(14, 14)
        self.system_message_icon = icon
        self.system_message_label.setProperty("state", "idle")
        dismiss_button = QPushButton("Ã—")
        dismiss_button.setObjectName("systemMessageDismissButton")
        dismiss_button.setFixedSize(18, 18)
        dismiss_button.setToolTip("Dismiss message")
        dismiss_button.clicked.connect(self.dismiss_system_message)
        layout.addWidget(icon)
        layout.addWidget(self.system_message_label, 1)
        layout.addWidget(dismiss_button)
        bar.setLayout(layout)
        return bar

    def create_left_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(305)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        readings_panel = CurrentReadingsPanel(
            self.resistance_value_label,
            self.max_total_flow_label,
            self.total_setpoint_label,
            self.total_actual_label,
        )

        monitor_panel = MFCMonitorPanel(self.zero_mfc_setpoints)
        self.mfc_rack_status_label = monitor_panel.rack_status_label
        self.mfc_channel_monitor = monitor_panel.channel_monitor
        self.zero_mfc_setpoints_button = monitor_panel.zero_setpoints_button

        layout.addWidget(readings_panel.card)
        layout.addWidget(monitor_panel.card)
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

        live_measurement = LiveMeasurementPanel(
            self.resistance_plot,
            self.flow_plot,
            self.mfc_channel_colors,
            self.set_active_plot,
        )
        self.resistance_plot_button = live_measurement.resistance_button
        self.flow_plot_button = live_measurement.flow_button
        self.flow_legend = live_measurement.flow_legend
        self.event_summary = live_measurement.event_summary
        self.event_summary_dot = live_measurement.event_summary_dot
        self.event_summary_label = live_measurement.event_summary_label
        self.plot_stack = live_measurement.plot_stack
        self.set_active_plot("resistance")

        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(0, 0, 0, 10)
        log_layout.addWidget(self.log_table)
        log_card = self.log_card(
            "Log Preview",
            log_layout,
        )
        self.log_card_widget = log_card
        log_card.setMinimumHeight(235)
        self.set_log_preview_expanded(False)

        schedule_panel = ExperimentSchedulePanel(
            table=self.recipe_table,
            event_input=self.recipe_event_input,
            duration_input=self.recipe_duration_input,
            rh_input=self.recipe_rh_input,
            gas_inputs=self.recipe_gas_inputs,
            dry_mfc5_input=self.recipe_dry_mfc5_input,
            mfc6_remainder_label=self.recipe_mfc6_remainder_label,
            apply_mixture_button=self.recipe_apply_mixture_button,
            target_total_label=self.recipe_target_total_label,
            target_total_input=self.recipe_target_total_input,
            target_total_unit_label=self.recipe_target_total_unit_label,
            rate_control=self.rate_control,
            issues_label=self.recipe_issues_label,
            action_buttons=self.recipe_action_buttons,
            toggle_schedule=self.toggle_recipe_schedule,
            toggle_details=self.toggle_recipe_details,
        )
        self.recipe_card_widget = schedule_panel.card
        self.recipe_content_frame = schedule_panel.content_frame
        self.recipe_header_controls = schedule_panel.header_controls
        self.recipe_chevron = schedule_panel.schedule_chevron
        self.recipe_details_title = schedule_panel.details_title
        self.recipe_details_step_label = schedule_panel.details_step_label
        self.recipe_details_chevron = schedule_panel.details_chevron
        self.recipe_details_content = schedule_panel.details_content
        self.recipe_details_expanded = True
        self.set_recipe_schedule_expanded(True)
        self.set_recipe_details_expanded(False)

        layout.addWidget(live_measurement.card, 4)
        layout.addWidget(self.recipe_card_widget)
        layout.addWidget(log_card, 2)
        panel.setLayout(layout)
        return panel

    def create_right_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(305)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        device_panel = DeviceStatusPanel(
            multimeter_mode=self.multimeter_mode_selector,
            multimeter_device=self.visa_device_selector,
            multimeter_resource=self.multimeter_resource_input,
            connect_multimeter=self.connect_multimeter_button,
            scan_multimeter=self.scan_visa_button,
            multimeter_status=self.multimeter_status_label,
            multimeter_summary=self.multimeter_summary_label,
            mfc_mode=self.mfc_mode_selector,
            mfc_port=self.mfc_port_selector,
            connect_mfc=self.connect_mfc_button,
            scan_mfc=self.scan_mfc_button,
            mfc_status=self.mfc_status_label,
            mfc_note=self.mfc_note_label,
            mfc_summary=self.mfc_summary_label,
            toggle_setup=self.toggle_device_setup,
        )
        self.device_setup_bodies = device_panel.setup_bodies
        self.device_control_rows = device_panel.control_rows
        self.multimeter_status_dot = device_panel.multimeter_status_dot
        self.mfc_status_dot = device_panel.mfc_status_dot
        self.device_status_chevron = device_panel.chevron
        self.device_status_chevron.setIcon(self.chevron_icon(expanded=False))
        self.device_status_chevron.setIconSize(QSize(12, 12))

        status_panel = ExperimentStatusPanel()
        self.experiment_state_badge = status_panel.state_badge
        self.experiment_step_caption = status_panel.step_caption
        self.experiment_step_value = status_panel.step_value
        self.experiment_event_value = status_panel.event_value
        self.experiment_time_caption = status_panel.time_caption
        self.experiment_remaining_value = status_panel.remaining_value
        self.experiment_progress = status_panel.progress
        self.experiment_sampling_rate_value = status_panel.sampling_rate_value
        self.experiment_total_time_value = status_panel.total_time_value
        self.experiment_elapsed_value = status_panel.elapsed_value

        layout.addWidget(device_panel.card, 0, Qt.AlignTop)
        layout.addWidget(status_panel.card, 0, Qt.AlignTop)
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
        card.content_frame = content_frame
        return card

    def compact_section_card(self, title, content_layout, title_accent=None):
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

        if title_accent is not None:
            accent = QLabel()
            accent.setObjectName("sectionAccentDot")
            accent.setFixedSize(8, 8)
            accent.setStyleSheet(
                f"background: {title_accent}; border-radius: 4px;"
            )
            header.addWidget(accent)
            header.addSpacing(7)
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
        content_layout.setContentsMargins(0, 0, 0, 0)

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

        title_label = QLabel(title)
        title_label.setObjectName("graphTitle")

        header.addWidget(title_label)
        header.addStretch()

        rows_layout = QHBoxLayout()
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(3)
        rows_label = QLabel("Rows:")
        rows_label.setObjectName("mutedLabel")
        rows_layout.addWidget(rows_label)
        rows_layout.addWidget(self.log_rows_selector)

        rows_widget = QWidget()
        rows_widget.setLayout(rows_layout)
        self.log_header_controls = QWidget()
        header_controls_layout = QHBoxLayout()
        header_controls_layout.setContentsMargins(0, 0, 0, 0)
        header_controls_layout.setSpacing(8)
        header_controls_layout.addWidget(self.open_data_folder_button)
        header_controls_layout.addWidget(self.view_full_log_button)
        header_controls_layout.addWidget(rows_widget)
        self.log_header_controls.setLayout(header_controls_layout)
        header.addWidget(self.log_header_controls)

        self.log_chevron = QPushButton()
        self.log_chevron.setObjectName("logChevron")
        self.log_chevron.setFixedSize(24, 22)
        self.log_chevron.setCheckable(True)
        self.log_chevron.setToolTip("Show or hide log preview")
        self.log_chevron.clicked.connect(self.toggle_log_preview)
        header.addWidget(self.log_chevron)

        layout.addLayout(header)
        self.log_content_frame = QFrame()
        self.log_content_frame.setObjectName("logContentFrame")
        self.log_content_frame.setLayout(content_layout)
        layout.addWidget(self.log_content_frame, 1)
        card.setLayout(layout)
        return card

    def metric_value(self, text):
        label = QLabel(text)
        label.setObjectName("metricValue")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return label

    def state_row(self, name, value_label):
        row = QFrame()
        row.setObjectName("compactStateRow")

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(8)

        name_label = QLabel(name)
        name_label.setObjectName("experimentStatusName")

        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(name_label)
        layout.addStretch()
        layout.addWidget(value_label)

        row.setLayout(layout)
        return row

    def toggle_device_setup(self, _checked=False):
        setup_bodies = getattr(self, "device_setup_bodies", [])
        visible = not setup_bodies[0].isVisible() if setup_bodies else False
        for body in setup_bodies:
            body.setVisible(visible)
        for row in getattr(self, "device_control_rows", []):
            if visible:
                row.setMinimumHeight(0)
                row.setMaximumHeight(16_777_215)
                row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                row.setFixedHeight(46)
        if hasattr(self, "device_status_chevron"):
            self.device_status_chevron.setIcon(self.chevron_icon(expanded=visible))
            self.device_status_chevron.setChecked(visible)
        if visible:
            self.mfc_mode_selector.setFocus(Qt.OtherFocusReason)

    def create_plot(self, title, left_label, units, color):
        plot = pg.PlotWidget()
        plot.setBackground("w")
        axis_label_style = {
            "color": "#334155",
            "font-size": "11px",
            "font-weight": "600",
        }
        plot.setLabel("left", f"{left_label} ({units})", **axis_label_style)
        plot.setLabel("bottom", "Time (s)", **axis_label_style)
        plot.showGrid(x=True, y=True, alpha=0.26)
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

    def on_log_rows_changed(self, value):
        self.max_log_preview_rows = int(value)
        self.log_table.set_max_rows(self.max_log_preview_rows)
        self.update_log_preview_height()

    def update_log_preview_height(self):
        if not hasattr(self, "log_card_widget"):
            return

        if not self.log_preview_expanded:
            self.log_card_widget.setMinimumHeight(52)
            self.log_card_widget.setMaximumHeight(52)
            return

        visible_rows = min(self.max_log_preview_rows, 10)
        table_height = 34 + visible_rows * self.log_table.verticalHeader().defaultSectionSize()
        self.log_table.setMinimumHeight(table_height)
        self.log_card_widget.setMinimumHeight(table_height + 78)
        if self.max_log_preview_rows <= 5:
            self.log_card_widget.setMaximumHeight(table_height + 88)
        else:
            self.log_card_widget.setMaximumHeight(16777215)

    def set_log_preview_expanded(self, expanded):
        self.log_preview_expanded = expanded
        self.log_content_frame.setVisible(expanded)
        self.log_header_controls.setVisible(expanded)
        self.log_chevron.setChecked(expanded)
        self.log_chevron.setIcon(self.chevron_icon(expanded=expanded))
        self.update_log_preview_height()

    def toggle_log_preview(self):
        self.set_log_preview_expanded(not self.log_preview_expanded)

    def set_recipe_schedule_expanded(self, expanded):
        self.recipe_schedule_expanded = expanded
        self.recipe_content_frame.setVisible(expanded)
        self.recipe_header_controls.setVisible(expanded)
        self.recipe_chevron.setChecked(expanded)
        self.recipe_chevron.setIcon(self.chevron_icon(expanded=expanded))

        if expanded:
            minimum_height = 488 if self.recipe_details_expanded else 372
            self.recipe_card_widget.setMinimumHeight(minimum_height)
            self.recipe_card_widget.setMaximumHeight(16777215)
            self.recipe_card_widget.setSizePolicy(
                QSizePolicy.Preferred, QSizePolicy.Preferred
            )
        else:
            self.recipe_card_widget.setMinimumHeight(48)
            self.recipe_card_widget.setMaximumHeight(48)
            self.recipe_card_widget.setSizePolicy(
                QSizePolicy.Preferred, QSizePolicy.Fixed
            )

    def toggle_recipe_schedule(self):
        self.set_recipe_schedule_expanded(not self.recipe_schedule_expanded)

    def set_recipe_details_expanded(self, expanded):
        self.recipe_details_expanded = expanded
        self.recipe_details_content.setVisible(expanded)
        self.recipe_details_chevron.setChecked(expanded)
        self.recipe_details_chevron.setIcon(self.chevron_icon(expanded=expanded))

        if self.recipe_schedule_expanded:
            self.recipe_card_widget.setMinimumHeight(488 if expanded else 372)

    def toggle_recipe_details(self):
        self.set_recipe_details_expanded(not self.recipe_details_expanded)

    def start_experiment(self):
        # UI preview data is deliberately cleared before each run. The manager
        # will create a new CSV/XLSX file for the new experiment.
        self.commit_filename_stem()
        self.commit_recipe_event()
        if not self.ensure_ready_to_start():
            return

        if self.completed_experiment_exists and not self.confirm_new_experiment():
            return

        # Keep the complete live-validation summary visible instead of
        # replacing it with the first error raised while building a run.
        if not self.validate_recipe_live():
            return
        try:
            self.recipe_to_run = self.schedule_steps()
            self.manager.validate_recipe_start(self.recipe_to_run)
        except (ValueError, RuntimeError, ConnectionError) as exc:
            self.on_device_error(f"Experiment is invalid. {exc}")
            return

        if self.manager.mfc_mode == "real" and not self.confirm_real_schedule_start():
            self.recipe_to_run = ()
            return

        self.time_data.clear()
        self.resistance_data.clear()
        for values in self.mfc_flow_data.values():
            values.clear()
        self.clear_event_markers()
        self.log_table.clear_records()

        self.resistance_curve.setData([], [])
        for curve in self.flow_curves.values():
            curve.setData([], [])

        self.manager.start_experiment(
            self.format_selector.currentText(),
            self.data_directory,
            self.filename_stem,
            {
                "target_total_mln_min": self.recipe_target_total_input.value(),
                "schedule": self.recipe_to_run,
            },
        )

    def open_data_folder(self):
        if not self.data_directory:
            self.set_system_message("Choose a save location first.", "warning")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.data_directory))

    def choose_save_location(self):
        if self.is_experiment_running():
            return

        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose save location",
            self.data_directory,
        )
        if not directory:
            return

        self.data_directory = directory
        self.manager.data_directory = directory
        self.update_save_location_display(preview=True)

    def zero_mfc_setpoints(self):
        if self.is_experiment_running():
            QMessageBox.warning(
                self,
                "Experiment is running",
                "Use STOP to end the experiment safely and reset all MFC setpoints.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Zero all MFC setpoints",
            "Set every MFC setpoint to 0 mln/min?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        if self.manager.safe_shutdown_controls():
            self.set_system_message("All MFC setpoints were reset to zero.", "stopped")

    def on_save_format_changed(self):
        if not self.is_experiment_running():
            self.update_save_location_display(preview=True)

    def on_filename_stem_changed(self):
        if self.is_experiment_running():
            return

        self.commit_filename_stem()

    def commit_filename_stem(self):
        """Use the current toolbar text as the next experiment file name."""
        if self.is_experiment_running():
            return

        entered_name = Path(self.save_location_input.text().strip()).name
        for extension in (".csv", ".xlsx"):
            if entered_name.lower().endswith(extension):
                entered_name = entered_name[:-len(extension)]
                break
        entered_name = entered_name.replace("_<timestamp>", "")
        self.filename_stem = self.manager.sanitize_filename_stem(entered_name)
        self.update_save_location_display(preview=True)

    def update_save_location_display(self, filename="", preview=False):
        file_name = Path(filename).name if filename else ""
        if preview:
            extension = "csv"
            if self.format_selector.currentText() == "Excel":
                extension = "xlsx"
            file_name = f"{self.filename_stem}_<timestamp>.{extension}"
        elif not file_name:
            file_name = self.filename_stem
        has_save_location = bool(self.data_directory)
        full_path = (
            str(Path(self.data_directory) / file_name)
            if has_save_location and file_name
            else "No save location selected"
        )
        display_name = self.filename_stem if preview or not filename else Path(filename).stem
        self.save_location_input.setText(display_name)
        self.save_location_input.setToolTip(
            f"Output: {full_path}\n"
            "Edit the experiment name. The timestamp and selected file extension are added automatically."
        )
        if hasattr(self, "choose_save_location_button"):
            self.choose_save_location_button.setToolTip(
                "Choose save location\n"
                f"Current folder: {self.data_directory or 'Not selected'}"
            )
        if hasattr(self, "toolbar_file_path_label"):
            self.toolbar_file_path_label.setText(
                f"File path: {self.data_directory or 'Not selected'}"
            )
            self.toolbar_file_path_label.setToolTip(full_path)

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

    def confirm_real_schedule_start(self):
        target_total = self.recipe_target_total_input.value()
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("Start real MFC schedule?")
        dialog.setText(
            f"Run {len(self.recipe_to_run)} schedule step(s) on the real MFC rack?"
        )
        dialog.setInformativeText(
            f"The target total is {target_total:g} mln/min. The app will apply the "
            "six-channel setpoints for every step, write the event log, and command "
            "all MFCs to zero on Stop, error, or completion. Confirm the gas path and "
            "sensor-chamber outlet are open before continuing."
        )
        start_button = dialog.addButton("Start real schedule", QMessageBox.AcceptRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        return dialog.clickedButton() == start_button

    def clear_recipe_schedule(self):
        if self.is_experiment_running():
            return

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("Clear experiment schedule?")
        dialog.setText("Clear every step in the experiment schedule?")
        dialog.setInformativeText(
            "This cannot be undone. One empty Step 1 will remain for creating a new schedule."
        )
        clear_button = dialog.addButton("Clear all", QMessageBox.DestructiveRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        if dialog.clickedButton() != clear_button:
            return

        self.recipe_table.blockSignals(True)
        try:
            clear_recipe_steps(self.recipe_table)
        finally:
            self.recipe_table.blockSignals(False)
        self.on_recipe_selection_changed()
        self.validate_recipe_live()

    def ensure_ready_to_start(self):
        if not self.data_directory:
            self.on_device_error(
                "Choose a save location with the folder button before starting the experiment."
            )
            return False

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
        return self.multimeter_mode_selector.currentData() == "real"

    def is_real_mfc_mode(self):
        return self.mfc_mode_selector.currentData() == "real"

    def on_rate_changed(self, rate_hz):
        self.manager.set_acquisition_rate_hz(rate_hz)
        self.update_experiment_status()

    def schedule_steps(self):
        steps = []
        for row in range(self.recipe_table.rowCount()):
            duration_seconds = self.recipe_duration_number(row)
            rh = self.recipe_number(row, 3, "RH")
            if rh > 100:
                raise ValueError(f"Step {row + 1} RH must be between 0 and 100%.")
            setpoints = {
                index: self.recipe_number(row, index + 3, f"MFC {index}")
                for index in range(1, 7)
            }
            if duration_seconds == 0 and not any(setpoints.values()):
                continue
            if duration_seconds <= 0:
                raise ValueError(f"Step {row + 1} duration must be greater than zero.")
            for index, value in setpoints.items():
                capacity = self.manager.mfc_channel_capacity_sccm(index)
                if value > capacity:
                    raise ValueError(
                        f"Step {row + 1} MFC {index} setpoint {value:g} mln/min "
                        f"exceeds its {capacity:g} mln/min limit."
                    )

            total_setpoint = self.recipe_number(row, 1, "step total")
            channel_total = sum(setpoints.values())
            if not math.isclose(total_setpoint, channel_total, rel_tol=0, abs_tol=0.01):
                raise ValueError(
                    f"Step {row + 1} step total ({total_setpoint:g} mln/min) must equal "
                    f"the sum of MFC setpoints ({channel_total:g} mln/min)."
                )
            target_total = self.recipe_target_total_input.value()
            if not flow_matches_target(channel_total, target_total):
                raise ValueError(
                    f"Step {row + 1} total ({channel_total:g} mln/min) must equal "
                    f"the {target_total:g} mln/min target flow."
                )
            steps.append({
                "total_setpoint_mln_min": total_setpoint,
                "target_total_mln_min": target_total,
                "duration_ms": round(duration_seconds * 1_000),
                "rh_percent": rh,
                "setpoints": setpoints,
                "event_name": recipe_event(self.recipe_table, row),
            })
        if not steps:
            raise ValueError("Add at least one experiment step.")
        return steps

    def update_recipe_total(self, changed_item):
        row = changed_item.row()
        if changed_item.column() == 3:
            self.apply_recipe_rh_from_table(row)
            return
        if changed_item.column() < 4:
            return

        self.update_recipe_total_from_setpoints(row)

    def update_recipe_total_from_setpoints(self, row):
        values = []
        invalid_value = False
        for column in range(4, 10):
            item = self.recipe_table.item(row, column)
            raw_value = item.text().strip() if item is not None else ""
            numeric_text = self.recipe_numeric_text(raw_value)
            if numeric_text is None:
                invalid_value = True
                break
            values.append(float(numeric_text))

        total_item = self.recipe_table.item(row, 1)
        if total_item is None:
            total_item = QTableWidgetItem()
            total_item.setTextAlignment(Qt.AlignCenter)
            total_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.recipe_table.setItem(row, 1, total_item)

        self.recipe_table.blockSignals(True)
        try:
            total_item.setText("--" if invalid_value else f"{sum(values):g}")
            style_recipe_total_item(total_item)
            self.update_recipe_rh(row)
        finally:
            self.recipe_table.blockSignals(False)

    def apply_recipe_rh_from_table(self, row):
        """Use a manually entered RH target to update the humid-air MFC flow."""
        rh = self.recipe_cell_value(row, 3)
        if rh is None or rh < 0 or rh > 100:
            return

        mfc4_item = self.recipe_table.item(row, 7)
        if mfc4_item is None:
            return

        target_total = self.recipe_target_total_input.value()
        self.recipe_table.blockSignals(True)
        try:
            mfc4_item.setText(f"{target_total * rh / 100:g}")
            mfc6_item = self.recipe_table.item(row, 9)
            if mfc6_item is not None:
                other_flows = sum(
                    self.recipe_cell_value(row, column) or 0.0
                    for column in range(4, 9)
                )
                mfc6_item.setText(f"{target_total - other_flows:g}")
            self.update_recipe_total_from_setpoints(row)
        finally:
            self.recipe_table.blockSignals(False)

    def update_recipe_rh(self, row):
        target_total = self.recipe_target_total_input.value()
        humid_air = self.recipe_cell_value(row, 7)
        rh_item = self.recipe_table.item(row, 3)
        if rh_item is None:
            rh_item = QTableWidgetItem()
            rh_item.setTextAlignment(Qt.AlignCenter)
            rh_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.recipe_table.setItem(row, 3, rh_item)

        rh_item.setText("--" if humid_air is None or target_total <= 0 else f"{100 * humid_air / target_total:g}")
        style_recipe_rh_item(rh_item)

    def rescale_recipe_for_target_total(self):
        """Preserve every step's gas composition when its common target changes."""
        new_target = self.recipe_target_total_input.value()
        previous_target = getattr(self, "_last_recipe_target_total", new_target)
        if math.isclose(new_target, previous_target, abs_tol=0.001):
            self.validate_recipe_live()
            return

        scale = new_target / previous_target
        self.recipe_table.blockSignals(True)
        try:
            for row in range(self.recipe_table.rowCount()):
                for column in range(4, 10):
                    value = self.recipe_cell_value(row, column)
                    if value is None:
                        continue
                    item = self.recipe_table.item(row, column)
                    item.setText(f"{value * scale:.6g}")
                self.update_recipe_total(self.recipe_table.item(row, 4))
        finally:
            self.recipe_table.blockSignals(False)

        self._last_recipe_target_total = new_target
        self.on_recipe_selection_changed()
        self.validate_recipe_live()

    def validate_recipe_live(self, _changed_item=None):
        if self.validating_recipe:
            return not self.recipe_issues_label.isVisible()

        self.validating_recipe = True
        try:
            return self._validate_recipe_live()
        finally:
            self.validating_recipe = False

    def _validate_recipe_live(self):
        errors = []
        target_total = self.recipe_target_total_input.value()

        for row in range(self.recipe_table.rowCount()):
            for column in range(1, 10):
                self.set_recipe_item_error(row, column, "")

            duration = self.recipe_duration_cell_value(row)
            rh = self.recipe_cell_value(row, 3)
            setpoints = {
                index: self.recipe_cell_value(row, index + 3)
                for index in range(1, 7)
            }
            has_values = (
                rh not in (None, 0.0)
                or any(value not in (None, 0.0) for value in setpoints.values())
            )
            if duration == 0 and not has_values:
                continue

            if rh is None or rh < 0 or rh > 100:
                message = f"Step {row + 1} RH must be a number between 0 and 100%."
                self.set_recipe_item_error(row, 3, message)
                errors.append((row + 1, message))

            if duration is None or duration <= 0:
                message = (
                    f"Step {row + 1} duration must use an explicit unit, for example "
                    "30 s or 2 min, and must be greater than zero."
                )
                self.set_recipe_item_error(row, 2, message)
                errors.append((row + 1, message))

            numeric_setpoints = []
            for index, value in setpoints.items():
                column = index + 3
                capacity = self.manager.mfc_channel_capacity_sccm(index)
                if value is None or value < 0:
                    message = (
                        f"Step {row + 1} MFC {index} must be a non-negative number "
                        "without leading zeros."
                    )
                    self.set_recipe_item_error(row, column, message)
                    errors.append((row + 1, message))
                    continue

                numeric_setpoints.append(value)
                if value > capacity:
                    message = (
                        f"Step {row + 1} MFC {index} exceeds its "
                        f"{capacity:g} mln/min limit."
                    )
                    self.set_recipe_item_error(row, column, message)
                    errors.append((row + 1, message))

            if len(numeric_setpoints) != 6:
                continue

            total_setpoint = sum(numeric_setpoints)
            if not flow_matches_target(total_setpoint, target_total):
                message = (
                    f"Step {row + 1} total must equal the "
                    f"{target_total:g} mln/min target flow."
                )
                self.set_recipe_item_error(row, 1, message)
                errors.append((row + 1, message))

        if errors:
            step_numbers = sorted({step_number for step_number, _message in errors})
            steps_text = ", ".join(str(step_number) for step_number in step_numbers)
            issue_count = len(errors)
            issue_label = "Issue" if issue_count == 1 else "Issues"
            self.recipe_issues_label.setText(f"{issue_count} {issue_label}")
            self.recipe_issues_label.setToolTip("\n".join(message for _step, message in errors))
            self.recipe_issues_label.show()
            noun = "error" if issue_count == 1 else "errors"
            self.set_system_message(
                f"Experiment: {issue_count} validation {noun} in steps {steps_text}. "
                "See highlighted cells.",
                "error",
            )
            return False
        else:
            self.recipe_issues_label.hide()
            self.recipe_issues_label.setToolTip("")
            if self.system_message_label.text().startswith(("Experiment:", "Experiment is invalid.")):
                self.dismiss_system_message()
                if not self.is_experiment_running() and self.status_label.text() == "ERROR":
                    self.status_label.setText("IDLE")
                    self.set_status_badge_state("idle")
            return True

    def recipe_cell_value(self, row, column):
        item = self.recipe_table.item(row, column)
        raw_value = item.text().strip() if item is not None else ""
        numeric_text = self.recipe_numeric_text(raw_value)
        if numeric_text is None:
            return None
        value = float(numeric_text)
        return value if math.isfinite(value) else None

    def recipe_duration_cell_value(self, row):
        item = self.recipe_table.item(row, 2)
        raw_value = item.text().strip() if item is not None else ""
        value = parse_duration_seconds(raw_value)
        return value if value is not None and math.isfinite(value) else None

    @staticmethod
    def recipe_numeric_text(raw_value):
        if not raw_value:
            return None
        numeric_text = raw_value.replace(",", ".").split()[0]
        if not re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d+)?", numeric_text):
            return None
        return numeric_text

    def set_recipe_item_error(self, row, column, message):
        item = self.recipe_table.item(row, column)
        if item is None:
            return
        if message:
            item.setData(Qt.BackgroundRole, QColor("#fee2e2"))
            item.setData(Qt.ForegroundRole, QColor("#b91c1c"))
        elif column == 1:
            style_recipe_total_item(item)
        elif column == 3:
            style_recipe_rh_item(item)
        else:
            item.setData(Qt.BackgroundRole, None)
            item.setData(Qt.ForegroundRole, None)
        item.setToolTip(message)

    def recipe_number(self, row, column, label):
        item = self.recipe_table.item(row, column)
        raw_value = item.text().strip() if item is not None else ""
        numeric_text = self.recipe_numeric_text(raw_value)
        if numeric_text is None:
            raise ValueError(
                f"Step {row + 1} {label} must be a non-negative number without leading zeros."
            )
        value = float(numeric_text)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Step {row + 1} {label} must be a non-negative number without leading zeros.")
        return value

    def recipe_duration_number(self, row):
        item = self.recipe_table.item(row, 2)
        raw_value = item.text().strip() if item is not None else ""
        value = parse_duration_seconds(raw_value)
        if value is None or not math.isfinite(value) or value < 0:
            raise ValueError(
                f"Step {row + 1} duration must use an explicit unit, for example 30 s or 2 min."
            )
        return value

    def recipe_mixture_input(self, minimum, maximum, value):
        input_widget = QDoubleSpinBox()
        input_widget.setObjectName("recipeMixtureInput")
        input_widget.setRange(minimum, maximum)
        input_widget.setDecimals(1)
        input_widget.setSingleStep(0.5)
        input_widget.setValue(value)
        input_widget.setButtonSymbols(QAbstractSpinBox.NoButtons)
        input_widget.setFixedWidth(56)
        input_widget.setFixedHeight(24)
        return input_widget

    def selected_recipe_row(self):
        selected_rows = self.recipe_table.selectionModel().selectedRows()
        return selected_rows[0].row() if selected_rows else -1

    def show_recipe_row_event_tooltip(self, row, column):
        """Show a step's event only when its number is hovered."""
        if column != 0:
            QToolTip.hideText()
            return

        item = self.recipe_table.item(row, column)
        if item is None:
            return

        event = recipe_event(self.recipe_table, row) or "Not set"
        cell_rect = self.recipe_table.visualItemRect(item)
        position = self.recipe_table.viewport().mapToGlobal(cell_rect.bottomLeft())
        QToolTip.showText(position, f"Event: {event}", self.recipe_table)

    def update_recipe_mfc6_remainder(self, *_args):
        if not hasattr(self, "recipe_mfc6_remainder_label"):
            return

        try:
            setpoints = calculate_mixture_setpoints(
                self.recipe_target_total_input.value(),
                self.recipe_rh_input.value(),
                self.recipe_gas_inputs[1].value(),
                self.recipe_gas_inputs[2].value(),
                self.recipe_gas_inputs[3].value(),
                self.recipe_dry_mfc5_input.value(),
            )
            remainder = setpoints[6]
        except ValueError:
            remainder = math.nan
        capacity = self.manager.mfc_channel_capacity_sccm(6)
        valid = -0.01 <= remainder <= capacity + 0.01
        self.recipe_mfc6_remainder_label.setText(f"{max(0.0, remainder):g} mln/min")
        self.recipe_mfc6_remainder_label.setStyleSheet(
            "color: #b91c1c;" if not valid else ""
        )
        message = ""
        if remainder < -0.01:
            message = "Humidity, analyte gases, and MFC5 dry air exceed the target total."
        elif remainder > capacity + 0.01:
            message = f"MFC6 remainder exceeds its {capacity:g} mln/min capacity."
        self.recipe_mfc6_remainder_label.setToolTip(message)
        return remainder

    def apply_recipe_mixture(self):
        if self.is_experiment_running():
            return

        row = self.selected_recipe_row()
        if row < 0:
            self.set_system_message("Select an experiment step before calculating a mixture.", "error")
            return

        try:
            setpoints = calculate_mixture_setpoints(
                self.recipe_target_total_input.value(),
                self.recipe_rh_input.value(),
                self.recipe_gas_inputs[1].value(),
                self.recipe_gas_inputs[2].value(),
                self.recipe_gas_inputs[3].value(),
                self.recipe_dry_mfc5_input.value(),
            )
        except ValueError as exc:
            self.set_system_message(f"Mixture cannot be applied: {exc}", "error")
            return
        self.update_recipe_mfc6_remainder()
        invalid_channels = [
            index
            for index, value in setpoints.items()
            if value < -0.01 or value > self.manager.mfc_channel_capacity_sccm(index) + 0.01
        ]
        if invalid_channels:
            self.set_system_message(
                "Mixture cannot be applied: adjust RH, gas flow, or the MFC5 dry-air split. "
                f"Invalid MFC: {', '.join(str(index) for index in invalid_channels)}.",
                "error",
            )
            return

        self.recipe_table.blockSignals(True)
        try:
            for index, value in setpoints.items():
                item = self.recipe_table.item(row, index + 3)
                if item is not None:
                    item.setText(f"{max(0.0, value):g}")
        finally:
            self.recipe_table.blockSignals(False)

        self.update_recipe_total(self.recipe_table.item(row, 4))
        if not recipe_event(self.recipe_table, row):
            event_parts = []
            if self.recipe_rh_input.value() > 0:
                event_parts.append(f"Set {self.recipe_rh_input.value():g}% RH")
            if any(setpoints[index] > 0 for index in range(1, 4)):
                gases = ", ".join(
                    f"Gas {index} {setpoints[index]:g} mln/min"
                    for index in range(1, 4)
                    if setpoints[index] > 0
                )
                event_parts.append(f"Exposure: {gases}")
            set_recipe_event(
                self.recipe_table,
                row,
                " | ".join(event_parts) or "Baseline: dry air",
            )
        self.on_recipe_selection_changed()
        self.validate_recipe_live()

    def sync_recipe_mixture_from_row(self, row):
        if row < 0:
            self.recipe_duration_input.setText("")
            return

        values = {
            index: self.recipe_cell_value(row, index + 3) or 0.0
            for index in range(1, 7)
        }
        target_total = self.recipe_target_total_input.value()
        rh = 100 * values[4] / target_total if target_total else 0.0
        widgets_and_values = (
            (self.recipe_rh_input, rh),
            (self.recipe_gas_inputs[1], values[1]),
            (self.recipe_gas_inputs[2], values[2]),
            (self.recipe_gas_inputs[3], values[3]),
            (self.recipe_dry_mfc5_input, values[5]),
        )
        for input_widget, value in widgets_and_values:
            input_widget.blockSignals(True)
            input_widget.setValue(value)
            input_widget.blockSignals(False)
        duration_item = self.recipe_table.item(row, 2)
        self.recipe_duration_input.setText(duration_item.text() if duration_item else "")
        self.update_recipe_mfc6_remainder()

    def on_recipe_selection_changed(self):
        row = self.selected_recipe_row()
        if hasattr(self, "recipe_details_step_label"):
            self.recipe_details_step_label.setText(
                f"Selected: step {row + 1}" if row >= 0 else "No step selected"
            )
        self.recipe_event_input.blockSignals(True)
        self.recipe_event_input.setText(recipe_event(self.recipe_table, row))
        self.recipe_event_input.blockSignals(False)
        editable = row >= 0 and not self.is_experiment_running()
        self.recipe_event_input.setEnabled(editable)
        self.recipe_duration_input.setEnabled(editable)
        for input_widget in self.recipe_mixture_inputs:
            input_widget.setEnabled(editable)
        self.recipe_apply_mixture_button.setEnabled(editable)
        self.sync_recipe_mixture_from_row(row)

    def commit_recipe_event(self):
        selected_rows = self.recipe_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        set_recipe_event(
            self.recipe_table,
            selected_rows[0].row(),
            self.recipe_event_input.text(),
        )

    def commit_recipe_duration(self):
        row = self.selected_recipe_row()
        if row < 0 or self.is_experiment_running():
            return

        item = self.recipe_table.item(row, 2)
        if item is None:
            return
        item.setText(self.recipe_duration_input.text().strip())
        self.validate_recipe_live()

    def on_experiment_started(self, filename):
        self.completed_experiment_exists = False
        self.current_file_path = filename
        self.experiment_status_step_index = -1
        self.experiment_step_deadline = None
        self.experiment_status_state = "running"
        self.experiment_last_step_index = -1
        self.start_button.setEnabled(False)
        set_recipe_editable(self.recipe_table, self.recipe_action_buttons, False)
        self.recipe_target_total_input.setEnabled(False)
        self.recipe_event_input.setEnabled(False)
        self.recipe_duration_input.setEnabled(False)
        for input_widget in self.recipe_mixture_inputs:
            input_widget.setEnabled(False)
        self.recipe_apply_mixture_button.setEnabled(False)
        self.format_selector.setEnabled(False)
        self.rate_control.setEnabled(False)
        self.save_location_input.setEnabled(False)
        self.choose_save_location_button.setEnabled(False)
        self.view_full_log_button.setEnabled(False)
        self.update_device_setup_controls_enabled()
        self.status_label.setText("RUNNING")
        self.set_status_badge_state("running")
        self.file_label.setText(filename)
        self.update_save_location_display(filename)
        self.bottom_acquisition_label.setText("Acquisition running")
        self.set_system_message("Data logging in progress.", "running")
        self.update_experiment_status()
        if self.recipe_to_run and not self.manager.start_recipe(self.recipe_to_run):
            self.manager.stop_experiment("Stopped: schedule could not be applied")

    def on_experiment_stopped(self, message):
        stopped_after_error = self.status_label.text() == "ERROR"
        self.completed_experiment_exists = True
        self.recipe_to_run = ()
        self.experiment_status_step_index = -1
        self.experiment_step_deadline = None
        self.experiment_status_timer.stop()
        self.start_button.setEnabled(True)
        set_recipe_editable(self.recipe_table, self.recipe_action_buttons, True)
        self.recipe_target_total_input.setEnabled(True)
        self.on_recipe_selection_changed()
        self.format_selector.setEnabled(True)
        self.rate_control.setEnabled(True)
        self.save_location_input.setEnabled(True)
        self.choose_save_location_button.setEnabled(True)
        self.update_save_location_display(preview=True)
        self.view_full_log_button.setEnabled(bool(self.current_file_path))
        self.update_device_setup_controls_enabled()
        if stopped_after_error:
            self.experiment_status_state = "error"
            self.bottom_acquisition_label.setText("Acquisition error")
            self.update_experiment_status()
            return

        self.experiment_status_state = (
            "completed" if message.startswith("Experiment completed") else "stopped"
        )
        self.status_label.setText("STOPPED")
        self.set_status_badge_state("stopped")
        self.file_label.setText(message)
        self.bottom_acquisition_label.setText("Acquisition stopped")
        self.set_system_message(message, "stopped")
        self.update_experiment_status()

    def on_recipe_step_changed(self, step_index):
        if step_index < 0:
            self.experiment_status_step_index = -1
            self.experiment_step_deadline = None
            self.experiment_status_timer.stop()
            self.recipe_table.clearSelection()
            self.update_experiment_status()
            return

        self.experiment_status_step_index = step_index
        self.experiment_last_step_index = step_index
        if 0 <= step_index < len(self.recipe_to_run):
            duration_seconds = self.recipe_to_run[step_index]["duration_ms"] / 1000
            self.experiment_step_deadline = time.monotonic() + duration_seconds
            self.experiment_status_timer.start()
        self.recipe_table.selectRow(step_index)
        item = self.recipe_table.item(step_index, 0)
        if item is not None:
            self.recipe_table.scrollToItem(item)
        self.update_experiment_status()

    def on_device_error(self, message):
        self.experiment_status_state = "error"
        self.status_label.setText("ERROR")
        self.set_status_badge_state("error")
        self.bottom_acquisition_label.setText("Acquisition error")
        self.set_system_message(message, "error")
        self.update_experiment_status()

    def on_flow_warning(self, message):
        self.bottom_acquisition_label.setText("Acquisition warning")
        self.set_system_message(message, "warning")

    def update_experiment_status(self, *_args):
        if not hasattr(self, "experiment_step_value"):
            return

        total_seconds = self.experiment_schedule_total_seconds()
        self.experiment_total_time_value.setText(
            self.format_experiment_duration(total_seconds) if total_seconds else "--"
        )
        self.experiment_sampling_rate_value.setText(
            f"{self.rate_input.value():g} Hz"
        )
        elapsed_seconds = self.elapsed_duration_seconds()
        self.experiment_elapsed_value.setText(
            self.format_experiment_duration(elapsed_seconds)
        )

        state = self.experiment_status_state
        state_labels = {
            "idle": "IDLE",
            "running": "RUNNING",
            "completed": "COMPLETED",
            "stopped": "STOPPED",
            "error": "ERROR",
        }
        self.experiment_state_badge.setText(state_labels.get(state, "IDLE"))
        self.experiment_state_badge.setProperty("state", state)
        self.experiment_state_badge.style().unpolish(self.experiment_state_badge)
        self.experiment_state_badge.style().polish(self.experiment_state_badge)
        if (
            self.is_experiment_running()
            and 0 <= self.experiment_status_step_index < len(self.recipe_to_run)
        ):
            step = self.recipe_to_run[self.experiment_status_step_index]
            self.experiment_step_value.setText(
                f"Step {self.experiment_status_step_index + 1} of {len(self.recipe_to_run)}"
            )
            event_name = str(step.get("event_name", "")).strip()
            self.experiment_event_value.setText(event_name or "No event description")
            self.experiment_time_caption.setText("Time remaining")
            remaining_seconds = max(
                0,
                math.ceil(self.experiment_step_deadline - time.monotonic())
            ) if self.experiment_step_deadline is not None else 0
            self.experiment_remaining_value.setText(
                self.format_experiment_duration(remaining_seconds)
            )
            progress = round(100 * elapsed_seconds / total_seconds) if total_seconds else 0
            self.experiment_progress.setValue(max(0, min(100, progress)))
        elif state == "completed":
            total_steps = len(self.recipe_to_run) or self.recipe_table.rowCount()
            self.experiment_step_value.setText("Completed")
            self.experiment_event_value.setText(
                f"{total_steps} of {total_steps} steps"
            )
            self.experiment_time_caption.setText("Total duration")
            self.experiment_remaining_value.setText(
                self.format_experiment_duration(total_seconds)
            )
            self.experiment_progress.setValue(100)
        elif state in ("stopped", "error"):
            total_steps = len(self.recipe_to_run) or self.recipe_table.rowCount()
            if self.experiment_last_step_index >= 0:
                self.experiment_step_value.setText(
                    f"Step {self.experiment_last_step_index + 1} of {total_steps}"
                )
            else:
                self.experiment_step_value.setText("Not started")
            self.experiment_event_value.setText(
                "Stopped by user" if state == "stopped" else "Experiment stopped due to an error"
            )
            self.experiment_time_caption.setText("Elapsed time")
            self.experiment_remaining_value.setText(
                self.format_experiment_duration(elapsed_seconds)
            )
            progress = round(100 * elapsed_seconds / total_seconds) if total_seconds else 0
            self.experiment_progress.setValue(max(0, min(100, progress)))
        else:
            total_steps = self.recipe_table.rowCount()
            self.experiment_step_value.setText("Not started")
            self.experiment_event_value.setText(f"0 of {total_steps} steps")
            self.experiment_time_caption.setText("Time remaining")
            self.experiment_remaining_value.setText("--:--:--")
            self.experiment_progress.setValue(0)

    def elapsed_duration_seconds(self):
        parts = self.elapsed_label.text().split(":")
        if len(parts) != 3:
            return 0
        try:
            hours, minutes, seconds = (int(part) for part in parts)
        except ValueError:
            return 0
        return max(0, hours * 3600 + minutes * 60 + seconds)

    def experiment_schedule_total_seconds(self):
        total_seconds = 0
        for row in range(self.recipe_table.rowCount()):
            duration_seconds = self.recipe_duration_cell_value(row)
            if duration_seconds is not None and duration_seconds > 0:
                total_seconds += round(duration_seconds)
        return total_seconds

    @staticmethod
    def format_experiment_duration(total_seconds):
        total_seconds = max(0, int(total_seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def set_system_message(self, message, state):
        self.system_message_bar.show()
        self.update_toolbar_height()
        self.system_message_label.setText(message)
        self.system_message_icon.setText("!" if state in ("error", "warning") else "i")
        for widget in (
            self.system_message_bar,
            self.system_message_icon,
            self.system_message_label,
        ):
            widget.setProperty("state", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def dismiss_system_message(self):
        self.system_message_bar.hide()
        self.update_toolbar_height()

    def set_status_badge_state(self, state):
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

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
        mfc_port = self.mfc_port_selector.currentData()
        mfc_ready = not mfc_real or mfc_port in self.mfc_verified_ports
        self.connect_mfc_button.setEnabled(setup_enabled and mfc_ready)
        self.zero_mfc_setpoints_button.setEnabled(setup_enabled)

    def on_multimeter_mode_changed(self, _text):
        is_real = self.is_real_multimeter_mode()
        self.multimeter_mode_selector.setToolTip(
            "Real multimeter mode" if is_real else "Simulated multimeter mode"
        )
        self.connect_multimeter_button.setText("Connect" if is_real else "Use")
        if is_real:
            self.set_connection_label(
                self.multimeter_status_label,
                "Not connected",
                "disconnected",
            )
            self.set_device_summary(
                self.multimeter_summary_label,
                self.multimeter_status_dot,
                "Not Connected",
                "disconnected",
            )
        else:
            self.set_connection_label(
                self.multimeter_status_label,
                "Connected: Simulated",
                "connected",
            )
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
            self.visa_device_selector.addItem("No device", "")
            self.visa_device_selector.setItemData(
                0, "No VISA instruments found.", Qt.ToolTipRole
            )
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
            self.set_connection_label(
                self.multimeter_status_label,
                "Connected: real multimeter",
                "connected",
            )
            self.set_device_summary(
                self.multimeter_summary_label,
                self.multimeter_status_dot,
                "Connected",
                "connected",
            )
            self.multimeter_status_label.setToolTip(status)
        else:
            self.set_connection_label(
                self.multimeter_status_label,
                "Connected: Simulated",
                "connected",
            )
            self.set_device_summary(
                self.multimeter_summary_label,
                self.multimeter_status_dot,
                "Simulated",
                "connected",
            )
            self.multimeter_status_label.setToolTip(status)

    def on_mfc_mode_changed(self, _text):
        is_real = self.is_real_mfc_mode()
        self.mfc_mode_selector.setToolTip(
            "Real MFC rack mode" if is_real else "Simulated MFC rack mode"
        )
        self.connect_mfc_button.setText("Connect" if is_real else "Use")

        if is_real:
            self.set_connection_label(
                self.mfc_status_label,
                "Not connected",
                "disconnected",
            )
            self.set_device_summary(
                self.mfc_summary_label,
                self.mfc_status_dot,
                "Not Connected",
                "disconnected",
            )
            self.mfc_note_label.setText(
                "Scan verifies all 6 MFC nodes before connection."
            )
            self.bottom_mode_label.setText(
                "Real rack mode: scan and connect the verified six-node rack."
            )
            self.on_device_error(
                "MFC rack is not connected. Scan Rack to verify all 6 nodes."
            )
        else:
            self.set_connection_label(
                self.mfc_status_label,
                "Connected: Simulated",
                "connected",
            )
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
            self.bottom_mode_label.setText("Simulation mode ready")
        self.update_device_setup_controls_enabled()

    def scan_mfc_ports(self):
        if self.is_experiment_running():
            return

        self.mfc_port_selector.clear()
        self.mfc_verified_ports = set()

        try:
            discoveries = self.manager.discover_mfc_racks()
        except Exception as exc:
            self.mfc_port_selector.addItem("Rack scan unavailable", "")
            self.set_connection_label(
                self.mfc_status_label,
                "Rack scan unavailable",
                "disconnected",
            )
            self.on_device_error(f"MFC rack scan failed: {exc}")
            self.update_device_setup_controls_enabled()
            return

        verified = [discovery for discovery in discoveries if discovery.verified]
        if not verified:
            self.mfc_port_selector.addItem("Unverified", "")
            self.mfc_port_selector.setItemData(
                0, "No verified six-node MFC rack found.", Qt.ToolTipRole
            )
            detail = " | ".join(
                f"{discovery.port}: {discovery.message}"
                for discovery in discoveries
            ) or "No COM ports found"
            self.mfc_port_selector.setToolTip(detail)
            self.set_connection_label(
                self.mfc_status_label,
                "No 6/6 MFC rack verified",
                "disconnected",
            )
            self.on_device_error(f"No verified 6-node MFC rack found. {detail}")
            self.update_device_setup_controls_enabled()
            return

        for discovery in verified:
            label = f"{discovery.port} | 6/6 verified"
            self.mfc_port_selector.addItem(label, discovery.port)
            index = self.mfc_port_selector.count() - 1
            self.mfc_port_selector.setItemData(index, discovery.message, Qt.ToolTipRole)
            self.mfc_verified_ports.add(discovery.port)

        self.set_connection_label(
            self.mfc_status_label,
            "Rack verified. Click Connect.",
            "verified",
        )
        self.set_device_summary(
            self.mfc_summary_label,
            self.mfc_status_dot,
            "Rack Verified",
            "verified",
        )
        self.file_label.setText(f"Found {len(verified)} verified MFC rack(s)")
        self.status_label.setText("IDLE")
        self.set_status_badge_state("idle")
        self.set_system_message(
            "MFC rack verified. Click Connect to monitor it.",
            "idle",
        )
        self.update_device_setup_controls_enabled()

    def connect_mfc(self):
        if self.is_experiment_running():
            return

        if self.is_real_mfc_mode():
            port = self.mfc_port_selector.currentData() or self.mfc_port_selector.currentText()
            port = port.strip()
            if not port or port not in self.mfc_verified_ports:
                self.on_device_error("Scan and select a verified 6-node MFC rack before connecting.")
                return

            ok = self.manager.set_mfc_mode("real", port=port)
        else:
            ok = self.manager.set_mfc_mode("simulation")

        if ok:
            self.status_label.setText("IDLE")
            self.set_status_badge_state("idle")
            self.file_label.setText("MFC ready")
            if self.is_real_mfc_mode():
                self.set_system_message(
                    "MFC rack connected. The experiment schedule can now control all six MFCs.",
                    "idle",
                )
        elif self.is_real_mfc_mode():
            self.set_device_summary(
                self.mfc_summary_label,
                self.mfc_status_dot,
                "Not Connected",
                "disconnected",
            )

    def on_mfc_changed(self, mode, status):
        if mode == "real":
            self.set_connection_label(
                self.mfc_status_label,
                self.compact_mfc_status(status),
                "connected",
            )
            self.set_device_summary(
                self.mfc_summary_label,
                self.mfc_status_dot,
                "Rack Connected",
                "connected",
            )
            self.mfc_status_label.setToolTip(status)
        else:
            if self.is_real_mfc_mode():
                self.set_connection_label(
                    self.mfc_status_label,
                    "Not connected",
                    "disconnected",
                )
                self.set_device_summary(
                    self.mfc_summary_label,
                    self.mfc_status_dot,
                    "Not Connected",
                    "disconnected",
                )
            else:
                self.set_connection_label(
                    self.mfc_status_label,
                    "Connected: Simulated",
                    "connected",
                )
                self.set_device_summary(
                    self.mfc_summary_label,
                    self.mfc_status_dot,
                    "Simulated",
                    "connected",
                )
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
    def set_connection_label(label, text, state):
        label.setText(text)
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)

    @staticmethod
    def compact_mfc_status(status):
        if "MFC RACK" in status:
            parts = [part.strip() for part in status.split("|")]
            port = parts[1] if len(parts) > 1 else ""
            verification = parts[2] if len(parts) > 2 else ""
            return f"Rack connected: {port}\n{verification} | manual test available".strip()

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

        first_line = "Real MFC"
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

    def refresh_state_label(self, state):
        self.update_mfc_rack_monitor(state)
        self.update_experiment_status()

    def update_mfc_rack_monitor(self, state):
        if not hasattr(self, "mfc_channel_monitor"):
            return

        channels = {
            channel.index: channel
            for channel in getattr(state, "mfc_channels", ())
        }
        verified = len(channels) == 6
        if verified and self.manager.mfc_mode == "real":
            port = state.mfc_port or self.manager.mfc_port
            self.mfc_rack_status_label.setText(
                f"Real rack | {port} | {self.manager.settings.mfc_baudrate} | 6/6 verified"
            )
        elif verified:
            self.mfc_rack_status_label.setText("Simulation | 6 channels")
        elif self.manager.mfc_mode == "real":
            self.mfc_rack_status_label.setText("Real rack | not connected")
        else:
            self.mfc_rack_status_label.setText("Simulation | rack not connected")

        if channels:
            total_capacity = sum(channel.capacity_sccm for channel in channels.values())
            total_actual = sum(channel.actual_sccm for channel in channels.values())
            total_setpoint = sum(channel.setpoint_sccm for channel in channels.values())
            self.max_total_flow_label.setText(f"{total_capacity:g} mln/min")
            self.total_actual_label.setText(f"{total_actual:.2f} mln/min")
            self.total_setpoint_label.setText(f"{total_setpoint:.2f} mln/min")
        else:
            self.max_total_flow_label.setText("--")
            self.total_actual_label.setText("--")
            self.total_setpoint_label.setText("--")

        for index, widgets in self.mfc_channel_monitor.items():
            channel = channels.get(index)
            detail_label = widgets["detail"]
            if channel is None:
                widgets["actual"].setText("--")
                widgets["setpoint"].setText("--")
                detail_label.setVisible(False)
                widgets["row"].setToolTip("")
            else:
                unit = channel.capacity_unit or "mln/min"
                widgets["actual"].setText(f"{channel.actual_sccm:.2f}")
                widgets["setpoint"].setText(f"{channel.setpoint_sccm:.2f}")
                status = (channel.status or "").upper()
                health_state = (
                    "alarm" if status not in {"", "OK", "SIMULATED"}
                    else "simulated" if status == "SIMULATED"
                    else "ok"
                )
                if health_state == "alarm":
                    detail_label.setText(status.title())
                    detail_label.setProperty("state", "alarm")
                    detail_label.setVisible(True)
                elif channel.serial:
                    detail_label.setText(
                        f"{channel.serial} | limit {channel.capacity_sccm:g} {unit}"
                    )
                    detail_label.setProperty("state", "serial")
                    detail_label.setVisible(True)
                else:
                    detail_label.setVisible(False)
                header_item = self.recipe_table.horizontalHeaderItem(index + 3)
                if header_item is not None:
                    header_item.setToolTip(
                        f"MFC {index} limit: {channel.capacity_sccm:g} {unit}"
                    )
                widgets["row"].setToolTip(
                    f"Address: {channel.address}\n"
                    f"Serial: {channel.serial}\n"
                    f"Fluid: {channel.fluid_name}\n"
                    f"Capacity: {channel.capacity_sccm:g} {unit}\n"
                    f"Temperature: {channel.temperature_c:.2f} C\n"
                    f"Alarm Info: {channel.alarm_info or '0'}"
                )
            detail_label.style().unpolish(detail_label)
            detail_label.style().polish(detail_label)

    def on_data_acquired(self, data, event):
        self.time_data.append(data["elapsed_s"])
        self.resistance_data.append(data["resistance_ohm"])

        self.resistance_curve.setData(self.time_data, self.resistance_data)
        for index, curve in self.flow_curves.items():
            value = data.get(f"mfc{index}_actual_mln_min", math.nan)
            self.mfc_flow_data[index].append(value)
            curve.setData(self.time_data, self.mfc_flow_data[index])
        if event:
            self.add_event_marker(data["elapsed_s"], event)
        self.update_plot_ranges()

        self.resistance_value_label.setText(
            self.format_number(data["resistance_ohm"], suffix=" Ohm", precision=2)
        )
        total_actual = sum(
            data.get(f"mfc{index}_actual_mln_min", 0.0) for index in range(1, 7)
        )
        total_setpoint = sum(
            data.get(f"mfc{index}_setpoint_mln_min", 0.0) for index in range(1, 7)
        )
        self.total_actual_label.setText(f"{total_actual:.2f} mln/min")
        self.total_setpoint_label.setText(f"{total_setpoint:.2f} mln/min")

        self.add_log_preview_row(data, event)

    def update_plot_ranges(self):
        resistance_values = self.finite_values(self.resistance_data)
        flow_values = self.finite_values([
            value
            for values in self.mfc_flow_data.values()
            for value in values
        ])

        if self.time_data:
            self.resistance_plot.setXRange(self.time_data[0], self.time_data[-1], padding=0.02)
            self.flow_plot.setXRange(self.time_data[0], self.time_data[-1], padding=0.02)

        if resistance_values:
            low = min(resistance_values)
            high = max(resistance_values)
            padding = max((high - low) * 0.12, 50)
            self.resistance_plot.setYRange(low - padding, high + padding, padding=0)

        if flow_values:
            low = min(flow_values)
            high = max(flow_values)
            padding = max((high - low) * 0.15, 0.5)
            self.flow_plot.setYRange(max(0, low - padding), high + padding, padding=0)

    def set_active_plot(self, mode):
        showing_flow = mode == "flow"
        self.plot_stack.setCurrentIndex(1 if showing_flow else 0)
        self.resistance_plot_button.setChecked(not showing_flow)
        self.flow_plot_button.setChecked(showing_flow)
        self.flow_legend.setVisible(showing_flow)

        for button, active in (
            (self.resistance_plot_button, not showing_flow),
            (self.flow_plot_button, showing_flow),
        ):
            button.setProperty("active", "true" if active else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def add_event_marker(self, elapsed_s, event):
        color = self.event_color(event)
        pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)

        resistance_line = pg.InfiniteLine(pos=elapsed_s, angle=90, movable=False, pen=pen)
        flow_line = pg.InfiniteLine(pos=elapsed_s, angle=90, movable=False, pen=pen)
        event_label = self.short_event_label(event)
        resistance_line.setToolTip(event_label)
        flow_line.setToolTip(event_label)
        self.resistance_plot.addItem(resistance_line)
        self.flow_plot.addItem(flow_line)

        self.event_markers.append({
            "resistance_line": resistance_line,
            "flow_line": flow_line,
        })
        self.event_summary_dot.setStyleSheet(
            f"background: {color}; border: none; border-radius: 3px;"
        )
        self.event_summary_label.setText(event_label.replace("\n", " | "))
        self.event_summary.show()

    def clear_event_markers(self):
        for marker in self.event_markers:
            self.resistance_plot.removeItem(marker["resistance_line"])
            self.flow_plot.removeItem(marker["flow_line"])
        self.event_markers.clear()
        self.event_summary.hide()

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
        step_text = "--"
        if self.recipe_to_run:
            step_index = self.experiment_status_step_index
            if not 0 <= step_index < len(self.recipe_to_run):
                step_index = self.experiment_last_step_index
            if 0 <= step_index < len(self.recipe_to_run):
                step_text = f"{step_index + 1}/{len(self.recipe_to_run)}"

        self.log_table.append_record([
            data["timestamp"],
            f"{data['elapsed_s']:.1f}",
            step_text,
            self.format_number(data["resistance_ohm"], precision=2),
            f"{sum(data.get(f'mfc{index}_setpoint_mln_min', 0.0) for index in range(1, 7)):.2f}",
            f"{sum(data.get(f'mfc{index}_actual_mln_min', 0.0) for index in range(1, 7)):.2f}",
            data.get("event") or event or "--",
        ])

    def closeEvent(self, event):
        self.manager.close()
        event.accept()
    def apply_styles(self):
        chevron_down_path = (self.assets_dir / "chevron_down.svg").as_posix()
        self.setStyleSheet(application_style(chevron_down_path))
