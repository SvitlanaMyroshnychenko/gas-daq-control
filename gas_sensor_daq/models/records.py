from dataclasses import asdict, dataclass


MFC_CHANNEL_COUNT = 6


def mfc_channel_fieldnames():
    fields = []
    for index in range(1, MFC_CHANNEL_COUNT + 1):
        prefix = f"mfc{index}_"
        fields.extend([
            f"{prefix}setpoint_mln_min",
            f"{prefix}actual_mln_min",
        ])
    return fields


FIELDNAMES = [
    # This is the compact, per-sample logging contract. Static MFC identity and
    # capacity details live once in the adjacent metadata JSON file.
    "timestamp",
    "elapsed_s",
    "step_number",
    "event",
    "resistance_ohm",
    "total_setpoint_mln_min",
    "total_actual_mln_min",
    "measurement_status",
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


def mfc_channel_export_fields(channels):
    fields = {field: "" for field in mfc_channel_fieldnames()}
    for channel in channels:
        if 1 <= channel.index <= MFC_CHANNEL_COUNT:
            prefix = f"mfc{channel.index}_"
            fields[f"{prefix}setpoint_mln_min"] = channel.setpoint_sccm
            fields[f"{prefix}actual_mln_min"] = channel.actual_sccm
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
        } | {
            channel_key: value
            for channel in self.mfc_channels
            for channel_key, value in channel.to_log_fields().items()
        }


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
    step_number: int | None = None
    total_setpoint_mln_min: float = 0.0
    total_actual_mln_min: float = 0.0

    def to_dict(self):
        data = asdict(self)
        data.pop("mfc_channels", None)
        legacy_channel_fields = {
            channel_key: value
            for channel in self.mfc_channels
            for channel_key, value in channel.to_log_fields().items()
        }
        return data | legacy_channel_fields | mfc_channel_export_fields(self.mfc_channels) | {
            "measurement_status": self.multimeter_status,
        }
