from datetime import datetime
import math
import os
import time

from PySide6.QtCore import QObject, QTimer, Signal

from gas_sensor_daq.devices.factory import create_devices, create_mfc, create_multimeter
from gas_sensor_daq.devices.propar_mfc_rack import ProparMFCRack
from gas_sensor_daq.logging.data_logger import CSVLogger, ExcelLogger
from gas_sensor_daq.models.records import MeasurementRecord
from gas_sensor_daq.settings import DEFAULT_SETTINGS


class AcquisitionManager(QObject):
    """Coordinates UI actions, device adapters, acquisition timing, and logging.

    The UI should stay mostly declarative: it asks this manager to start, stop,
    apply controls, or switch devices. Hardware-specific details belong in the
    device adapters under gas_sensor_daq/devices.
    """

    experiment_started = Signal(str)
    experiment_stopped = Signal(str)
    elapsed_changed = Signal(str)
    data_acquired = Signal(object, str)
    state_changed = Signal(object)
    device_error = Signal(str)
    multimeter_changed = Signal(str, str)
    mfc_changed = Signal(str, str)
    recipe_step_changed = Signal(int)

    def __init__(self, parent=None, settings=DEFAULT_SETTINGS):
        super().__init__(parent)
        self.settings = settings
        self.multimeter, self.mfc = create_devices(settings)
        self.multimeter_mode = settings.multimeter_mode
        self.mfc_mode = settings.mfc_mode
        self.multimeter_resource = settings.multimeter_resource
        self.mfc_port = settings.mfc_port
        self.mfc_address = settings.mfc_address
        self.data_directory = settings.data_directory
        self.acquisition_interval_ms = settings.acquisition_interval_ms
        self.logger = None
        self.pending_events = []
        self.experiment_start_time = None
        self.control_timer_tokens = {
            "analyte": 0,
            "humidity": 0,
            "heating": 0,
        }

        self.acquisition_timer = QTimer(self)
        self.acquisition_timer.timeout.connect(self.acquire_once)

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)

        self.recipe_steps = ()
        self.recipe_step_index = -1
        self.recipe_timer = QTimer(self)
        self.recipe_timer.setSingleShot(True)
        self.recipe_timer.timeout.connect(self.advance_simulated_recipe)

    def set_acquisition_rate_hz(self, rate_hz):
        if self.acquisition_timer.isActive():
            raise RuntimeError("Stop the experiment before changing the acquisition rate.")
        if rate_hz <= 0:
            raise ValueError("Acquisition rate must be greater than zero.")
        self.acquisition_interval_ms = max(1, round(1000 / rate_hz))

    def current_state(self):
        try:
            return self.mfc.get_state()
        except Exception as exc:
            self.handle_device_error("MFC state read failed", exc)
            raise

    def set_multimeter_mode(self, mode, resource_name=""):
        # Device mode changes are blocked during acquisition so a run cannot
        # silently mix data from two different instruments in one output file.
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
        self.multimeter_resource = resource_name
        self._close_device(previous_multimeter, "Previous multimeter close failed")
        self.multimeter_changed.emit(mode, self.multimeter_status_text())
        return True

    def multimeter_status_text(self):
        if self.multimeter_mode == "real":
            return f"Multimeter: real ({self.multimeter_resource})"

        return "Multimeter: simulated"

    def set_mfc_mode(self, mode, port="", address=None):
        # If a real MFC connection fails, fall back to simulation. This keeps
        # the UI usable without leaving a half-connected hardware object alive.
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
                port=port or self.settings.mfc_port,
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
        self.mfc_port = port
        self.mfc_address = address
        self.mfc_changed.emit(mode, self.mfc_status_text())
        self.emit_state_changed()
        return True

    def mfc_status_text(self):
        if self.mfc_mode == "real":
            status_text = getattr(self.mfc, "status_text", None)
            if status_text is not None:
                return status_text()
            return f"MFC controller: real ({self.mfc_port})"

        return "MFC controller: simulated"

    def discover_mfc_racks(self):
        """Probe serial ports without sending any MFC control commands."""
        return ProparMFCRack.discover_serial_ports(
            baudrate=self.settings.mfc_baudrate,
            expected_nodes=self.settings.mfc_nodes,
        )

    def start_experiment(self, save_format, data_directory=None, filename_stem="experiment"):
        try:
            # Every Start creates a fresh experiment file. Resume/append would
            # need explicit metadata handling and is intentionally not implicit.
            self.multimeter.reset_time()
            self.pending_events = []
            self.experiment_start_time = datetime.now()
            self.data_directory = data_directory or self.data_directory
            os.makedirs(self.data_directory, exist_ok=True)

            stem = self.sanitize_filename_stem(filename_stem)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            base_filename = f"{stem}_{timestamp}"
            if save_format == "CSV":
                filename = os.path.join(self.data_directory, f"{base_filename}.csv")
                self.logger = CSVLogger(filename)
            else:
                filename = os.path.join(self.data_directory, f"{base_filename}.xlsx")
                self.logger = ExcelLogger(filename)

            self.acquisition_timer.start(self.acquisition_interval_ms)
            self.elapsed_timer.start(1000)
            self.experiment_started.emit(filename)
            self.elapsed_changed.emit("00:00:00")
        except Exception as exc:
            self.handle_device_error("Experiment start failed", exc)
            self.stop_experiment("Experiment start failed")

    def start_simulated_recipe(self, steps):
        if self.mfc_mode != "simulation":
            return False
        if not steps:
            return False

        try:
            self.validate_simulated_recipe(steps)
        except ValueError as exc:
            self.handle_device_error("Simulated experiment validation failed", exc)
            return False

        self.stop_recipe_execution()
        self.recipe_steps = tuple(steps)
        self.recipe_step_index = 0
        self.apply_current_recipe_step()
        return True

    def validate_simulated_recipe(self, steps):
        capacities = getattr(self.mfc, "channel_capacities", {})
        for step_index, step in enumerate(steps, start=1):
            setpoints = step.get("setpoints", {})
            channel_total = 0.0
            for channel_index in range(1, 7):
                try:
                    value = float(setpoints[channel_index])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Step {step_index} is missing a valid MFC {channel_index} setpoint."
                    ) from exc
                capacity = float(capacities.get(channel_index, 0.0))
                if value < 0 or value > capacity:
                    raise ValueError(
                        f"Step {step_index} MFC {channel_index} must be between "
                        f"0 and {capacity:g} sccm."
                    )
                channel_total += value

            total_setpoint = float(step.get("total_setpoint_mln_min", math.nan))
            total_capacity = sum(float(value) for value in capacities.values())
            if total_setpoint > total_capacity:
                raise ValueError(
                    f"Step {step_index} step total exceeds the {total_capacity:g} mln/min rack capacity."
                )
            if not math.isfinite(total_setpoint) or not math.isclose(
                total_setpoint, channel_total, rel_tol=0, abs_tol=0.01
            ):
                raise ValueError(
                    f"Step {step_index} step total must equal the sum of MFC setpoints."
                )

    def mfc_channel_capacity_sccm(self, channel_index):
        capacities = getattr(self.mfc, "channel_capacities", {})
        return float(capacities.get(channel_index, 0.0))

    def apply_current_recipe_step(self):
        if not 0 <= self.recipe_step_index < len(self.recipe_steps):
            return

        step = self.recipe_steps[self.recipe_step_index]
        try:
            self.mfc.set_channel_setpoints(step["setpoints"])
        except Exception as exc:
            self.handle_device_error("Apply simulated experiment step failed", exc)
            self.stop_experiment("Stopped: experiment step could not be applied")
            return

        self.set_event(
            f"Experiment step {self.recipe_step_index + 1}/{len(self.recipe_steps)}: "
            f"step total {step['total_setpoint_mln_min']:g} mln/min"
        )
        self.emit_state_changed()
        self.recipe_step_changed.emit(self.recipe_step_index)
        self.recipe_timer.start(step["duration_ms"])

    def advance_simulated_recipe(self):
        self.recipe_step_index += 1
        if self.recipe_step_index < len(self.recipe_steps):
            self.apply_current_recipe_step()
            return

        try:
            self.mfc.set_channel_setpoints({index: 0.0 for index in range(1, 7)})
        except Exception as exc:
            self.handle_device_error("Reset simulated experiment flows failed", exc)
            return

        self.set_event("Experiment completed; simulated MFC setpoints reset to zero")
        self.emit_state_changed()
        self.recipe_step_changed.emit(-1)

    def stop_recipe_execution(self):
        self.recipe_timer.stop()
        self.recipe_steps = ()
        self.recipe_step_index = -1

    @staticmethod
    def sanitize_filename_stem(filename_stem):
        stem = str(filename_stem or "").strip().rstrip(". ")
        if not stem:
            return "experiment"

        invalid_characters = '<>:"/\\|?*'
        sanitized = "".join(
            "_" if character in invalid_characters else character
            for character in stem
        ).strip()
        return sanitized or "experiment"

    def stop_experiment(self, message="Experiment finished"):
        self.acquisition_timer.stop()
        self.elapsed_timer.stop()
        self.invalidate_control_timers()
        self.stop_recipe_execution()

        self.safe_shutdown_controls()

        if self.logger is not None:
            try:
                self.logger.close()
            except Exception as exc:
                self.handle_device_error("Logger close failed", exc)
            self.logger = None

        self.experiment_stopped.emit(message)

    def safe_shutdown_controls(self):
        # Safe shutdown is part of Stop, not only application exit. For real
        # MFCs this currently performs no writes until gas control is approved.
        shutdown = getattr(self.mfc, "safe_shutdown", None)
        if shutdown is None:
            return

        try:
            shutdown()
            state = self.current_state()
            if self.mfc_mode == "simulation":
                channels = getattr(state, "mfc_channels", ())
                if any(channel.setpoint_sccm != 0 for channel in channels):
                    raise RuntimeError("Simulated MFC setpoints did not reset to zero.")
            self.state_changed.emit(state)
        except Exception as exc:
            self.handle_device_error("Safe shutdown failed", exc)

    def close(self):
        self.acquisition_timer.stop()
        self.elapsed_timer.stop()
        self.invalidate_control_timers()
        self.stop_recipe_execution()
        self.safe_shutdown_controls()

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
        if text:
            self.pending_events.append(text)

    def consume_pending_events(self):
        event = "; ".join(self.pending_events)
        self.pending_events = []
        return event

    def next_control_timer_token(self, name):
        self.control_timer_tokens[name] += 1
        return self.control_timer_tokens[name]

    def control_timer_is_current(self, name, token):
        return self.control_timer_tokens.get(name) == token

    def invalidate_control_timers(self):
        for name in self.control_timer_tokens:
            self.control_timer_tokens[name] += 1

    def apply_nh3(self, flow_sccm, duration_ms=0):
        if not self.safe_command("Set analyte flow failed", self.mfc.set_nh3_flow, flow_sccm):
            return

        token = self.next_control_timer_token("analyte")
        self.set_event(f"Set analyte flow = {flow_sccm} sccm")
        self.emit_state_changed()

        if duration_ms > 0:
            QTimer.singleShot(duration_ms, lambda token=token: self.reset_nh3(token))

    def reset_nh3(self, timer_token=None):
        if timer_token is not None and not self.control_timer_is_current("analyte", timer_token):
            return

        if not self.safe_command("Reset analyte flow failed", self.mfc.set_nh3_flow, 0):
            return

        self.set_event("Analyte duration ended")
        self.emit_state_changed()

    def apply_air(self, flow_sccm):
        if not self.safe_command("Set Air flow failed", self.mfc.set_air_flow, flow_sccm):
            return

        self.set_event(f"Set Air flow = {flow_sccm} sccm")
        self.emit_state_changed()

    def air_purge(self):
        if not self.safe_command("Air purge failed", self.mfc.air_purge):
            return

        self.next_control_timer_token("analyte")
        self.set_event("Air purge")
        self.emit_state_changed()

    def set_humidity(self, enabled, duration_ms=0):
        if not self.safe_command("Set humidity failed", self.mfc.set_humidity, enabled):
            return False

        token = self.next_control_timer_token("humidity")
        state = "ON" if enabled else "OFF"
        self.set_event(f"Humidity {state}")
        self.emit_state_changed()

        if enabled and duration_ms > 0:
            QTimer.singleShot(duration_ms, lambda token=token: self.expire_humidity(token))
        return True

    def expire_humidity(self, timer_token):
        if self.control_timer_is_current("humidity", timer_token):
            self.set_humidity(False)

    def set_heating(self, enabled, duration_ms=0):
        if not self.safe_command("Set heating failed", self.mfc.set_heating, enabled):
            return False

        token = self.next_control_timer_token("heating")
        state = "ON" if enabled else "OFF"
        self.set_event(f"Heating {state}")
        self.emit_state_changed()

        if enabled and duration_ms > 0:
            QTimer.singleShot(duration_ms, lambda token=token: self.expire_heating(token))
        return True

    def expire_heating(self, timer_token):
        if self.control_timer_is_current("heating", timer_token):
            self.set_heating(False)

    def acquire_once(self):
        # Acquisition order matters: read the control state first, then attach
        # the same state snapshot to the multimeter record and logger row.
        try:
            state = self.mfc.get_state()
        except Exception as exc:
            message = self.format_device_error(
                "MFC controller connection lost during read",
                exc,
            )
            self.handle_device_error_message(message)
            self.write_error_record(message)
            self.stop_experiment("Stopped: MFC connection lost")
            return

        try:
            record = self.multimeter.read(state)
            record.event = "; ".join(self.pending_events)
        except Exception as exc:
            message = self.format_device_error(
                "Multimeter connection lost during measurement",
                exc,
            )
            self.handle_device_error_message(message)
            self.write_error_record(message, state)
            self.stop_experiment("Stopped: multimeter connection lost")
            return

        if self.logger is not None:
            try:
                self.logger.write(record)
            except Exception as exc:
                self.handle_device_error("Logger write failed", exc)
                self.stop_experiment("Stopped: logger write failed")
                return

        event = self.consume_pending_events()
        record.event = event
        # Events are one-shot annotations. The next row should be blank unless
        # another user action or device error occurs.
        self.state_changed.emit(state)
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
        self.set_event(message)
        self.device_error.emit(message)

    @staticmethod
    def format_device_error(context, exc):
        detail = str(exc).strip()
        if detail:
            return f"{context}. Details: {detail}"
        return context

    def write_error_record(self, message, state=None):
        # Write one final row when a device fails mid-run. NaN readings make the
        # failure visible in analysis without pretending a measurement happened.
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
            mfc_channels=state.mfc_channels if state is not None else (),
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
