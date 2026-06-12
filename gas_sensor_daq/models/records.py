from dataclasses import asdict, dataclass


FIELDNAMES = [
    # This list is the logging contract. Add new columns here first, then make
    # sure MeasurementRecord fills them for both simulated and real devices.
    "timestamp",
    "elapsed_s",
    "resistance_ohm",
    "temperature_c",
    "nh3_flow_sccm",
    "air_flow_sccm",
    "humidity_on",
    "heating_on",
    "event",
    "nh3_setpoint_sccm",
    "nh3_actual_sccm",
    "air_setpoint_sccm",
    "air_actual_sccm",
    "multimeter_status",
    "mfc_status",
    "mfc_port",
    "mfc_address",
    "mfc_serial",
    "mfc_fluid",
    "mfc_capacity_sccm",
    "mfc_capacity_unit",
    "mfc_temperature_c",
    "mfc_alarm_info",
]


@dataclass
class ControlState:
    """Current gas/environment state used by both fake and real MFC adapters."""

    nh3_setpoint_sccm: float = 0.0
    nh3_actual_sccm: float = 0.0
    air_setpoint_sccm: float = 100.0
    air_actual_sccm: float = 100.0
    humidity_on: bool = False
    heating_on: bool = False
    device_status: str = "Simulated"
    mfc_port: str = ""
    mfc_address: str = ""
    mfc_serial: str = ""
    mfc_fluid: str = ""
    mfc_capacity_sccm: float = 0.0
    mfc_capacity_unit: str = ""
    mfc_temperature_c: float = 0.0
    mfc_alarm_info: str = ""

    @property
    def nh3_flow_sccm(self):
        return self.nh3_actual_sccm

    @property
    def air_flow_sccm(self):
        return self.air_actual_sccm

    def to_sensor_state(self):
        return {
            "nh3_flow": self.nh3_actual_sccm,
            "air_flow": self.air_actual_sccm,
            "humidity_on": self.humidity_on,
            "heating_on": self.heating_on,
        }

    def to_dict(self):
        return asdict(self) | {
            "nh3_flow_sccm": self.nh3_flow_sccm,
            "air_flow_sccm": self.air_flow_sccm,
        }


@dataclass
class MeasurementRecord:
    """One row of experiment data written to CSV/Excel and shown in preview."""

    timestamp: str
    elapsed_s: float
    resistance_ohm: float
    temperature_c: float
    nh3_flow_sccm: float
    air_flow_sccm: float
    humidity_on: bool
    heating_on: bool
    event: str = ""
    nh3_setpoint_sccm: float = 0.0
    nh3_actual_sccm: float = 0.0
    air_setpoint_sccm: float = 100.0
    air_actual_sccm: float = 100.0
    multimeter_status: str = "Simulated"
    mfc_status: str = "Simulated"
    mfc_port: str = ""
    mfc_address: str = ""
    mfc_serial: str = ""
    mfc_fluid: str = ""
    mfc_capacity_sccm: float = 0.0
    mfc_capacity_unit: str = ""
    mfc_temperature_c: float = 0.0
    mfc_alarm_info: str = ""

    def to_dict(self):
        return asdict(self)
