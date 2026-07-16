import math
from dataclasses import dataclass

from gas_sensor_daq.models.records import ControlState, MFCChannelState


RAW_FULL_SCALE = 32000.0


@dataclass(frozen=True)
class MFCRackDiscovery:
    port: str
    addresses: tuple[int, ...]
    serials: tuple[str, ...]
    verified: bool
    message: str


class ProparMFCRack:
    """Read-only connection to the six verified MFCs on one propar bus."""

    DDE_PARAMETERS = {
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

    def __init__(self, port, baudrate, expected_nodes):
        self.port = port
        self.baudrate = int(baudrate)
        self.expected_nodes = tuple(expected_nodes)
        self.master = None
        self.nodes_by_address = {}
        self.channel_metadata = {}
        self.connect()

    @classmethod
    def discover(cls, baudrate, expected_nodes, ports):
        discoveries = []
        for port in ports:
            master = None
            try:
                master = cls._open_master(port, baudrate)
                nodes = master.get_nodes()
                addresses = tuple(sorted(node.get("address") for node in nodes))
                serials = tuple(
                    node.get("serial", "")
                    for node in sorted(nodes, key=lambda node: node.get("address", -1))
                )
                verified, message = cls._verify_nodes(nodes, expected_nodes)
                discoveries.append(MFCRackDiscovery(
                    port=port,
                    addresses=addresses,
                    serials=serials,
                    verified=verified,
                    message=message,
                ))
            except Exception as exc:
                discoveries.append(MFCRackDiscovery(
                    port=port,
                    addresses=(),
                    serials=(),
                    verified=False,
                    message=str(exc),
                ))
            finally:
                cls._stop_master(master)
        return discoveries

    @classmethod
    def discover_serial_ports(cls, baudrate, expected_nodes):
        try:
            from serial.tools import list_ports
        except ImportError as exc:
            raise ConnectionError("pyserial is required to scan MFC COM ports.") from exc

        ports = [port.device for port in list_ports.comports()]
        return cls.discover(baudrate, expected_nodes, ports)

    def connect(self):
        try:
            self.master = self._open_master(self.port, self.baudrate)
            nodes = self.master.get_nodes()
            verified, message = self._verify_nodes(nodes, self.expected_nodes)
            if not verified:
                raise ConnectionError(message)

            self.nodes_by_address = {node["address"]: node for node in nodes}
            self._read_channel_metadata()
        except Exception:
            self.close()
            raise

    def get_state(self):
        channels = self.read_channels()
        primary = channels[0]
        return ControlState(
            # Legacy fields keep the existing UI functional until its six-MFC
            # monitor replaces the old NH3/Air controls in the next stage.
            air_setpoint_sccm=primary.setpoint_sccm,
            air_actual_sccm=primary.actual_sccm,
            device_status=self.status_text(),
            mfc_port=self.port,
            mfc_address=",".join(str(channel.address) for channel in channels),
            mfc_serial=primary.serial,
            mfc_fluid=primary.fluid_name,
            mfc_capacity_sccm=primary.capacity_sccm,
            mfc_capacity_unit=primary.capacity_unit,
            mfc_temperature_c=primary.temperature_c,
            mfc_alarm_info=primary.alarm_info,
            mfc_channels=channels,
        )

    def read_channels(self):
        self._ensure_connected()
        channels = []
        for index, expected in enumerate(self.expected_nodes, start=1):
            address = expected.address
            metadata = self.channel_metadata[address]
            measure = self._read_flow(address, "fmeasure", "measure_raw", metadata["capacity"])
            setpoint = self._read_flow(address, "fsetpoint", "setpoint_raw", metadata["capacity"])
            temperature = self._read_float(address, "temperature")
            alarm_info = self._read_value(address, "alarm_info")
            alarm_text = "" if alarm_info in (None, 0, "0") else str(alarm_info)
            channels.append(MFCChannelState(
                index=index,
                address=address,
                serial=metadata["serial"],
                fluid_name=metadata["fluid_name"],
                capacity_sccm=metadata["capacity"],
                capacity_unit=metadata["capacity_unit"],
                setpoint_sccm=setpoint,
                actual_sccm=measure,
                temperature_c=self._finite_or_zero(temperature),
                alarm_info=alarm_text,
                status="ALARM" if alarm_text else "OK",
            ))
        return tuple(channels)

    def set_nh3_flow(self, value_sccm):
        raise ConnectionError("MFC rack is connected read-only; setpoint writes are disabled.")

    def set_air_flow(self, value_sccm):
        raise ConnectionError("MFC rack is connected read-only; setpoint writes are disabled.")

    def air_purge(self):
        raise ConnectionError("MFC rack is connected read-only; purge writes are disabled.")

    def set_humidity(self, enabled):
        raise ConnectionError("Humidity controller is not connected to the MFC rack.")

    def set_heating(self, enabled):
        raise ConnectionError("Heating controller is not connected to the MFC rack.")

    def safe_shutdown(self):
        # Read-only mode must never write a setpoint or change a controller mode.
        return

    def status_text(self):
        return f"PROPAR MFC RACK READ-ONLY | {self.port} | {len(self.expected_nodes)}/6 verified"

    def close(self):
        self._stop_master(self.master)
        self.master = None
        self.nodes_by_address = {}
        self.channel_metadata = {}

    def _read_channel_metadata(self):
        for expected in self.expected_nodes:
            address = expected.address
            node = self.nodes_by_address[address]
            self.channel_metadata[address] = {
                "serial": node.get("serial", ""),
                "capacity": self._finite_or_zero(self._read_float(address, "capacity")),
                "capacity_unit": str(self._read_value(address, "capacity_unit") or "").strip(),
                "fluid_name": str(self._read_value(address, "fluid_name") or "").strip(),
            }

    def _read_flow(self, address, normalized_name, raw_name, capacity):
        value = self._read_float(address, normalized_name)
        if math.isfinite(value):
            return value
        raw_value = self._read_float(address, raw_name)
        if not math.isfinite(raw_value):
            return 0.0
        return self._finite_or_zero(raw_value / RAW_FULL_SCALE * capacity)

    def _read_value(self, address, name):
        parameter = self.master.db.get_parameter(self.DDE_PARAMETERS[name])
        request = {
            "node": address,
            "proc_nr": parameter["proc_nr"],
            "parm_nr": parameter["parm_nr"],
            "parm_type": parameter["parm_type"],
            "parm_name": parameter["parm_name"],
        }
        if "parm_size" in parameter:
            request["parm_size"] = parameter["parm_size"]

        response = self.master.read_parameters([request])
        if not response or response[0].get("status") != 0:
            return None

        value = response[0].get("data")
        if isinstance(value, bytes):
            return value.decode(errors="replace").strip("\x00")
        if isinstance(value, str):
            return value.strip("\x00")
        return value

    def _read_float(self, address, name):
        try:
            return float(self._read_value(address, name))
        except (TypeError, ValueError):
            return math.nan

    def _ensure_connected(self):
        if self.master is None or not self.nodes_by_address:
            raise ConnectionError("MFC rack is not connected.")

    @staticmethod
    def _verify_nodes(nodes, expected_nodes):
        expected_by_address = {node.address: node.serial for node in expected_nodes}
        found_by_address = {node.get("address"): node.get("serial", "") for node in nodes}
        if set(found_by_address) != set(expected_by_address):
            found = ", ".join(str(address) for address in sorted(found_by_address)) or "none"
            expected = ", ".join(str(address) for address in sorted(expected_by_address))
            return False, f"MFC rack address mismatch: found [{found}], expected [{expected}]."

        mismatches = [
            f"addr {address}: {found_by_address[address]}"
            for address, serial in expected_by_address.items()
            if found_by_address[address] != serial
        ]
        if mismatches:
            return False, "MFC rack serial mismatch: " + "; ".join(mismatches)
        return True, "6/6 MFC nodes verified"

    @staticmethod
    def _open_master(port, baudrate):
        try:
            import propar
        except ImportError as exc:
            raise ConnectionError("propar MFC support is not installed. Install requirements first.") from exc
        try:
            return propar.master(port, baudrate)
        except Exception as exc:
            if "Access is denied" in str(exc):
                raise ConnectionError(f"{port} is busy. Close other app using this COM port.") from exc
            raise

    @staticmethod
    def _stop_master(master):
        if master is not None:
            try:
                master.stop()
            except Exception:
                pass

    @staticmethod
    def _finite_or_zero(value):
        return value if math.isfinite(value) else 0.0
