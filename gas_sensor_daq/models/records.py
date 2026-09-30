from dataclasses import asdict, dataclass

# Second multimeter added

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
    "resistance_2_ohm",
    "total_setpoint_mln_min",
    "total_actual_mln_min",
    "measurement_status",
    "measurement_2_status",
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
    """Current state of the shared six-channel MFC rack."""

    device_status: str = "Simulated"
    mfc_port: str = ""
    mfc_channels: tuple[MFCChannelState, ...] = ()


@dataclass
class MeasurementRecord:
    """One row of experiment data written to CSV/Excel and shown in preview."""

    timestamp: str
    elapsed_s: float
    resistance_ohm: float
    resistance_2_ohm: float | None = None
    multimeter_2_status: str = "Disabled"
    event: str = ""
    multimeter_status: str = "Simulated"
    mfc_channels: tuple[MFCChannelState, ...] = ()
    step_number: int | None = None
    total_setpoint_mln_min: float = 0.0
    total_actual_mln_min: float = 0.0

    def to_dict(self):
        data = asdict(self)
        data.pop("mfc_channels", None)
        return data | mfc_channel_export_fields(self.mfc_channels) | {
            "measurement_status": self.multimeter_status,
            "measurement_2_status": self.multimeter_2_status,
        }
