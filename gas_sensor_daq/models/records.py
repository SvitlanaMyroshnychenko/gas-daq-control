from dataclasses import asdict, dataclass


MFC_CHANNEL_COUNT = 6


def mfc_channel_fieldnames():
    fields = []
    for index in range(1, MFC_CHANNEL_COUNT + 1):
        prefix = f"mfc{index}_"
        fields.extend([
            f"{prefix}address",
            f"{prefix}serial",
            f"{prefix}fluid",
            f"{prefix}capacity_sccm",
            f"{prefix}capacity_unit",
            f"{prefix}setpoint_sccm",
            f"{prefix}actual_sccm",
            f"{prefix}temperature_c",
            f"{prefix}alarm_info",
            f"{prefix}status",
        ])
    return fields


FIELDNAMES = [
    # This list is the logging contract. Add new columns here first, then make
    # sure MeasurementRecord fills them for both simulated and real devices.
    "timestamp",
    "elapsed_s",
    "resistance_ohm",
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
    *mfc_channel_fieldnames(),
]


@dataclass(frozen=True)
class MFCChannelState:
    """Read-only snapshot of one MFC on the shared Bronkhorst bus."""

    index: int
    address: int
    serial: str = ""
    fluid_name: str = ""
    capacity_sccm: float = 0.0
    capacity_unit: str = ""
    setpoint_sccm: float = 0.0
    actual_sccm: float = 0.0
    temperature_c: float = 0.0
    alarm_info: str = ""
    status: str = ""

    def to_log_fields(self):
        prefix = f"mfc{self.index}_"
        return {
            f"{prefix}address": self.address,
            f"{prefix}serial": self.serial,
            f"{prefix}fluid": self.fluid_name,
            f"{prefix}capacity_sccm": self.capacity_sccm,
            f"{prefix}capacity_unit": self.capacity_unit,
            f"{prefix}setpoint_sccm": self.setpoint_sccm,
            f"{prefix}actual_sccm": self.actual_sccm,
            f"{prefix}temperature_c": self.temperature_c,
            f"{prefix}alarm_info": self.alarm_info,
            f"{prefix}status": self.status,
        }


def mfc_channel_log_fields(channels):
    fields = {field: "" for field in mfc_channel_fieldnames()}
    for channel in channels:
        if 1 <= channel.index <= MFC_CHANNEL_COUNT:
            fields.update(channel.to_log_fields())
    return fields


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
    mfc_channels: tuple[MFCChannelState, ...] = ()

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
        data = asdict(self)
        data.pop("mfc_channels", None)
        return data | {
            "nh3_flow_sccm": self.nh3_flow_sccm,
            "air_flow_sccm": self.air_flow_sccm,
        } | mfc_channel_log_fields(self.mfc_channels)


@dataclass
class MeasurementRecord:
    """One row of experiment data written to CSV/Excel and shown in preview."""

    timestamp: str
    elapsed_s: float
    resistance_ohm: float
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
    mfc_channels: tuple[MFCChannelState, ...] = ()

    def to_dict(self):
        data = asdict(self)
        data.pop("mfc_channels", None)
        return data | mfc_channel_log_fields(self.mfc_channels)
