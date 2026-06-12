import math

from gas_sensor_daq.models.records import ControlState


RAW_FULL_SCALE = 32000.0


class ProparMFCController:
    """Read-only propar MFC integration.

    This class intentionally does not write setpoints yet. It is safe for
    connection checks and live monitoring while gas hardware is not ready.
    """

    DDE_PARAMETERS = {
        # DDE parameter numbers are Bronkhorst/propar protocol metadata. Keep
        # them centralized here so future write support can be reviewed safely.
        "measure_raw": 8,
        "setpoint_raw": 9,
        "capacity": 21,
        "fluid_name": 25,
        "alarm_info": 28,
        "capacity_unit": 129,
        "temperature": 142,
        "fmeasure": 205,
        "fsetpoint": 206,
    }

    def __init__(
        self,
        port="COM3",
        baudrate=38400,
        address=None,
        default_air_flow_sccm=100.0,
    ):
        self.port = port
        self.baudrate = int(baudrate)
        self.requested_address = address
        self.default_air_flow_sccm = float(default_air_flow_sccm)
        self.master = None
        self.nodes = []
        self.address = None
        self.serial = ""
        self.device_type = ""
        self.capacity = math.nan
        self.capacity_unit = ""
        self.fluid_name = ""
        self.last_temperature_c = math.nan
        self.last_alarm_info = None
        self.connect()

    def connect(self):
        try:
            import propar
        except ImportError as exc:
            raise ConnectionError(
                "propar MFC support is not installed. Install requirements first."
            ) from exc

        try:
            self.master = propar.master(self.port, self.baudrate)
            self.nodes = self.master.get_nodes()
        except Exception as exc:
            self.close()
            if "Access is denied" in str(exc):
                raise ConnectionError(
                    f"{self.port} is busy. Close other app/test script using this COM port."
                ) from exc
            raise

        if not self.nodes:
            self.close()
            raise ConnectionError(f"No propar MFC instruments found on {self.port}.")

        node = self._select_node()
        self.address = node["address"]
        self.serial = node.get("serial", "")
        self.device_type = node.get("type", "")
        self._read_static_metadata()

    def get_state(self):
        self._ensure_connected()

        # Prefer normalized flow values when the controller exposes them. Fall
        # back to raw 0..32000 values scaled by capacity for older devices.
        measure = self._read_float("fmeasure")
        setpoint = self._read_float("fsetpoint")

        if not math.isfinite(measure):
            measure = self._raw_to_capacity(self._read_float("measure_raw"))
        if not math.isfinite(setpoint):
            setpoint = self._raw_to_capacity(self._read_float("setpoint_raw"))

        self.last_temperature_c = self._read_float("temperature")
        self.last_alarm_info = self._read_value("alarm_info")

        state = ControlState(
            # Until full channel mapping exists, a real MFC row represents the
            # detected channel only; other flows stay at their safe defaults.
            air_setpoint_sccm=self.default_air_flow_sccm,
            air_actual_sccm=self.default_air_flow_sccm,
            device_status=self.status_text(),
            mfc_port=self.port,
            mfc_address=str(self.address),
            mfc_serial=self.serial,
            mfc_fluid=self.fluid_name,
            mfc_capacity_sccm=self._finite_or_zero(self.capacity),
            mfc_capacity_unit=self.capacity_unit,
            mfc_temperature_c=self._finite_or_zero(self.last_temperature_c),
            mfc_alarm_info="" if self.last_alarm_info is None else str(self.last_alarm_info),
        )

        if self._is_air_channel():
            state.air_setpoint_sccm = self._finite_or_zero(setpoint)
            state.air_actual_sccm = self._finite_or_zero(measure)
        else:
            state.nh3_setpoint_sccm = self._finite_or_zero(setpoint)
            state.nh3_actual_sccm = self._finite_or_zero(measure)

        return state

    def set_nh3_flow(self, value_sccm):
        raise ConnectionError("MFC controller is connected read-only; setpoint writes are disabled.")

    def set_air_flow(self, value_sccm):
        raise ConnectionError("MFC controller is connected read-only; setpoint writes are disabled.")

    def air_purge(self):
        raise ConnectionError("MFC controller is connected read-only; purge writes are disabled.")

    def set_humidity(self, enabled):
        raise ConnectionError("Humidity controller is not connected to the real MFC interface.")

    def set_heating(self, enabled):
        raise ConnectionError("Heating controller is not connected to the real MFC interface.")

    def safe_shutdown(self):
        # The current real MFC integration is intentionally read-only.
        # Do not write setpoints here until gas testing and channel mapping are approved.
        return

    def status_text(self):
        parts = [
            f"PROPAR MFC READ-ONLY",
            f"{self.port}",
            f"addr {self.address}",
        ]
        if self.serial:
            parts.append(f"S/N {self.serial}")
        if self.fluid_name:
            parts.append(f"fluid {self.fluid_name}")
        if math.isfinite(self.capacity):
            unit = self.capacity_unit or "unit"
            parts.append(f"capacity {self.capacity:g} {unit}")
        if self.last_alarm_info not in (None, 0):
            parts.append(f"alarm {self.last_alarm_info}")
        return " | ".join(parts)

    def close(self):
        if self.master is not None:
            try:
                self.master.stop()
            except Exception:
                pass
            self.master = None

    def _select_node(self):
        if self.requested_address is None:
            return self.nodes[0]

        for node in self.nodes:
            if node.get("address") == self.requested_address:
                return node

        self.close()
        raise ConnectionError(
            f"MFC node address {self.requested_address} was not found on {self.port}."
        )

    def _read_static_metadata(self):
        self.capacity = self._read_float("capacity")
        self.capacity_unit = str(self._read_value("capacity_unit") or "").strip()
        self.fluid_name = str(self._read_value("fluid_name") or "").strip()

    def _read_value(self, name):
        parameter = self.master.db.get_parameter(self.DDE_PARAMETERS[name])
        request = {
            "node": self.address,
            "proc_nr": parameter["proc_nr"],
            "parm_nr": parameter["parm_nr"],
            "parm_type": parameter["parm_type"],
            "parm_name": parameter["parm_name"],
        }
        if "parm_size" in parameter:
            request["parm_size"] = parameter["parm_size"]

        response = self.master.read_parameters([request])
        if not response:
            return None

        result = response[0]
        if result.get("status") != 0:
            return None

        value = result.get("data")
        if isinstance(value, bytes):
            return value.decode(errors="replace").strip("\x00")
        if isinstance(value, str):
            return value.strip("\x00")
        return value

    def _read_float(self, name):
        value = self._read_value(name)
        try:
            return float(value)
        except (TypeError, ValueError):
            return math.nan

    def _raw_to_capacity(self, raw_value):
        if not math.isfinite(raw_value) or not math.isfinite(self.capacity):
            return math.nan
        return raw_value / RAW_FULL_SCALE * self.capacity

    def _is_air_channel(self):
        # Fluid names come from controller metadata and may include spaces or
        # vendor-specific spelling, so normalize before classifying the channel.
        return self.fluid_name.lower().replace(" ", "") in {"air", "airn2", "n2air"}

    def _ensure_connected(self):
        if self.master is None or self.address is None:
            raise ConnectionError("MFC controller is not connected.")

    @staticmethod
    def _finite_or_zero(value):
        return value if math.isfinite(value) else 0.0
