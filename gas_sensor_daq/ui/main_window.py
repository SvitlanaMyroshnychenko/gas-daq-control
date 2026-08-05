import math
import re
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap, QPolygon, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
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
    QStackedWidget,
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
from gas_sensor_daq.core.experiment_design import (
    DEFAULT_TARGET_TOTAL_FLOW,
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
        self.adjusting_log_columns = False
        self.log_preview_expanded = False
        self.recipe_to_run = ()
        self.validating_recipe = False
        self.data_directory = self.manager.data_directory
        self.current_file_path = ""
        self.experiment_status_step_index = -1
        self.experiment_step_deadline = None
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
        self.rate_input.setFixedSize(38, 32)
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
            button.setFixedSize(38, 32)
            button.setIconSize(QSize(14, 14))
            button.clicked.connect(callback)
        self.rate_minus_button.setToolTip("Decrease sampling rate")
        self.rate_plus_button.setToolTip("Increase sampling rate")

        self.rate_unit_label = QLabel("Hz")
        self.rate_unit_label.setObjectName("rateUnitBox")
        self.rate_unit_label.setFixedSize(26, 32)
        self.rate_unit_label.setAlignment(Qt.AlignCenter)
        self.rate_control = QWidget()
        self.rate_control.setFixedHeight(32)
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
        self.format_selector.setFixedWidth(96)
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

        self.start_button = QPushButton("  Start")
        self.stop_button = QPushButton("  Stop")
        self.start_button.setFixedSize(96, 32)
        self.stop_button.setFixedSize(96, 32)
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
        self.max_total_flow_label = self.metric_value("--")
        self.nh3_actual_label = self.metric_value("--")
        self.air_actual_label = self.metric_value("--")
        self.resistance_value_label.setProperty("metricColor", "blue")
        self.max_total_flow_label.setProperty("metricColor", "slate")
        self.nh3_actual_label.setProperty("metricColor", "purple")
        self.air_actual_label.setProperty("metricColor", "teal")
        for value_label in (
            self.resistance_value_label,
            self.max_total_flow_label,
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
            "Ω",
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

        self.log_table = QTableWidget(0, 6)
        self.log_table.setHorizontalHeaderLabels([
            "Time",
            "Elapsed (s)",
            "Resistance (Ohm)",
            "Actual Flow\n(mln/min)",
            "Setpoint Flow\n(mln/min)",
            "Event",
        ])
        self.configure_log_table()
        self.recipe_table = QTableWidget(5, 10)
        self.recipe_table.setObjectName("recipeTable")
        self.recipe_table.setHorizontalHeaderLabels([
            "Step",
            "Step Total\n(mln/min)",
            "Duration\n(s / min)",
            "RH\n(%)",
            "MFC 1",
            "MFC 2",
            "MFC 3",
            "MFC 4",
            "MFC 5",
            "MFC 6",
        ])
        configure_recipe_table(self.recipe_table)
        self.recipe_table.setToolTip(
            "All MFC flow values in this schedule are mln/min."
        )
        # Keep the schedule compact at five visible steps; additional steps scroll.
        self.recipe_table.setFixedHeight(174)
        self.recipe_table.itemChanged.connect(self.update_recipe_total)
        self.recipe_table.itemChanged.connect(self.validate_recipe_live)
        self.recipe_table.itemChanged.connect(self.update_experiment_status)

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
        self.recipe_target_total_label = QLabel("Target total")
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
        body_layout.addWidget(self.scroll_panel(self.create_left_panel()), 0)
        body_layout.addWidget(self.scroll_panel(self.create_center_panel()), 1)
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
        self.manager.recipe_step_changed.connect(self.on_recipe_step_changed)
        self.manager.flow_warning.connect(self.on_flow_warning)

    def create_toolbar(self):
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        self.toolbar = toolbar

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        controls = QFrame()
        controls.setObjectName("toolbarControls")
        self.toolbar_controls = controls
        self.toolbar_status_group = self.toolbar_inline_group("Status", self.status_label, 141)
        self.toolbar_elapsed_group = self.toolbar_inline_group("Elapsed", self.elapsed_label, 125)
        self.toolbar_rate_group = self.toolbar_inline_group("Rate", self.rate_control, 199)
        save_location = self.save_location_control()
        save_location.setFixedWidth(220)
        self.toolbar_save_group = self.toolbar_inline_group("Save to", save_location, 273)
        self.toolbar_format_group = self.toolbar_inline_group("Save as", self.format_selector, 149)
        self.toolbar_run_group = self.toolbar_cluster(
            self.toolbar_status_group,
            self.toolbar_elapsed_group,
            self.toolbar_rate_group,
        )
        self.toolbar_storage_group = self.toolbar_cluster(self.toolbar_save_group)
        self.toolbar_actions_group = self.toolbar_cluster(
            self.toolbar_format_group,
            self.start_button,
            self.stop_button,
        )
        self.toolbar_rows = [self.toolbar_control_row() for _ in range(3)]
        self.toolbar_controls_layout = QGridLayout()
        self.toolbar_controls_layout.setContentsMargins(12, 10, 12, 10)
        self.toolbar_controls_layout.setHorizontalSpacing(6)
        self.toolbar_controls_layout.setVerticalSpacing(8)
        controls.setLayout(self.toolbar_controls_layout)

        layout.addWidget(controls)
        layout.addWidget(self.toolbar_message_bar())

        toolbar.setLayout(layout)
        self.reflow_toolbar_controls(self.width())
        return toolbar

    def toolbar_inline_group(self, title, content, width, expanding=False):
        group = QWidget()
        group.setObjectName("toolbarInlineGroup")
        if expanding:
            group.setMinimumSize(width, 32)
            group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        else:
            group.setFixedSize(width, 32)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel(title)
        label.setObjectName("toolbarInlineLabel")
        label.setFixedWidth(48)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label)
        layout.addWidget(content, 1 if expanding else 0)
        group.setLayout(layout)
        return group

    @staticmethod
    def toolbar_cluster(*widgets):
        cluster = QWidget()
        cluster.setObjectName("toolbarCluster")
        cluster.setFixedHeight(32)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for widget in widgets:
            layout.addWidget(widget)
        cluster.setLayout(layout)
        return cluster

    def toolbar_separator(self):
        divider = QFrame()
        divider.setObjectName("toolbarDivider")
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedSize(1, 32)
        return divider

    def toolbar_control_row(self):
        row = QWidget()
        row.setObjectName("toolbarControlRow")
        row.setFixedHeight(32)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        row.setLayout(layout)
        return row

    def populate_toolbar_row(self, row, leading_widgets, trailing_widgets=()):
        layout = row.layout()
        while layout.count():
            layout.takeAt(0)

        for widget in leading_widgets:
            layout.addWidget(widget)
        if trailing_widgets:
            layout.addStretch(1)
            for widget in trailing_widgets:
                layout.addWidget(widget)
        else:
            layout.addStretch(1)
        row.show()

    def reflow_toolbar_controls(self, width):
        if not hasattr(self, "toolbar_controls_layout"):
            return

        layout = self.toolbar_controls_layout
        while layout.count():
            layout.takeAt(0)

        for row in self.toolbar_rows:
            row.hide()

        self.toolbar_controls.setFixedHeight(56)
        self.populate_toolbar_row(
            self.toolbar_rows[0],
            (self.toolbar_run_group,),
            (
                self.toolbar_storage_group,
                self.toolbar_actions_group,
            ),
        )
        layout.addWidget(self.toolbar_rows[0], 0, 0, 1, 10)

        self.update_toolbar_height()

    def update_toolbar_height(self):
        if not hasattr(self, "toolbar_controls"):
            return
        message_height = 0
        if hasattr(self, "system_message_bar") and not self.system_message_bar.isHidden():
            message_height = self.system_message_bar.height() + 6
        self.toolbar.setFixedHeight(self.toolbar_controls.height() + message_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow_toolbar_controls(event.size().width())

    def toolbar_value_section(self, title, value_widget, width, separated=False):
        section = QFrame()
        section.setObjectName("toolbarSection")
        section.setProperty("separated", "true" if separated else "false")
        section.setFixedSize(width, 54)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(title)
        label.setObjectName("caption")
        layout.addWidget(label)
        layout.addWidget(value_widget)
        section.setLayout(layout)
        return section

    def toolbar_button_section(self, button, width):
        section = QFrame()
        section.setObjectName("toolbarButtonSection")
        section.setFixedSize(width, 54)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(button)
        section.setLayout(layout)
        return section

    def save_location_control(self):
        control = QWidget()
        control.setFixedHeight(32)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.save_location_input, 1)
        layout.addWidget(self.choose_save_location_button)
        control.setLayout(layout)
        return control

    def toolbar_divider(self):
        divider = QFrame()
        divider.setObjectName("toolbarDivider")
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedSize(5, 38)
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
        block.setFixedWidth(135)
        block.setFixedHeight(60)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title_label = QLabel("Status")
        title_label.setObjectName("caption")
        title_label.setAlignment(Qt.AlignVCenter)
        layout.addWidget(title_label)
        layout.addWidget(self.status_label)

        block.setLayout(layout)
        return block

    def toolbar_file_block(self):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setFixedWidth(120)
        block.setFixedHeight(60)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(1)
        title_label = QLabel("File")
        title_label.setObjectName("caption")
        layout.addWidget(title_label)
        layout.addWidget(self.file_label)
        block.setLayout(layout)
        return block

    def toolbar_block(self, title, value_label, detail_label=None):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setFixedWidth(100)
        block.setFixedHeight(60)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 6, 0, 6)
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
        block.setFixedHeight(60)
        block.setFixedWidth(96)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(1)

        label = QLabel("Save as")
        label.setObjectName("caption")
        layout.addWidget(label)
        layout.addWidget(self.format_selector)

        block.setLayout(layout)
        return block

    def toolbar_rate_block(self):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setFixedHeight(60)
        block.setFixedWidth(164)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(1)
        label = QLabel("Sampling Rate")
        label.setObjectName("caption")

        self.rate_control = QWidget()
        rate_layout = QHBoxLayout()
        rate_layout.setContentsMargins(0, 0, 0, 0)
        rate_layout.setSpacing(2)
        rate_layout.addWidget(self.rate_minus_button)
        rate_layout.addWidget(self.rate_input)
        rate_layout.addWidget(self.rate_unit_label)
        rate_layout.addWidget(self.rate_plus_button)
        rate_layout.addStretch()
        self.rate_control.setLayout(rate_layout)

        layout.addWidget(label)
        layout.addWidget(self.rate_control)
        block.setLayout(layout)
        return block

    def toolbar_location_block(self):
        block = QFrame()
        block.setObjectName("toolbarBlock")
        block.setFixedWidth(300)
        block.setFixedHeight(60)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(1)
        label = QLabel("Save Location")
        label.setObjectName("caption")
        location_row = QHBoxLayout()
        location_row.setContentsMargins(0, 0, 0, 0)
        location_row.setSpacing(5)
        location_row.addWidget(self.save_location_input, 1)
        location_row.addWidget(self.choose_save_location_button)
        layout.addWidget(label)
        layout.addLayout(location_row)
        block.setLayout(layout)
        return block

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
        dismiss_button = QPushButton("×")
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
        panel.setMinimumWidth(310)
        panel.setMaximumWidth(335)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        readings_layout = QVBoxLayout()
        readings_layout.setContentsMargins(0, 0, 0, 0)
        readings_layout.setSpacing(0)
        readings_layout.addWidget(self.reading_row("Resistance", self.resistance_value_label, "#2563eb"))
        readings_layout.addWidget(self.reading_row("Rack capacity", self.max_total_flow_label, "#64748b"))
        readings_layout.addWidget(self.reading_row("Current setpoint flow", self.air_actual_label, "#0f9f9a"))
        readings_layout.addWidget(self.reading_row("Current actual flow", self.nh3_actual_label, "#7c3aed"))
        readings_card = self.compact_section_card(
            "Current Readings",
            readings_layout,
        )

        layout.addWidget(readings_card)
        layout.addWidget(self.create_mfc_rack_monitor())
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

        plot_layout = QVBoxLayout()
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(10)

        plot_controls = QHBoxLayout()
        plot_controls.setContentsMargins(0, 0, 0, 0)
        plot_controls.setSpacing(0)
        self.resistance_plot_button = QPushButton("Resistance")
        self.flow_plot_button = QPushButton("MFC Flow")
        self.resistance_plot_button.setProperty("position", "start")
        self.flow_plot_button.setProperty("position", "end")
        for button in (self.resistance_plot_button, self.flow_plot_button):
            button.setObjectName("plotModeButton")
            button.setCheckable(True)
            button.setFixedHeight(28)
        self.resistance_plot_button.setChecked(True)
        self.resistance_plot_button.clicked.connect(
            lambda: self.set_active_plot("resistance")
        )
        self.flow_plot_button.clicked.connect(lambda: self.set_active_plot("flow"))
        plot_controls.addWidget(self.resistance_plot_button)
        plot_controls.addWidget(self.flow_plot_button)
        plot_controls.addStretch()
        plot_layout.addLayout(plot_controls)

        self.flow_legend = QWidget()
        self.flow_legend.setObjectName("flowLegend")
        legend_layout = QHBoxLayout()
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setSpacing(14)
        for index, color in self.mfc_channel_colors.items():
            entry = QWidget()
            entry_layout = QHBoxLayout()
            entry_layout.setContentsMargins(0, 0, 0, 0)
            entry_layout.setSpacing(5)

            marker = QFrame()
            marker.setFixedSize(8, 8)
            marker.setStyleSheet(f"background: {color}; border: none; border-radius: 4px;")
            label = QLabel(f"MFC {index}")
            label.setObjectName("flowLegendItem")

            entry_layout.addWidget(marker)
            entry_layout.addWidget(label)
            entry.setLayout(entry_layout)
            legend_layout.addWidget(entry)
        legend_layout.addStretch()
        self.flow_legend.setLayout(legend_layout)
        self.flow_legend.hide()
        plot_layout.addWidget(self.flow_legend)

        self.event_summary = QFrame()
        self.event_summary.setObjectName("eventSummary")
        event_summary_layout = QHBoxLayout()
        event_summary_layout.setContentsMargins(8, 4, 8, 4)
        event_summary_layout.setSpacing(7)
        self.event_summary_dot = QFrame()
        self.event_summary_dot.setFixedSize(7, 7)
        self.event_summary_dot.setStyleSheet("background: #64748b; border: none; border-radius: 3px;")
        self.event_summary_label = QLabel()
        self.event_summary_label.setObjectName("eventSummaryLabel")
        event_summary_layout.addWidget(self.event_summary_dot)
        event_summary_layout.addWidget(self.event_summary_label, 1)
        self.event_summary.setLayout(event_summary_layout)
        self.event_summary.hide()
        plot_layout.addWidget(self.event_summary)
        plot_layout.addSpacing(6)

        self.plot_stack = QStackedWidget()
        self.plot_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_stack.layout().setContentsMargins(0, 0, 0, 0)
        self.plot_stack.addWidget(self.resistance_plot)
        self.plot_stack.addWidget(self.flow_plot)
        plot_layout.addWidget(self.plot_stack, 1)
        plot_card = self.graph_card("Live measurement", "#3b82f6", plot_layout)
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

        recipe_layout = QVBoxLayout()
        recipe_layout.setContentsMargins(0, 3, 0, 0)
        recipe_layout.setSpacing(8)
        recipe_layout.addWidget(self.recipe_table)

        recipe_actions = QWidget()
        recipe_actions_layout = QVBoxLayout()
        recipe_actions_layout.setContentsMargins(0, 0, 0, 0)
        recipe_actions_layout.setSpacing(5)
        recipe_event_actions = QHBoxLayout()
        recipe_event_actions.setContentsMargins(0, 0, 0, 0)
        recipe_event_actions.setSpacing(5)
        recipe_event_actions.addWidget(QLabel("Event"))
        recipe_event_actions.addWidget(self.recipe_event_input)
        recipe_event_actions.addStretch()
        recipe_actions_layout.addLayout(recipe_event_actions)

        recipe_mixture_band = QFrame()
        recipe_mixture_band.setObjectName("recipeMixtureBand")
        recipe_mixture_layout = QVBoxLayout()
        recipe_mixture_layout.setContentsMargins(0, 8, 0, 8)
        recipe_mixture_layout.setSpacing(4)
        mixture_primary_row = QHBoxLayout()
        mixture_primary_row.setContentsMargins(0, 0, 0, 0)
        mixture_primary_row.setSpacing(6)
        mixture_title = QLabel("Selected-step mixture")
        mixture_title.setObjectName("recipeMixtureTitle")
        mixture_primary_row.addWidget(mixture_title)
        for label, widget in (
            ("RH", self.recipe_rh_input),
            ("Gas 1", self.recipe_gas_inputs[1]),
            ("Gas 2", self.recipe_gas_inputs[2]),
            ("Gas 3", self.recipe_gas_inputs[3]),
        ):
            mixture_primary_row.addWidget(QLabel(label))
            mixture_primary_row.addWidget(widget)
        mixture_primary_row.addStretch()

        mixture_dry_air_row = QHBoxLayout()
        mixture_dry_air_row.setContentsMargins(0, 0, 0, 0)
        mixture_dry_air_row.setSpacing(6)
        dry_air_title = QLabel("Dry-air allocation")
        dry_air_title.setObjectName("recipeMixtureTitle")
        mixture_dry_air_row.addWidget(dry_air_title)
        mixture_dry_air_row.addWidget(QLabel("MFC5 dry"))
        mixture_dry_air_row.addWidget(self.recipe_dry_mfc5_input)
        mixture_dry_air_row.addWidget(QLabel("MFC6 remainder"))
        mixture_dry_air_row.addWidget(self.recipe_mfc6_remainder_label)
        mixture_dry_air_row.addStretch()
        mixture_dry_air_row.addWidget(self.recipe_apply_mixture_button)
        recipe_mixture_layout.addLayout(mixture_primary_row)
        recipe_mixture_layout.addLayout(mixture_dry_air_row)
        recipe_mixture_band.setLayout(recipe_mixture_layout)
        recipe_actions_layout.addWidget(recipe_mixture_band)
        recipe_actions.setLayout(recipe_actions_layout)

        self.recipe_details_title = QLabel("Step details")
        self.recipe_details_title.setObjectName("recipeDetailsTitle")
        self.recipe_details_step_label = QLabel("Selected: step 1")
        self.recipe_details_step_label.setObjectName("recipeDetailsStep")
        self.recipe_details_chevron = QPushButton()
        self.recipe_details_chevron.setObjectName("logChevron")
        self.recipe_details_chevron.setFixedSize(24, 22)
        self.recipe_details_chevron.setCheckable(True)
        self.recipe_details_chevron.setToolTip("Show or hide selected-step details")
        self.recipe_details_chevron.clicked.connect(self.toggle_recipe_details)
        recipe_details_header = QWidget()
        recipe_details_header.setObjectName("recipeDetailsHeader")
        recipe_details_header_layout = QHBoxLayout()
        recipe_details_header_layout.setContentsMargins(0, 2, 0, 0)
        recipe_details_header_layout.setSpacing(5)
        recipe_details_header_layout.addWidget(self.recipe_details_title)
        recipe_details_header_layout.addWidget(self.recipe_details_step_label)
        recipe_details_header_layout.addStretch()
        for button in self.recipe_action_buttons:
            recipe_details_header_layout.addWidget(button)
        recipe_details_header_layout.addWidget(self.recipe_details_chevron)
        recipe_details_header.setLayout(recipe_details_header_layout)

        self.recipe_details_content = recipe_actions
        recipe_layout.addWidget(recipe_details_header)
        recipe_layout.addWidget(self.recipe_details_content)

        recipe_target_control = QWidget()
        recipe_target_control_layout = QHBoxLayout()
        recipe_target_control_layout.setContentsMargins(0, 0, 0, 0)
        recipe_target_control_layout.setSpacing(4)
        recipe_target_control_layout.addWidget(self.recipe_target_total_input)
        recipe_target_control_layout.addWidget(self.recipe_target_total_unit_label)
        recipe_target_control.setLayout(recipe_target_control_layout)

        recipe_header_controls = QWidget()
        recipe_header_controls_layout = QHBoxLayout()
        recipe_header_controls_layout.setContentsMargins(0, 0, 0, 0)
        recipe_header_controls_layout.setSpacing(5)
        recipe_header_controls_layout.addWidget(self.recipe_issues_label)
        recipe_header_controls_layout.addSpacing(16)
        recipe_header_controls_layout.addWidget(self.recipe_target_total_label)
        recipe_header_controls_layout.addWidget(recipe_target_control)
        recipe_header_controls.setLayout(recipe_header_controls_layout)

        self.recipe_chevron = QPushButton()
        self.recipe_chevron.setObjectName("logChevron")
        self.recipe_chevron.setFixedSize(24, 22)
        self.recipe_chevron.setCheckable(True)
        self.recipe_chevron.setToolTip("Show or hide experiment schedule")
        self.recipe_chevron.clicked.connect(self.toggle_recipe_schedule)
        recipe_header_widget = QWidget()
        recipe_header_widget_layout = QHBoxLayout()
        recipe_header_widget_layout.setContentsMargins(0, 0, 0, 0)
        recipe_header_widget_layout.setSpacing(5)
        recipe_header_widget_layout.addWidget(recipe_header_controls)
        recipe_header_widget_layout.addWidget(self.recipe_chevron)
        recipe_header_widget.setLayout(recipe_header_widget_layout)

        recipe_card = self.section_card(
            "Experiment Schedule",
            None,
            recipe_layout,
            expanding=False,
            header_widget=recipe_header_widget,
        )
        # Let the card account for both the five-row table and its bottom
        # action row. A fixed height clips them at non-100% display scaling.
        self.recipe_card_widget = recipe_card
        self.recipe_content_frame = recipe_card.content_frame
        self.recipe_header_controls = recipe_header_controls
        recipe_card.setMinimumHeight(352)
        self.recipe_details_expanded = True
        self.set_recipe_schedule_expanded(True)
        self.set_recipe_details_expanded(False)

        layout.addWidget(plot_card, 4)
        layout.addWidget(recipe_card)
        layout.addWidget(log_card, 2)
        panel.setLayout(layout)
        return panel

    def create_right_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(310)
        panel.setMaximumWidth(320)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

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

        layout.addWidget(devices_card, 0, Qt.AlignTop)
        layout.addWidget(self.create_manual_mfc_test_card(), 0, Qt.AlignTop)
        layout.addWidget(self.create_experiment_status_card(), 0, Qt.AlignTop)
        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def create_experiment_status_card(self):
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        self.experiment_step_value = self.experiment_status_value("--")
        self.experiment_remaining_value = self.experiment_status_value(
            "--", "experimentTimeValue"
        )
        self.experiment_total_time_value = self.experiment_status_value(
            "--", "experimentTimeValue"
        )

        content.addWidget(self.state_row("Step", self.experiment_step_value))
        content.addWidget(self.state_row("Remaining", self.experiment_remaining_value))
        content.addWidget(self.state_row("Total time", self.experiment_total_time_value))

        return self.compact_section_card(
            "Experiment Status", content, title_accent="#2563eb"
        )

    def create_manual_mfc_test_card(self):
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(6)

        self.manual_mfc_channel_selector = QComboBox()
        for index in range(1, 7):
            self.manual_mfc_channel_selector.addItem(f"MFC {index}", index)
        self.manual_mfc_channel_selector.setObjectName("manualMfcChannel")
        self.manual_mfc_channel_selector.currentIndexChanged.connect(
            self.update_manual_mfc_test_limit
        )

        self.manual_mfc_flow_input = QDoubleSpinBox()
        self.manual_mfc_flow_input.setObjectName("manualMfcFlow")
        self.manual_mfc_flow_input.setDecimals(2)
        self.manual_mfc_flow_input.setSingleStep(0.1)
        self.manual_mfc_flow_input.setValue(1.0)

        self.manual_mfc_apply_button = QPushButton("Apply test flow")
        self.manual_mfc_apply_button.setObjectName("manualMfcApplyButton")
        self.manual_mfc_apply_button.clicked.connect(self.apply_manual_mfc_test)
        self.manual_mfc_zero_button = QPushButton("Zero all MFCs")
        self.manual_mfc_zero_button.setObjectName("manualMfcZeroButton")
        self.manual_mfc_zero_button.clicked.connect(self.confirm_zero_all_mfcs)

        channel_row = QHBoxLayout()
        channel_row.setContentsMargins(0, 0, 0, 0)
        channel_row.setSpacing(6)
        channel_label = QLabel("Channel")
        channel_label.setObjectName("manualMfcLabel")
        channel_row.addWidget(channel_label)
        channel_row.addWidget(self.manual_mfc_channel_selector, 1)

        flow_row = QHBoxLayout()
        flow_row.setContentsMargins(0, 0, 0, 0)
        flow_row.setSpacing(6)
        flow_label = QLabel("Test flow")
        flow_label.setObjectName("manualMfcLabel")
        flow_unit = QLabel("mln/min")
        flow_unit.setObjectName("manualMfcUnit")
        flow_row.addWidget(flow_label)
        flow_row.addWidget(self.manual_mfc_flow_input, 1)
        flow_row.addWidget(flow_unit)

        self.manual_mfc_test_state = QLabel(
            "Connect a verified real rack to enable manual testing."
        )
        self.manual_mfc_test_state.setObjectName("manualMfcHint")
        self.manual_mfc_test_state.setWordWrap(True)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 2, 0, 0)
        actions.setSpacing(6)
        actions.addWidget(self.manual_mfc_apply_button, 1)
        actions.addWidget(self.manual_mfc_zero_button, 1)

        content.addLayout(channel_row)
        content.addLayout(flow_row)
        content.addWidget(self.manual_mfc_test_state)
        content.addLayout(actions)

        card = self.compact_section_card(
            "Manual MFC Test", content, title_accent="#d97706"
        )
        card.setObjectName("manualMfcTestCard")
        self.manual_mfc_test_card = card
        self.update_manual_mfc_test_limit()
        self.update_manual_mfc_test_controls()
        return card

    @staticmethod
    def experiment_status_value(text, object_name="experimentStatusValue"):
        label = QLabel(text)
        label.setObjectName(object_name)
        return label

    def create_mfc_rack_monitor(self):
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(4)

        self.mfc_rack_status_label = QLabel("Read-only | rack not connected")
        self.mfc_rack_status_label.setObjectName("mfcRackStatus")
        content.addWidget(self.mfc_rack_status_label)

        table_header = QGridLayout()
        table_header.setContentsMargins(4, 2, 4, 1)
        table_header.setHorizontalSpacing(8)
        table_header.setColumnMinimumWidth(0, 68)
        table_header.setColumnMinimumWidth(1, 55)
        table_header.setColumnMinimumWidth(2, 60)
        table_header.setColumnMinimumWidth(3, 70)
        table_header.setColumnStretch(0, 1)
        table_header.setColumnStretch(1, 1)
        table_header.setColumnStretch(2, 1)
        for column, text in enumerate((
            "Channel",
            "Actual\n(mln/min)",
            "Setpoint\n(mln/min)",
            "Status",
        )):
            label = QLabel(text)
            label.setObjectName("mfcMonitorHeader")
            if column in (1, 2, 3):
                label.setAlignment(Qt.AlignCenter)
            table_header.addWidget(label, 0, column)
        content.addLayout(table_header)

        self.mfc_channel_monitor = {}
        for index in range(1, 7):
            row = QFrame()
            row.setObjectName("mfcChannelMonitorRow")
            row.setFixedHeight(36)

            row_layout = QGridLayout()
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setHorizontalSpacing(8)
            row_layout.setColumnMinimumWidth(0, 68)
            row_layout.setColumnMinimumWidth(1, 55)
            row_layout.setColumnMinimumWidth(2, 60)
            row_layout.setColumnMinimumWidth(3, 70)
            row_layout.setColumnStretch(0, 1)
            row_layout.setColumnStretch(1, 1)
            row_layout.setColumnStretch(2, 1)

            channel_label = QLabel(f"MFC {index}")
            channel_label.setObjectName("mfcChannelName")
            channel_label.setProperty("channel", str(index))
            actual_label = QLabel("--")
            actual_label.setObjectName("mfcChannelValue")
            actual_label.setAlignment(Qt.AlignCenter)
            setpoint_label = QLabel("--")
            setpoint_label.setObjectName("mfcChannelValue")
            setpoint_label.setAlignment(Qt.AlignCenter)
            status_label = QLabel("Waiting")
            status_label.setObjectName("mfcChannelStatus")
            status_label.setProperty("state", "waiting")
            status_label.setAlignment(Qt.AlignCenter)

            row_layout.addWidget(channel_label, 0, 0)
            row_layout.addWidget(actual_label, 0, 1)
            row_layout.addWidget(setpoint_label, 0, 2)
            row_layout.addWidget(status_label, 0, 3, Qt.AlignRight)
            row.setLayout(row_layout)
            content.addWidget(row)
            self.mfc_channel_monitor[index] = {
                "row": row,
                "actual": actual_label,
                "setpoint": setpoint_label,
                "status": status_label,
            }

        return self.compact_section_card("MFC Monitor", content)

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

    def reading_row(self, name, value_label, color):
        row = QFrame()
        row.setObjectName("compactReadingRow")

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(8)

        dot = QFrame()
        dot.setObjectName("compactReadingMarker")
        dot.setStyleSheet(f"background: {color}; border: none; border-radius: 0px;")
        dot.setFixedSize(12, 4)

        name_label = QLabel(name)
        name_label.setObjectName("compactReadingName")

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
        name_label.setObjectName("experimentStatusName")

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
        self.device_control_rows = getattr(self, "device_control_rows", [])
        self.device_control_rows.append(row)
        row.setFixedHeight(46)
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
            "MFC Rack (6 nodes)",
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
            "Rack",
            self.mfc_port_selector,
            self.scan_mfc_button,
        ))
        body.layout().addWidget(self.mfc_status_label)
        body.layout().addWidget(self.mfc_note_label)
        body.setVisible(False)
        self.device_setup_bodies = getattr(self, "device_setup_bodies", [])
        self.device_setup_bodies.append(body)
        self.device_control_rows = getattr(self, "device_control_rows", [])
        self.device_control_rows.append(row)
        row.setFixedHeight(46)
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
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(6)
        body.setLayout(layout)
        return body

    def device_setting_row(self, label_text, selector, button):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("metricName")
        label.setFixedWidth(42)
        selector.setFixedWidth(130)
        row.addWidget(label)
        row.addWidget(selector, 1)
        row.addWidget(button, 0)
        return row

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
        for column, width in enumerate((70, 85, 125, 110, 105, 95)):
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
            ratios = (0.12, 0.15, 0.23, 0.18, 0.18, 0.14)
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

        if not self.log_preview_expanded:
            self.log_card_widget.setMinimumHeight(52)
            self.log_card_widget.setMaximumHeight(52)
            return

        self.log_card_widget.setMinimumHeight(235)
        if self.max_log_preview_rows <= 5:
            self.log_card_widget.setMaximumHeight(245)
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
            minimum_height = 352 if self.recipe_details_expanded else 258
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
            self.recipe_card_widget.setMinimumHeight(352 if expanded else 258)

    def toggle_recipe_details(self):
        self.set_recipe_details_expanded(not self.recipe_details_expanded)

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
        self.log_table.setRowCount(0)

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
        full_path = str(Path(self.data_directory) / file_name) if file_name else self.data_directory
        display_name = self.filename_stem if preview or not filename else Path(filename).stem
        self.save_location_input.setText(display_name)
        self.save_location_input.setToolTip(
            f"Output: {full_path}\n"
            "Edit the experiment name. The timestamp and selected file extension are added automatically."
        )
        if hasattr(self, "choose_save_location_button"):
            self.choose_save_location_button.setToolTip(
                f"Choose save location\nCurrent folder: {self.data_directory}"
            )

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

    def schedule_steps(self):
        steps = []
        for row in range(self.recipe_table.rowCount()):
            duration_seconds = self.recipe_duration_number(row)
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
                "setpoints": setpoints,
                "event_name": recipe_event(self.recipe_table, row),
            })
        if not steps:
            raise ValueError("Add at least one experiment step.")
        return steps

    def update_recipe_total(self, changed_item):
        if changed_item.column() < 4:
            return

        values = []
        invalid_value = False
        for column in range(4, 10):
            item = self.recipe_table.item(changed_item.row(), column)
            raw_value = item.text().strip() if item is not None else ""
            numeric_text = self.recipe_numeric_text(raw_value)
            if numeric_text is None:
                invalid_value = True
                break
            values.append(float(numeric_text))

        total_item = self.recipe_table.item(changed_item.row(), 1)
        if total_item is None:
            total_item = QTableWidgetItem()
            total_item.setTextAlignment(Qt.AlignCenter)
            total_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.recipe_table.setItem(changed_item.row(), 1, total_item)

        self.recipe_table.blockSignals(True)
        total_item.setText("--" if invalid_value else f"{sum(values):g}")
        style_recipe_total_item(total_item)
        self.update_recipe_rh(changed_item.row())
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
            setpoints = {
                index: self.recipe_cell_value(row, index + 3)
                for index in range(1, 7)
            }
            has_values = any(value not in (None, 0.0) for value in setpoints.values())
            if duration == 0 and not has_values:
                continue

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
        input_widget.setFixedWidth(62)
        input_widget.setFixedHeight(24)
        return input_widget

    def selected_recipe_row(self):
        selected_rows = self.recipe_table.selectionModel().selectedRows()
        return selected_rows[0].row() if selected_rows else -1

    def update_recipe_mfc6_remainder(self, *_args):
        if not hasattr(self, "recipe_mfc6_remainder_label"):
            return

        target_total = self.recipe_target_total_input.value()
        humid_air = target_total * self.recipe_rh_input.value() / 100
        analyte_total = sum(input_widget.value() for input_widget in self.recipe_gas_inputs.values())
        remainder = target_total - humid_air - analyte_total - self.recipe_dry_mfc5_input.value()
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

        target_total = self.recipe_target_total_input.value()
        humid_air = target_total * self.recipe_rh_input.value() / 100
        setpoints = {
            1: self.recipe_gas_inputs[1].value(),
            2: self.recipe_gas_inputs[2].value(),
            3: self.recipe_gas_inputs[3].value(),
            4: humid_air,
            5: self.recipe_dry_mfc5_input.value(),
            6: self.update_recipe_mfc6_remainder(),
        }
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

    def on_experiment_started(self, filename):
        self.completed_experiment_exists = False
        self.current_file_path = filename
        self.experiment_status_step_index = -1
        self.experiment_step_deadline = None
        self.start_button.setEnabled(False)
        set_recipe_editable(self.recipe_table, self.recipe_action_buttons, False)
        self.recipe_target_total_input.setEnabled(False)
        self.recipe_event_input.setEnabled(False)
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
        self.cancel_all_environment_countdowns(restore=False)
        self.reset_duration_controls()
        if stopped_after_error:
            self.bottom_acquisition_label.setText("Acquisition error")
            self.update_experiment_status()
            return

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
        if (
            self.is_experiment_running()
            and 0 <= self.experiment_status_step_index < len(self.recipe_to_run)
        ):
            self.experiment_step_value.setText(
                f"{self.experiment_status_step_index + 1} of {len(self.recipe_to_run)}"
            )
            remaining_seconds = max(
                0,
                math.ceil(self.experiment_step_deadline - time.monotonic())
            ) if self.experiment_step_deadline is not None else 0
            self.experiment_remaining_value.setText(
                self.format_experiment_duration(remaining_seconds)
            )
        else:
            self.experiment_step_value.setText("--")
            self.experiment_remaining_value.setText("--")

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

    def update_manual_mfc_test_limit(self, _index=None):
        if not hasattr(self, "manual_mfc_flow_input"):
            return
        channel_index = self.manual_mfc_channel_selector.currentData()
        try:
            capacity = self.manager.mfc_channel_capacity_sccm(int(channel_index))
        except (TypeError, ValueError, IndexError):
            capacity = 0.0
        self.manual_mfc_flow_input.setRange(0.01, max(0.01, capacity))
        self.manual_mfc_flow_input.setToolTip(
            f"MFC {channel_index} hardware capacity: {capacity:g} mln/min"
        )
        if self.manual_mfc_flow_input.value() > capacity > 0:
            self.manual_mfc_flow_input.setValue(capacity)

    def update_manual_mfc_test_controls(self):
        if not hasattr(self, "manual_mfc_test_card"):
            return
        ready = (
            self.manager.mfc_mode == "real"
            and self.is_real_mfc_mode()
            and not self.is_experiment_running()
        )
        for widget in (
            self.manual_mfc_channel_selector,
            self.manual_mfc_flow_input,
            self.manual_mfc_apply_button,
            self.manual_mfc_zero_button,
        ):
            widget.setEnabled(ready)

        if ready:
            self.manual_mfc_test_state.setText(
                "One channel only. All MFC setpoints must be zero before Apply."
            )
        elif self.is_experiment_running():
            self.manual_mfc_test_state.setText(
                "Manual test is disabled while an experiment is running."
            )
        else:
            self.manual_mfc_test_state.setText(
                "Connect a verified real rack to enable manual testing."
            )

    def apply_manual_mfc_test(self):
        if not self.manual_mfc_apply_button.isEnabled():
            return

        channel_index = self.manual_mfc_channel_selector.currentData()
        flow = self.manual_mfc_flow_input.value()
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("Apply real MFC test flow?")
        dialog.setText(f"Apply {flow:g} mln/min to MFC {channel_index}?")
        dialog.setInformativeText(
            "This sends a real command to the verified MFC rack. Only the selected "
            "channel may flow; the app will refuse the test unless every MFC setpoint "
            "is currently zero. Confirm the gas outlet is open before continuing."
        )
        apply_button = dialog.addButton("Apply test flow", QMessageBox.AcceptRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        if dialog.clickedButton() != apply_button:
            return

        state = self.manager.apply_manual_mfc_test(channel_index, flow)
        if state is None:
            return
        self.manual_mfc_test_state.setText(
            f"MFC {channel_index} command confirmed: {flow:g} mln/min. "
            "Use Zero all MFCs when the check is complete."
        )
        self.set_system_message(
            f"Manual MFC test active on MFC {channel_index}: {flow:g} mln/min.",
            "running",
        )

    def confirm_zero_all_mfcs(self):
        if not self.manual_mfc_zero_button.isEnabled():
            return

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle("Zero all real MFCs?")
        dialog.setText("Set all six real MFC setpoints to zero?")
        dialog.setInformativeText(
            "The app will send zero to every verified controller and then read the "
            "setpoints back. Do not treat a communication error as confirmation that "
            "the gas flow has stopped."
        )
        zero_button = dialog.addButton("Zero all MFCs", QMessageBox.DestructiveRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        if dialog.clickedButton() != zero_button:
            return

        state = self.manager.zero_real_mfc_setpoints()
        if state is None:
            return
        self.manual_mfc_test_state.setText("All six MFC zero setpoints were confirmed.")
        self.set_system_message("All verified MFC setpoints reset to zero.", "idle")

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
        self.update_manual_mfc_test_controls()

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
        self.set_mfc_write_controls_enabled(not is_real)

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
                "Scan verifies 6 MFC nodes before connection. Manual test is available after connect."
            )
            self.manual_mode_label.setText(
                "Real MFC mode. Schedule flow control remains disabled."
            )
            self.bottom_mode_label.setText(
                "Real rack mode: manual single-channel test is available after connection."
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
            self.manual_mode_label.setText(
                "Simulated MFC mode. Software model only."
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
            "MFC rack verified. Click Connect to monitor it or run a manual single-channel test.",
            "idle",
        )
        self.update_device_setup_controls_enabled()
        self.update_manual_mfc_test_controls()

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
                    "MFC rack connected. Manual single-channel test is available.",
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
            self.set_mfc_write_controls_enabled(False)
            self.update_manual_mfc_test_limit()
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
                self.set_mfc_write_controls_enabled(False)
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
                self.set_mfc_write_controls_enabled(True)
            self.mfc_status_label.setToolTip(status)
        self.update_manual_mfc_test_controls()

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
        self.update_mfc_rack_monitor(state)
        humidity = "ON" if state.humidity_on else "OFF"
        heating = "ON" if state.heating_on else "OFF"
        channels = getattr(state, "mfc_channels", ())
        total_actual = sum(channel.actual_sccm for channel in channels)
        total_setpoint = sum(channel.setpoint_sccm for channel in channels)

        self.nh3_value_label.setText(f"{total_actual:g} mln/min")
        self.air_value_label.setText(f"{total_setpoint:g} mln/min")
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
            self.mfc_rack_status_label.setText("Simulation | 6 simulated MFC channels")
        elif self.manager.mfc_mode == "real":
            self.mfc_rack_status_label.setText("Real rack | not connected")
        else:
            self.mfc_rack_status_label.setText("Simulation | rack not connected")

        if channels:
            total_capacity = sum(channel.capacity_sccm for channel in channels.values())
            total_actual = sum(channel.actual_sccm for channel in channels.values())
            total_setpoint = sum(channel.setpoint_sccm for channel in channels.values())
            self.max_total_flow_label.setText(f"{total_capacity:g} mln/min")
            self.nh3_actual_label.setText(f"{total_actual:.2f} mln/min")
            self.air_actual_label.setText(f"{total_setpoint:.2f} mln/min")
        else:
            self.max_total_flow_label.setText("--")
            self.nh3_actual_label.setText("--")
            self.air_actual_label.setText("--")

        for index, widgets in self.mfc_channel_monitor.items():
            channel = channels.get(index)
            status_label = widgets["status"]
            if channel is None:
                widgets["actual"].setText("--")
                widgets["setpoint"].setText("--")
                status_label.setText("Waiting")
                status_label.setProperty("state", "waiting")
                widgets["row"].setToolTip("")
            else:
                unit = channel.capacity_unit or "mln/min"
                widgets["actual"].setText(f"{channel.actual_sccm:.2f}")
                widgets["setpoint"].setText(f"{channel.setpoint_sccm:.2f}")
                status_label.setText(channel.status)
                status_label.setProperty(
                    "state",
                    "alarm" if channel.status == "ALARM"
                    else "simulated" if channel.status == "SIMULATED"
                    else "ok",
                )
                widgets["row"].setToolTip(
                    f"Address: {channel.address}\n"
                    f"Serial: {channel.serial}\n"
                    f"Fluid: {channel.fluid_name}\n"
                    f"Capacity: {channel.capacity_sccm:g} {unit}\n"
                    f"Temperature: {channel.temperature_c:.2f} C\n"
                    f"Alarm Info: {channel.alarm_info or '0'}"
                )
            status_label.style().unpolish(status_label)
            status_label.style().polish(status_label)

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

        self.resistance_curve.setData(self.time_data, self.resistance_data)
        for index, curve in self.flow_curves.items():
            value = data.get(f"mfc{index}_actual_sccm", math.nan)
            self.mfc_flow_data[index].append(value)
            curve.setData(self.time_data, self.mfc_flow_data[index])
        if event:
            self.add_event_marker(data["elapsed_s"], event)
        self.update_plot_ranges()

        self.resistance_value_label.setText(
            self.format_number(data["resistance_ohm"], suffix=" Ohm", precision=2)
        )
        total_actual = sum(
            data.get(f"mfc{index}_actual_sccm", 0.0) for index in range(1, 7)
        )
        total_setpoint = sum(
            data.get(f"mfc{index}_setpoint_sccm", 0.0) for index in range(1, 7)
        )
        self.nh3_actual_label.setText(f"{total_actual:.2f} mln/min")
        self.air_actual_label.setText(f"{total_setpoint:.2f} mln/min")

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
            f"{sum(data.get(f'mfc{index}_actual_sccm', 0.0) for index in range(1, 7)):.2f}",
            f"{sum(data.get(f'mfc{index}_setpoint_sccm', 0.0) for index in range(1, 7)):.2f}",
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
                background: transparent;
                border: none;
            }
            QFrame#toolbarControls {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
            }
            QFrame#toolbarSection,
            QFrame#toolbarButtonSection {
                background: transparent;
                border: none;
            }
            QFrame#toolbarSection[separated="true"] {
                border-left: 1px solid #e5eaf0;
            }
            QWidget#toolbarInlineGroup {
                background: transparent;
                border: none;
            }
            QLabel#toolbarInlineLabel {
                color: #64748b;
                font-size: 12px;
                font-weight: 700;
            }
            QFrame#toolbarDivider {
                background: #e5eaf0;
                border: none;
                min-width: 1px;
                max-width: 1px;
            }
            QFrame#systemMessageBar {
                background: #eff6ff;
                border: none;
                border-radius: 5px;
            }
            QFrame#systemMessageBar[state="running"] {
                background: #ecfdf3;
                border-color: #86efac;
            }
            QFrame#systemMessageBar[state="stopped"] {
                background: #f8fafc;
                border-color: #cbd5e1;
            }
            QFrame#systemMessageBar[state="error"] {
                background: #fef2f2;
                border-color: #fca5a5;
            }
            QFrame#systemMessageBar[state="warning"] {
                background: #fffbeb;
                border-color: #fcd34d;
            }
            QLabel#systemMessageIcon {
                color: #2563eb;
                background: #dbeafe;
                border-radius: 7px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#systemMessageIcon[state="running"] {
                color: #15803d;
                background: #dcfce7;
            }
            QLabel#systemMessageIcon[state="stopped"] {
                color: #475569;
                background: #e2e8f0;
            }
            QLabel#systemMessageIcon[state="error"] {
                color: #dc2626;
                background: #fee2e2;
            }
            QLabel#systemMessageIcon[state="warning"] {
                color: #a16207;
                background: #fef3c7;
            }
            QLabel#systemMessageText {
                color: #2563eb;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#systemMessageText[state="running"] {
                color: #15803d;
            }
            QLabel#systemMessageText[state="stopped"] {
                color: #475569;
            }
            QLabel#systemMessageText[state="error"] {
                color: #dc2626;
            }
            QLabel#systemMessageText[state="warning"] {
                color: #a16207;
            }
            QPushButton#systemMessageDismissButton {
                min-height: 18px;
                max-height: 18px;
                min-width: 18px;
                max-width: 18px;
                padding: 0;
                border: none;
                border-radius: 4px;
                color: #475569;
                background: transparent;
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton#systemMessageDismissButton:hover {
                color: #1e293b;
                background: #dbeafe;
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
                border-radius: 5px;
            }
            QFrame#compactSectionCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
            }
            QFrame#graphCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
            }
            QFrame#logCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
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
            QFrame#eventSummary {
                background: #eef2f7;
                border: none;
                border-radius: 0;
            }
            QLabel#eventSummaryLabel {
                color: #475569;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#graphAction {
                color: #475569;
                font-size: 16px;
                font-weight: 700;
                min-width: 22px;
                max-width: 22px;
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
            QPushButton#sectionChevron,
            QPushButton#logChevron {
                background: transparent;
                border: none;
                color: #475569;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                min-height: 20px;
            }
            QPushButton#sectionChevron:hover,
            QPushButton#logChevron:hover {
                background: #eef2f7;
                border-radius: 4px;
            }
            QFrame#metricRow,
            QFrame#deviceStatusRow,
            QFrame#readingCard,
            QFrame#controlCard,
            QFrame#gasChannelRow,
            QFrame#environmentChannelRow {
                background: #fbfcfe;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
            QFrame#deviceRow {
                background: #f7f9fc;
                border: none;
                border-radius: 0;
            }
            QFrame#mfcChannelMonitorRow {
                background: transparent;
                border: none;
                border-bottom: 1px solid #edf2f7;
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
            QFrame#compactReadingMarker {
                min-width: 12px;
                max-width: 12px;
                min-height: 4px;
                max-height: 4px;
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
            QLabel#compactReadingName {
                color: #52637a;
                font-size: 12px;
                font-weight: 700;
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
            QLabel#experimentStatusValue {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#experimentTimeValue {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#experimentStatusName {
                color: #52637a;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#experimentStateBadge {
                color: #475569;
                background: #f1f5f9;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#experimentStateBadge[state="idle"],
            QLabel#experimentStateBadge[state="running"] {
                color: #15803d;
                background: #dcfce7;
            }
            QLabel#experimentStateBadge[state="stopped"],
            QLabel#experimentStateBadge[state="error"] {
                color: #dc2626;
                background: #fee2e2;
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
                border: none;
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
            QLabel#connectedLabel[state="verified"] {
                color: #b45309;
            }
            QLabel#mfcRackStatus {
                color: #2563eb;
                background: #eff6ff;
                border: none;
                border-radius: 0;
                padding: 8px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#mfcMonitorHeader {
                color: #64748b;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#mfcTotalFlow {
                color: #0f172a;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#rateUnitBox {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QDoubleSpinBox#rateInput {
                min-height: 0;
                max-height: 32px;
                padding: 0 4px;
            }
            QLabel#mfcChannelName {
                color: #0f172a;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#mfcChannelName[channel="1"] { color: #2563eb; }
            QLabel#mfcChannelName[channel="2"] { color: #f97316; }
            QLabel#mfcChannelName[channel="3"] { color: #16a34a; }
            QLabel#mfcChannelName[channel="4"] { color: #7c3aed; }
            QLabel#mfcChannelName[channel="5"] { color: #dc2626; }
            QLabel#mfcChannelName[channel="6"] { color: #0f9f9a; }
            QLabel#mfcChannelValue {
                color: #1e293b;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#mfcChannelStatus {
                color: #64748b;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#mfcChannelStatus[state="ok"] {
                color: #15803d;
            }
            QLabel#mfcChannelStatus[state="alarm"] {
                color: #dc2626;
            }
            QLabel#mfcChannelStatus[state="simulated"] {
                color: #64748b;
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
            QLabel#deviceStatusDot[state="verified"] {
                background: #d97706;
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
            QDoubleSpinBox,
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
            QDoubleSpinBox:disabled,
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
                border: none;
                background: #ecfdf3;
                font-weight: 700;
            }
            QPushButton#startButton:hover,
            QPushButton#primaryButton:hover {
                background: #dcfce7;
            }
            QPushButton#startButton:disabled {
                color: #94a3b8;
                background: #f1f5f9;
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
            QPushButton#plotModeButton {
                min-width: 104px;
                color: #475569;
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0;
                font-size: 12px;
                font-weight: 600;
                padding: 2px 12px;
            }
            QPushButton#plotModeButton[position="start"] {
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
            }
            QPushButton#plotModeButton[position="end"] {
                border-left: none;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QPushButton#plotModeButton[active="true"] {
                color: #1d4ed8;
                background: #eff6ff;
                border-color: #60a5fa;
                font-weight: 700;
            }
            QLabel#flowLegendItem {
                font-size: 11px;
                font-weight: 600;
            }
            QComboBox#toolbarFormatSelector {
                min-height: 0;
                max-height: 32px;
                padding-top: 0;
                padding-bottom: 0;
            }
            QPushButton#rateStepButton {
                min-height: 0;
                max-height: 32px;
                min-width: 38px;
                max-width: 38px;
                border: none;
                background: transparent;
                padding: 0;
                text-align: center;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton#rateStepButton:hover {
                background: #eff6ff;
            }
            QPushButton#folderButton {
                min-height: 0;
                max-height: 32px;
                min-width: 32px;
                max-width: 32px;
                padding: 0;
                border-radius: 5px;
            }
            QPushButton#stopButton {
                color: #dc2626;
                border: none;
                background: #fef2f2;
                font-weight: 700;
            }
            QPushButton#stopButton:hover {
                background: #fee2e2;
            }
            QPushButton#recipeDuplicateButton {
                color: #334155;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeDuplicateButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton#recipeAddButton {
                color: #1d4ed8;
                background: transparent;
                border: 1px solid #bfdbfe;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeAddButton:hover {
                background: #dbeafe;
                border-color: #93c5fd;
            }
            QPushButton#recipeRemoveButton {
                color: #dc2626;
                background: transparent;
                border: 1px solid #fecaca;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeRemoveButton:hover {
                background: #fee2e2;
                border-color: #fca5a5;
            }
            QPushButton#recipeClearButton {
                color: #334155;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeClearButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QLabel#recipeMaxTotal {
                color: #475569;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeTargetUnit {
                color: #475569;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeMixtureTitle {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeMixtureValue {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeDetailsTitle {
                color: #1e293b;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeDetailsStep {
                color: #64748b;
                font-size: 11px;
            }
            QDoubleSpinBox#recipeMixtureInput {
                min-height: 0;
                max-height: 24px;
                padding: 0 4px;
                border-radius: 4px;
            }
            QPushButton#recipeMixtureButton {
                color: #1d4ed8;
                background: transparent;
                border: 1px solid #bfdbfe;
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeMixtureButton:hover {
                background: #dbeafe;
                border-color: #93c5fd;
            }
            QDoubleSpinBox#recipeTargetTotal {
                min-height: 0;
                max-height: 22px;
                padding-top: 0;
                padding-bottom: 0;
                border-radius: 4px;
            }
            QLineEdit#recipeEventInput {
                min-height: 0;
                max-height: 28px;
                padding: 0 7px;
                border-radius: 4px;
            }
            QLabel#recipeIssues {
                color: #b91c1c;
                background: #fee2e2;
                border: 1px solid #fecaca;
                border-radius: 5px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#manualMfcLabel,
            QLabel#manualMfcUnit {
                color: #475569;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#manualMfcHint {
                color: #64748b;
                font-size: 10px;
                line-height: 1.25;
            }
            QComboBox#manualMfcChannel,
            QDoubleSpinBox#manualMfcFlow {
                min-height: 0;
                max-height: 26px;
                padding: 0 6px;
            }
            QPushButton#manualMfcApplyButton {
                color: #1d4ed8;
                background: transparent;
                border: 1px solid #bfdbfe;
                border-radius: 4px;
                padding: 0 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton#manualMfcApplyButton:hover {
                background: #dbeafe;
                border-color: #93c5fd;
            }
            QPushButton#manualMfcZeroButton {
                color: #b91c1c;
                background: transparent;
                border: 1px solid #fecaca;
                border-radius: 4px;
                padding: 0 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton#manualMfcZeroButton:hover {
                background: #fee2e2;
                border-color: #fca5a5;
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
            QTableWidget#recipeTable::item {
                border: 0;
                border-radius: 0;
                padding: 0 4px;
            }
            QTableWidget#recipeTable {
                background: #ffffff;
                alternate-background-color: #f6f8fb;
                border: 1px solid #d9e2ee;
                border-radius: 0;
                gridline-color: #d9e2ee;
            }
            QTableWidget#recipeTable QHeaderView::section {
                background: #e8eef5;
                color: #1f3653;
                border: 0;
                border-right: 1px solid #d4deea;
                border-bottom: 1px solid #d4deea;
                padding: 5px 4px;
                font-weight: 700;
                font-size: 11px;
            }
            QTableWidget#recipeTable::item:selected,
            QTableWidget#recipeTable::item:selected:!active {
                background: #dbeafe;
                color: #0f172a;
                border: 0;
                outline: none;
            }
            QTableWidget#recipeTable QLineEdit {
                min-height: 0;
                max-height: 20px;
                padding: 0 3px;
                border: 1px solid #93c5fd;
                border-radius: 3px;
                background: #ffffff;
            }
            QTableWidget#recipeTable QLineEdit:focus {
                border: 1px solid #2563eb;
                border-radius: 3px;
                background: #ffffff;
            }
            QFrame#recipeMixtureBand {
                background: #f8fafc;
                border: 0;
                border-top: 1px solid #dbe3ee;
                border-radius: 0;
            }
            QHeaderView::section {
                background: #eef2f7;
                color: #334155;
                border: 0;
                border-right: 1px solid #dbe3ee;
                border-bottom: 1px solid #dbe3ee;
                padding: 5px 4px;
                font-weight: 700;
                font-size: 11px;
            }
        """.replace("__CHEVRON_DOWN__", chevron_down_path))
