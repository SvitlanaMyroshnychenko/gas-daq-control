from dataclasses import asdict, dataclass


FIELDNAMES = [
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
    "device_status",
]


@dataclass
class ControlState:
    nh3_setpoint_sccm: float = 0.0
    nh3_actual_sccm: float = 0.0
    air_setpoint_sccm: float = 100.0
    air_actual_sccm: float = 100.0
    humidity_on: bool = False
    heating_on: bool = False
    device_status: str = "Simulated"

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
    device_status: str = "Simulated"

    def to_dict(self):
        return asdict(self)

