from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DeviceSettings:
    mode: str = "simulation"
    multimeter_mode: str = "simulation"
    mfc_mode: str = "simulation"
    acquisition_interval_ms: int = 2000
    bronkhorst_port: str = "COM3"
    keithley_resource: str = ""
    default_air_flow_sccm: float = 100.0


def load_device_settings():
    return DeviceSettings(
        mode=os.getenv("GAS_DAQ_DEVICE_MODE", "simulation"),
        multimeter_mode=os.getenv(
            "GAS_DAQ_MULTIMETER",
            os.getenv("GAS_DAQ_DEVICE_MODE", "simulation"),
        ),
        mfc_mode=os.getenv(
            "GAS_DAQ_MFC",
            os.getenv("GAS_DAQ_DEVICE_MODE", "simulation"),
        ),
        acquisition_interval_ms=_env_int("GAS_DAQ_INTERVAL_MS", 2000),
        bronkhorst_port=os.getenv("GAS_DAQ_BRONKHORST_PORT", "COM3"),
        keithley_resource=os.getenv("GAS_DAQ_KEITHLEY_RESOURCE", ""),
        default_air_flow_sccm=_env_float("GAS_DAQ_DEFAULT_AIR_FLOW", 100.0),
    )


def _env_int(name, default):
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name, default):
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


DEFAULT_SETTINGS = load_device_settings()
