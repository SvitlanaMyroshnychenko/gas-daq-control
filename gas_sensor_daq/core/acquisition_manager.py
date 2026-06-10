from datetime import datetime
import math
import time

from PySide6.QtCore import QObject, QTimer, Signal

from gas_sensor_daq.devices.factory import create_devices, create_mfc, create_multimeter
from gas_sensor_daq.logging.data_logger import CSVLogger, ExcelLogger
from gas_sensor_daq.models.records import MeasurementRecord
from gas_sensor_daq.settings import DEFAULT_SETTINGS


class AcquisitionManager(QObject):
    experiment_started = Signal(str)
    experiment_stopped = Signal(str)
    elapsed_changed = Signal(str)
    data_acquired = Signal(object, str)
    state_changed = Signal(object)
    device_error = Signal(str)
    multimeter_changed = Signal(str, str)
    mfc_changed = Signal(str, str)

    def __init__(self, parent=None, settings=DEFAULT_SETTINGS):
        super().__init__(parent)
        self.settings = settings
        self.multimeter, self.mfc = create_devices(settings)
        self.multimeter_mode = settings.multimeter_mode
        self.mfc_mode = settings.mfc_mode
        self.keithley_resource = settings.keithley_resource
        self.bronkhorst_port = settings.bronkhorst_port
        self.bronkhorst_address = settings.bronkhorst_address
        self.logger = None
        self.pending_event = ""
        self.experiment_start_time = None

        self.acquisition_timer = QTimer(self)
        self.acquisition_timer.timeout.connect(self.acquire_once)

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)

    def current_state(self):
        try:
            return self.mfc.get_state()
        except Exception as exc:
            self.handle_device_error("MFC state read failed", exc)
            raise

    def set_multimeter_mode(self, mode, resource_name=""):
        if self.acquisition_timer.isActive():
            self.handle_device_error(
                "Cannot switch multimeter",
                RuntimeError("Stop the experiment before changing device mode."),
            )
            return False

        previous_multimeter = self.multimeter

        try:
            new_multimeter = create_multimeter(
                self.settings,
                mode=mode,
                resource_name=resource_name,
            )
        except Exception as exc:
            self.handle_device_error("Multimeter connection failed", exc)
            return False

        self.multimeter = new_multimeter
        self.multimeter_mode = mode
        self.keithley_resource = resource_name
        self._close_device(previous_multimeter, "Previous multimeter close failed")
        self.multimeter_changed.emit(mode, self.multimeter_status_text())
        return True

    def multimeter_status_text(self):
        if self.multimeter_mode == "real":
            return f"Keithley 2450: real ({self.keithley_resource})"

        return "Keithley 2450: simulated"

    def set_mfc_mode(self, mode, port="", address=None):
        if self.acquisition_timer.isActive():
            self.handle_device_error(
                "Cannot switch MFC",
                RuntimeError("Stop the experiment before changing device mode."),
            )
            return False

        previous_mfc = self.mfc
        self._close_device(previous_mfc, "Previous MFC close failed")

        try:
            new_mfc = create_mfc(
                self.settings,
                mode=mode,
                port=port or self.settings.bronkhorst_port,
                address=address,
            )
        except Exception as exc:
            self.mfc = create_mfc(self.settings, mode="simulation")
            self.mfc_mode = "simulation"
            self.mfc_changed.emit("simulation", self.mfc_status_text())
            self.handle_device_error("MFC connection failed", exc)
            return False

        self.mfc = new_mfc
        self.mfc_mode = mode
        self.bronkhorst_port = port
        self.bronkhorst_address = address
        self.mfc_changed.emit(mode, self.mfc_status_text())
        self.emit_state_changed()
        return True

    def mfc_status_text(self):
        if self.mfc_mode == "real":
            status_text = getattr(self.mfc, "status_text", None)
            if status_text is not None:
                return status_text()
            return f"Bronkhorst MFC: real ({self.bronkhorst_port})"

        return "Bronkhorst MFC: simulated"

    def start_experiment(self, save_format):
        try:
            self.multimeter.reset_time()
            self.pending_event = ""
            self.experiment_start_time = datetime.now()

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            if save_format == "CSV":
                filename = f"data/experiment_{timestamp}.csv"
                self.logger = CSVLogger(filename)
            else:
                filename = f"data/experiment_{timestamp}.xlsx"
                self.logger = ExcelLogger(filename)

            self.acquisition_timer.start(self.settings.acquisition_interval_ms)
            self.elapsed_timer.start(1000)
            self.experiment_started.emit(filename)
            self.elapsed_changed.emit("00:00:00")
        except Exception as exc:
            self.handle_device_error("Experiment start failed", exc)
            self.stop_experiment("Experiment start failed")

    def stop_experiment(self, message="Experiment finished"):
        self.acquisition_timer.stop()
        self.elapsed_timer.stop()

        if self.logger is not None:
            try:
                self.logger.close()
            except Exception as exc:
                self.handle_device_error("Logger close failed", exc)
            self.logger = None

        self.experiment_stopped.emit(message)

    def close(self):
        self.acquisition_timer.stop()
        self.elapsed_timer.stop()

        if self.logger is not None:
            try:
                self.logger.close()
            except Exception as exc:
                self.handle_device_error("Logger close failed", exc)
            self.logger = None

        self._close_device(self.multimeter, "Multimeter close failed")
        self._close_device(self.mfc, "MFC close failed")

    def update_elapsed_time(self):
        if self.experiment_start_time is None:
            return

        delta = datetime.now() - self.experiment_start_time
        total_seconds = int(delta.total_seconds())

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        self.elapsed_changed.emit(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def set_event(self, text):
        self.pending_event = text

    def apply_nh3(self, flow_sccm, duration_ms=0):
        if not self.safe_command("Set NH3 flow failed", self.mfc.set_nh3_flow, flow_sccm):
            return

        self.set_event(f"Set NH3 flow = {flow_sccm} sccm")
        self.emit_state_changed()

        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.reset_nh3)

    def reset_nh3(self):
        if not self.safe_command("Reset NH3 failed", self.mfc.set_nh3_flow, 0):
            return

        self.set_event("NH3 duration ended")
        self.emit_state_changed()

    def apply_air(self, flow_sccm):
        if not self.safe_command("Set Air flow failed", self.mfc.set_air_flow, flow_sccm):
            return

        self.set_event(f"Set Air flow = {flow_sccm} sccm")
        self.emit_state_changed()

    def air_purge(self):
        if not self.safe_command("Air purge failed", self.mfc.air_purge):
            return

        self.set_event("Air purge")
        self.emit_state_changed()

    def set_humidity(self, enabled, duration_ms=0):
        if not self.safe_command("Set humidity failed", self.mfc.set_humidity, enabled):
            return

        state = "ON" if enabled else "OFF"
        self.set_event(f"Humidity {state}")
        self.emit_state_changed()

        if enabled and duration_ms > 0:
            QTimer.singleShot(duration_ms, lambda: self.set_humidity(False))

    def set_heating(self, enabled, duration_ms=0):
        if not self.safe_command("Set heating failed", self.mfc.set_heating, enabled):
            return

        state = "ON" if enabled else "OFF"
        self.set_event(f"Heating {state}")
        self.emit_state_changed()

        if enabled and duration_ms > 0:
            QTimer.singleShot(duration_ms, lambda: self.set_heating(False))

    def acquire_once(self):
        try:
            state = self.mfc.get_state()
        except Exception as exc:
            message = self.format_device_error(
                "Bronkhorst MFC connection lost during read",
                exc,
            )
            self.handle_device_error_message(message)
            self.write_error_record(message)
            self.stop_experiment("Stopped: MFC connection lost")
            return

        try:
            record = self.multimeter.read(state)
            record.event = self.pending_event
        except Exception as exc:
            message = self.format_device_error(
                "Keithley connection lost during measurement",
                exc,
            )
            self.handle_device_error_message(message)
            self.write_error_record(message, state)
            self.stop_experiment("Stopped: Keithley connection lost")
            return

        if self.logger is not None:
            try:
                self.logger.write(record)
            except Exception as exc:
                self.handle_device_error("Logger write failed", exc)
                self.stop_experiment("Stopped: logger write failed")
                return

        event = self.pending_event
        self.pending_event = ""
        self.data_acquired.emit(record.to_dict(), event)

    def emit_state_changed(self):
        try:
            self.state_changed.emit(self.current_state())
        except Exception:
            pass

    def safe_command(self, context, func, *args):
        try:
            func(*args)
            return True
        except Exception as exc:
            self.handle_device_error(context, exc)
            return False

    def handle_device_error(self, context, exc):
        message = self.format_device_error(context, exc)
        self.handle_device_error_message(message)

    def handle_device_error_message(self, message):
        self.pending_event = message
        self.device_error.emit(message)

    @staticmethod
    def format_device_error(context, exc):
        detail = str(exc).strip()
        if detail:
            return f"{context}. Details: {detail}"
        return context

    def write_error_record(self, message, state=None):
        if self.logger is None:
            return

        if state is None:
            try:
                state = self.current_state()
            except Exception:
                state = None

        elapsed = 0.0
        if self.experiment_start_time is not None:
            elapsed = (datetime.now() - self.experiment_start_time).total_seconds()

        record = MeasurementRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            elapsed_s=elapsed,
            resistance_ohm=math.nan,
            temperature_c=math.nan,
            nh3_flow_sccm=state.nh3_flow_sccm if state is not None else math.nan,
            air_flow_sccm=state.air_flow_sccm if state is not None else math.nan,
            humidity_on=state.humidity_on if state is not None else False,
            heating_on=state.heating_on if state is not None else False,
            event=message,
            nh3_setpoint_sccm=state.nh3_setpoint_sccm if state is not None else math.nan,
            nh3_actual_sccm=state.nh3_actual_sccm if state is not None else math.nan,
            air_setpoint_sccm=state.air_setpoint_sccm if state is not None else math.nan,
            air_actual_sccm=state.air_actual_sccm if state is not None else math.nan,
            multimeter_status="ERROR",
            mfc_status=state.device_status if state is not None else "",
            mfc_port=state.mfc_port if state is not None else "",
            mfc_address=state.mfc_address if state is not None else "",
            mfc_serial=state.mfc_serial if state is not None else "",
            mfc_fluid=state.mfc_fluid if state is not None else "",
            mfc_capacity_sccm=state.mfc_capacity_sccm if state is not None else math.nan,
            mfc_capacity_unit=state.mfc_capacity_unit if state is not None else "",
            mfc_temperature_c=state.mfc_temperature_c if state is not None else math.nan,
            mfc_alarm_info=state.mfc_alarm_info if state is not None else "",
        )

        try:
            self.logger.write(record)
        except Exception as exc:
            self.device_error.emit(f"Failed to write error record: {exc}")

    def _close_device(self, device, context):
        close = getattr(device, "close", None)
        if close is None:
            return

        try:
            close()
        except Exception as exc:
            self.handle_device_error(context, exc)
