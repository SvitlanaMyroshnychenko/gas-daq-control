from datetime import datetime
import math
import os
import time

from PySide6.QtCore import QObject, QTimer, Signal

from gas_sensor_daq.devices.factory import create_devices, create_mfc, create_multimeter
from gas_sensor_daq.devices.propar_mfc_rack import ProparMFCRack
from gas_sensor_daq.core.experiment_design import flow_matches_target
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
    multimeter_2_changed = Signal(str, str)
    mfc_changed = Signal(str, str)
    recipe_step_changed = Signal(int)
    flow_warning = Signal(str)

    ACTUAL_FLOW_SETTLE_SECONDS = 6.0
    ACTUAL_FLOW_MIN_TOLERANCE = 1.0
    ACTUAL_FLOW_REL_TOLERANCE = 0.10
    STOP_FLOW_VERIFY_INTERVAL_MS = 1000
    STOP_FLOW_VERIFY_ATTEMPTS = 15
    STOP_FLOW_ZERO_TOLERANCE = 0.5

    def __init__(self, parent=None, settings=DEFAULT_SETTINGS):
        super().__init__(parent)
        self.settings = settings
        self.multimeter, self.mfc = create_devices(settings)
        self.multimeter_mode = settings.multimeter_mode
        self.mfc_mode = settings.mfc_mode
        self.multimeter_resource = settings.multimeter_resource

        self.multimeter_2_mode = settings.multimeter_2_mode
        self.multimeter_2_resource = settings.multimeter_2_resource
        self.multimeter_2 = None

        if self.multimeter_2_mode != "disabled":
            self.multimeter_2 = create_multimeter(
                settings,
                mode=self.multimeter_2_mode,
                resource_name=self.multimeter_2_resource,
            )

        self.mfc_port = settings.mfc_port
        self.data_directory = settings.data_directory
        self.acquisition_interval_ms = settings.acquisition_interval_ms
        self.logger = None
        self.pending_events = []
        self.active_event = ""
        self.experiment_start_time = None

        self.acquisition_timer = QTimer(self)
        self.acquisition_timer.timeout.connect(self.acquire_once)

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)

        self.recipe_steps = ()
        self.recipe_step_index = -1
        self.recipe_step_started_monotonic = None
        self.actual_flow_warning_emitted = False
        self.recipe_timer = QTimer(self)
        self.recipe_timer.setSingleShot(True)
        self.recipe_timer.timeout.connect(self.advance_recipe)

        self.stop_flow_verify_attempts = 0
        self.stop_flow_verify_timer = QTimer(self)
        self.stop_flow_verify_timer.setInterval(self.STOP_FLOW_VERIFY_INTERVAL_MS)
        self.stop_flow_verify_timer.timeout.connect(self.verify_stopped_mfc_flow)

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

    def set_multimeter_2_mode(self, mode, resource_name=""):
        if self.acquisition_timer.isActive():
            self.handle_device_error(
                "Cannot switch second multimeter",
                RuntimeError("Stop the experiment before changing device mode."),
            )
            return False

        mode = str(mode).strip().lower()
        resource_name = str(resource_name).strip()
        if mode not in {"disabled", "simulation", "real"}:
            self.handle_device_error(
                "Second multimeter configuration failed",
                ValueError(f"Unsupported mode: {mode}"),
            )
            return False

        if (
                mode == "real"
                and self.multimeter_mode == "real"
                and resource_name == self.multimeter_resource
        ):
            self.handle_device_error(
                "Second multimeter configuration failed",
                ValueError("Each multimeter must use a different VISA resource."),
            )
            return False

        previous_multimeter = self.multimeter_2

        try:
            new_multimeter = (
                None
                if mode == "disabled"
                else create_multimeter(
                    self.settings,
                    mode=mode,
                    resource_name=resource_name,
                )
            )
        except Exception as exc:
            self.handle_device_error("Second multimeter connection failed", exc)
            return False

        self.multimeter_2 = new_multimeter
        self.multimeter_2_mode = mode
        self.multimeter_2_resource = resource_name
        self._close_device(previous_multimeter, "Previous second multimeter close failed")
        self.multimeter_2_changed.emit(mode, self.multimeter_2_status_text())
        return True

    def multimeter_2_status_text(self):
        if self.multimeter_2_mode == "disabled":
            return "Multimeter 2: disabled"

        if self.multimeter_2_mode == "real":
            return f"Multimeter 2: real ({self.multimeter_2_resource})"

        return "Multimeter 2: simulated"

    def set_mfc_mode(self, mode, port=""):
        # If a real MFC connection fails, fall back to simulation. This keeps
        # the UI usable without leaving a half-connected hardware object alive.
        if self.acquisition_timer.isActive():
            self.handle_device_error(
                "Cannot switch MFC",
                RuntimeError("Stop the experiment before changing device mode."),
            )
            return False

        self.stop_flow_verify_timer.stop()
        previous_mfc = self.mfc
        self._close_device(previous_mfc, "Previous MFC close failed")

        try:
            new_mfc = create_mfc(
                self.settings,
                mode=mode,
                port=port or self.settings.mfc_port,
            )
        except Exception as exc:
            self.mfc = create_mfc(self.settings, mode="simulation")
            self.mfc_mode = "simulation"
            self.mfc_changed.emit("simulation", self.mfc_status_text())
            self.handle_device_error("MFC connection failed", exc)
            return False

        self.mfc = new_mfc
        self.mfc_mode = mode
        self.mfc_port = port or self.settings.mfc_port
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

    def start_experiment(
        self,
        save_format,
        data_directory=None,
        filename_stem="experiment",
        experiment_metadata=None,
    ):
        selected_directory = str(data_directory or self.data_directory).strip()
        if not selected_directory:
            raise ValueError("Choose a save location before starting the experiment.")

        try:
            self.stop_flow_verify_timer.stop()
            # Every Start creates a fresh experiment file. Resume/append would
            # need explicit metadata handling and is intentionally not implicit.
            self.multimeter.reset_time()
            if self.multimeter_2 is not None:
                self.multimeter_2.reset_time()
            self.pending_events = []
            self.active_event = ""
            self.experiment_start_time = datetime.now()
            self.data_directory = selected_directory
            os.makedirs(self.data_directory, exist_ok=True)

            stem = self.sanitize_filename_stem(filename_stem)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            base_filename = f"{stem}_{timestamp}"
            metadata = self.build_experiment_metadata(
                save_format,
                base_filename,
                experiment_metadata or {},
            )
            if save_format == "CSV":
                filename = os.path.join(self.data_directory, f"{base_filename}.csv")
                self.logger = CSVLogger(filename, metadata)
            else:
                filename = os.path.join(self.data_directory, f"{base_filename}.xlsx")
                self.logger = ExcelLogger(filename, metadata)

            self.acquisition_timer.start(self.acquisition_interval_ms)
            self.elapsed_timer.start(1000)
            self.experiment_started.emit(filename)
            self.elapsed_changed.emit("00:00:00")
        except Exception as exc:
            self.handle_device_error("Experiment start failed", exc)
            self.stop_experiment("Experiment start failed")

    def validate_recipe_start(self, steps):
        """Validate a schedule and, for hardware, perform a no-write preflight."""
        if not steps:
            raise ValueError("Add at least one experiment step.")
        self.validate_recipe(steps)
        if self.mfc_mode == "real":
            if not isinstance(self.mfc, ProparMFCRack):
                raise ValueError("Connect a verified six-node MFC rack before starting.")
            self.mfc.validate_recipe_start_ready()

    def start_recipe(self, steps):
        if not steps:
            return False

        try:
            self.validate_recipe_start(steps)
        except Exception as exc:
            self.handle_device_error("Experiment schedule validation failed", exc)
            return False

        self.stop_recipe_execution()
        self.recipe_steps = tuple(steps)
        self.recipe_step_index = 0
        self.apply_current_recipe_step()
        return True

    def validate_recipe(self, steps):
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
                        f"0 and {capacity:g} mln/min."
                    )
                channel_total += value

            total_setpoint = float(step.get("total_setpoint_mln_min", math.nan))
            if not math.isfinite(total_setpoint) or not math.isclose(
                total_setpoint, channel_total, rel_tol=0, abs_tol=0.01
            ):
                raise ValueError(
                    f"Step {step_index} step total must equal the sum of MFC setpoints."
                )
            target_total = float(step.get("target_total_mln_min", math.nan))
            if not math.isfinite(target_total) or not flow_matches_target(
                channel_total, target_total
            ):
                raise ValueError(
                    f"Step {step_index} total must equal the {target_total:g} mln/min target flow."
                )
            duration_ms = step.get("duration_ms", 0)
            if not isinstance(duration_ms, (int, float)) or duration_ms <= 0:
                raise ValueError(f"Step {step_index} duration must be greater than zero.")

    def mfc_channel_capacity_sccm(self, channel_index):
        capacities = getattr(self.mfc, "channel_capacities", {})
        fallback = self.settings.mfc_nodes[channel_index - 1].capacity_mln_min
        return float(capacities.get(channel_index, fallback))

    def zero_real_mfc_setpoints(self):
        """Explicit emergency/manual zero command for the verified real rack."""
        if self.acquisition_timer.isActive():
            self.handle_device_error(
                "Zero all MFCs blocked",
                RuntimeError("Stop the experiment before using the manual MFC controls."),
            )
            return None
        if self.mfc_mode != "real" or not isinstance(self.mfc, ProparMFCRack):
            self.handle_device_error(
                "Zero all MFCs blocked",
                RuntimeError("Connect a verified real six-node MFC rack first."),
            )
            return None
        try:
            state = self.mfc.zero_all_setpoints()
        except Exception as exc:
            self.handle_device_error("Zero all MFCs failed", exc)
            return None
        self.state_changed.emit(state)
        return state

    def apply_current_recipe_step(self):
        if not 0 <= self.recipe_step_index < len(self.recipe_steps):
            return

        step = self.recipe_steps[self.recipe_step_index]
        try:
            self.mfc.set_channel_setpoints(step["setpoints"])
        except Exception as exc:
            self.handle_device_error("Apply experiment step failed", exc)
            self.stop_experiment("Stopped: experiment step could not be applied")
            return

        event_name = str(step.get("event_name", "")).strip()
        self.set_active_event(event_name or (
            f"Experiment step {self.recipe_step_index + 1}/{len(self.recipe_steps)}: "
            f"step total {step['total_setpoint_mln_min']:g} mln/min"
        ))
        self.recipe_step_started_monotonic = time.monotonic()
        self.actual_flow_warning_emitted = False
        self.emit_state_changed()
        self.recipe_step_changed.emit(self.recipe_step_index)
        self.recipe_timer.start(step["duration_ms"])

    def advance_recipe(self):
        self.recipe_step_index += 1
        if self.recipe_step_index < len(self.recipe_steps):
            self.apply_current_recipe_step()
            return

        # Completion uses the same shutdown path as the Stop button: zero the
        # MFCs, stop acquisition, close the output file, and notify the UI.
        self.stop_experiment("Experiment completed; MFC setpoints reset to zero")

    def stop_recipe_execution(self):
        self.recipe_timer.stop()
        self.recipe_steps = ()
        self.recipe_step_index = -1
        self.recipe_step_started_monotonic = None
        self.actual_flow_warning_emitted = False
        self.active_event = ""

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
        self.stop_recipe_execution()

        shutdown_ok = self.safe_shutdown_controls()
        if not shutdown_ok:
            message = (
                f"{message}. CRITICAL: MFC zero setpoints could not be confirmed; "
                "verify the rack immediately."
            )

        if self.logger is not None:
            try:
                self.logger.update_metadata(self.experiment_completion_metadata(message))
                self.logger.close()
            except Exception as exc:
                self.handle_device_error("Logger close failed", exc)
            self.logger = None

        self.experiment_stopped.emit(message)
        if shutdown_ok:
            self.start_stop_flow_verification()

    def build_experiment_metadata(self, save_format, base_filename, experiment_metadata):
        rate_hz = 1000 / self.acquisition_interval_ms
        channels = [
            {
                "index": index,
                "address": node.address,
                "serial": node.serial,
                "gas": node.gas_name,
                "capacity_mln_min": node.capacity_mln_min,
            }
            for index, node in enumerate(self.settings.mfc_nodes, start=1)
        ]
        metadata = dict(experiment_metadata)
        schedule = metadata.get("schedule")
        if isinstance(schedule, (list, tuple)):
            metadata["schedule"] = [
                {
                    "step_number": step_number,
                    **{
                        key: value
                        for key, value in step.items()
                        if key != "target_total_mln_min"
                    },
                }
                for step_number, step in enumerate(schedule, start=1)
            ]

        return {
            "schema_version": 4,
            "data_file_stem": base_filename,
            "format": save_format,
            "started_at": self.experiment_start_time.isoformat(timespec="seconds"),
            "sampling_rate_hz": rate_hz,
            "multimeter_mode": self.multimeter_mode,
            "multimeter_resource": (
                self.multimeter_resource if self.multimeter_mode == "real" else ""
            ),
            "multimeter_2_mode": self.multimeter_2_mode,
            "multimeter_2_resource": (
                self.multimeter_2_resource
                if self.multimeter_2_mode == "real"
                else ""
            ),
            "mfc_mode": self.mfc_mode,
            "mfc_port": self.mfc_port if self.mfc_mode == "real" else "",
            "mfc_channels": channels,
            **metadata,
        }

    @staticmethod
    def experiment_completion_metadata(message):
        text = str(message or "").strip()
        lower = text.lower()
        if lower.startswith("experiment completed"):
            reason = "completed"
        elif "error" in lower or "failed" in lower or "critical" in lower:
            reason = "error"
        else:
            reason = "stopped"

        metadata = {
            "ended_at": datetime.now().isoformat(timespec="seconds"),
            "end_reason": reason,
        }
        if reason == "error" and text:
            metadata["error_message"] = text
        return metadata

    def safe_shutdown_controls(self):
        # Safe shutdown is part of Stop, not only application exit.
        shutdown = getattr(self.mfc, "safe_shutdown", None)
        if shutdown is None:
            return True

        try:
            shutdown()
            state = self.current_state()
            if self.mfc_mode == "simulation":
                channels = getattr(state, "mfc_channels", ())
                if any(channel.setpoint_sccm != 0 for channel in channels):
                    raise RuntimeError("Simulated MFC setpoints did not reset to zero.")
            self.state_changed.emit(state)
            return True
        except Exception as exc:
            self.handle_device_error("Safe shutdown failed", exc)
            return False

    def start_stop_flow_verification(self):
        """Monitor actual MFC flow briefly after a confirmed zero-setpoint command."""
        self.stop_flow_verify_timer.stop()
        self.stop_flow_verify_attempts = 0
        self.stop_flow_verify_timer.start()

    def verify_stopped_mfc_flow(self):
        self.stop_flow_verify_attempts += 1
        try:
            state = self.current_state()
        except Exception:
            self.stop_flow_verify_timer.stop()
            return

        self.state_changed.emit(state)
        residual = self.residual_mfc_flows(state)
        if not residual:
            self.stop_flow_verify_timer.stop()
            return

        if self.stop_flow_verify_attempts < self.STOP_FLOW_VERIFY_ATTEMPTS:
            return

        self.stop_flow_verify_timer.stop()
        channels = ", ".join(
            f"MFC {index}: {flow:.2f} mln/min" for index, flow in residual
        )
        self.flow_warning.emit(
            "MFC setpoints were reset to zero, but actual flow remains after "
            f"{self.STOP_FLOW_VERIFY_ATTEMPTS} seconds: {channels}. "
            "Verify the gas rack and outlet."
        )

    def residual_mfc_flows(self, state):
        return [
            (channel.index, channel.actual_sccm)
            for channel in getattr(state, "mfc_channels", ())
            if channel.actual_sccm > self.STOP_FLOW_ZERO_TOLERANCE
        ]

    def close(self):
        self.acquisition_timer.stop()
        self.elapsed_timer.stop()
        self.stop_flow_verify_timer.stop()
        self.stop_recipe_execution()
        if not self.safe_shutdown_controls():
            message = "Stopped with MFC zeroing error; verify the rack immediately"

        if self.logger is not None:
            try:
                self.logger.update_metadata({
                    "ended_at": datetime.now().isoformat(timespec="seconds"),
                    "end_reason": "application_closed",
                })
                self.logger.close()
            except Exception as exc:
                self.handle_device_error("Logger close failed", exc)
            self.logger = None

        self._close_device(self.multimeter, "Multimeter close failed")
        self._close_device(self.multimeter_2, "Second multimeter close failed")
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

    def set_active_event(self, text):
        """Set the schedule event persisted in every acquisition row."""
        self.active_event = str(text).strip()
        if self.active_event:
            self.set_event(self.active_event)

    def consume_pending_events(self):
        event = "; ".join(self.pending_events)
        self.pending_events = []
        return event

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

        alarms = self.active_mfc_alarms(state)
        if alarms:
            message = "MFC alarm detected during experiment: " + ", ".join(alarms)
            self.handle_device_error_message(message)
            self.write_error_record(message, state)
            self.stop_experiment("Stopped: MFC alarm; setpoints reset to zero")
            return

        try:
            record = self.multimeter.read(state)
        except Exception as exc:
            message = self.format_device_error(
                "First multimeter connection lost during measurement",
                exc,
            )
            self.handle_device_error_message(message)
            self.write_error_record(message, state, failed_multimeter=1)
            self.stop_experiment("Stopped: first multimeter connection lost")
            return

        if self.multimeter_2 is not None:
            try:
                second_record = self.multimeter_2.read(state)
            except Exception as exc:
                message = self.format_device_error(
                    "Second multimeter connection lost during measurement",
                    exc,
                )
                self.handle_device_error_message(message)
                self.write_error_record(message, state, failed_multimeter=2)
                self.stop_experiment("Stopped: second multimeter connection lost")
                return

            record.resistance_2_ohm = second_record.resistance_ohm
            record.multimeter_2_status = second_record.multimeter_status

        record.event = self.active_event
        record.step_number = (
            self.recipe_step_index + 1 if self.recipe_step_index >= 0 else None
        )
        channels = state.mfc_channels
        record.total_setpoint_mln_min = sum(
            channel.setpoint_sccm for channel in channels
        )
        record.total_actual_mln_min = sum(
            channel.actual_sccm for channel in channels
        )
        self.check_actual_total_flow(record)

        if self.logger is not None:
            try:
                self.logger.write(record)
            except Exception as exc:
                self.handle_device_error("Logger write failed", exc)
                self.stop_experiment("Stopped: logger write failed")
                return

        event = self.consume_pending_events()
        self.state_changed.emit(state)
        self.data_acquired.emit(record.to_dict(), event)

    @staticmethod
    def active_mfc_alarms(state):
        """Return human-readable alarms from one six-channel state snapshot."""
        return [
            f"MFC {channel.index}" + (
                f" ({channel.alarm_info})" if channel.alarm_info else ""
            )
            for channel in getattr(state, "mfc_channels", ())
            if channel.alarm_info or str(channel.status).upper() == "ALARM"
        ]

    def check_actual_total_flow(self, record):
        """Warn once per step after settling when readback differs materially.

        This is intentionally informational: an automatic stop tolerance must
        be agreed with the laboratory after observing the real installation.
        """
        if (
            self.recipe_step_index < 0
            or self.recipe_step_started_monotonic is None
            or self.actual_flow_warning_emitted
        ):
            return
        if time.monotonic() - self.recipe_step_started_monotonic < self.ACTUAL_FLOW_SETTLE_SECONDS:
            return

        expected = float(record.total_setpoint_mln_min)
        actual = float(record.total_actual_mln_min)
        if expected <= 0:
            return
        tolerance = max(
            self.ACTUAL_FLOW_MIN_TOLERANCE,
            expected * self.ACTUAL_FLOW_REL_TOLERANCE,
        )
        difference = abs(actual - expected)
        if difference <= tolerance:
            return

        self.actual_flow_warning_emitted = True
        self.flow_warning.emit(
            f"Actual total flow {actual:.2f} mln/min differs from setpoint "
            f"{expected:.2f} mln/min by {difference:.2f} mln/min "
            f"(warning threshold {tolerance:.2f} mln/min)."
        )

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

    def write_error_record(self, message, state=None, failed_multimeter=None):
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
            resistance_2_ohm=(
                math.nan if self.multimeter_2 is not None else None
            ),
            event=message,
            multimeter_status="ERROR",
            multimeter_2_status=(
                "Disabled"
                if self.multimeter_2 is None
                else (
                    "ERROR"
                    if failed_multimeter == 2
                    else (
                        "Real"
                        if self.multimeter_2_mode == "real"
                        else "Simulated"
                    )
                )
            ),
            mfc_channels=state.mfc_channels if state is not None else (),
            step_number=(self.recipe_step_index + 1 if self.recipe_step_index >= 0 else None),
            total_setpoint_mln_min=sum(
                channel.setpoint_sccm for channel in (state.mfc_channels if state else ())
            ),
            total_actual_mln_min=sum(
                channel.actual_sccm for channel in (state.mfc_channels if state else ())
            ),
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
