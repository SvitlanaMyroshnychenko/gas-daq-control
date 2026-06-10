from datetime import datetime
import math
import time

from PySide6.QtCore import QObject, QTimer, Signal

from gas_sensor_daq.devices.factory import create_devices, create_multimeter
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

    def __init__(self, parent=None, settings=DEFAULT_SETTINGS):
        super().__init__(parent)
        self.settings = settings
        self.multimeter, self.mfc = create_devices(settings)
        self.multimeter_mode = settings.multimeter_mode
        self.keithley_resource = settings.keithley_resource
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
            record = self.multimeter.read(self.current_state())
            record.event = self.pending_event

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
        except Exception as exc:
            self.handle_device_error("Acquisition failed", exc)
            self.write_error_record(self.pending_event)
            self.stop_experiment("Stopped: acquisition failed")

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
        message = f"{context}: {exc}"
        self.pending_event = message
        self.device_error.emit(message)

    def write_error_record(self, message):
        if self.logger is None:
            return

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
            device_status="ERROR",
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
