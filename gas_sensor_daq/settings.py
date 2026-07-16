from dataclasses import dataclass
import os


@dataclass(frozen=True)
class MFCNodeConfig:
    address: int
    serial: str


EXPECTED_MFC_NODES = (
    MFCNodeConfig(address=1, serial="M25217902C"),
    MFCNodeConfig(address=2, serial="M25217902A"),
    MFCNodeConfig(address=3, serial="M25217902B"),
    MFCNodeConfig(address=4, serial="M25217902E"),
    MFCNodeConfig(address=5, serial="M25217902F"),
    MFCNodeConfig(address=6, serial="M25217902D"),
)


@dataclass(frozen=True)
class DeviceSettings:
    mode: str = "simulation"
    multimeter_mode: str = "simulation"
    mfc_mode: str = "simulation"
    acquisition_interval_ms: int = 2000
    mfc_port: str = "COM3"
    mfc_baudrate: int = 38400
    mfc_address: int | None = None
    mfc_nodes: tuple[MFCNodeConfig, ...] = EXPECTED_MFC_NODES
    multimeter_resource: str = ""
    default_air_flow_sccm: float = 100.0
    data_directory: str = "data"


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
        mfc_port=os.getenv(
            "GAS_DAQ_MFC_PORT",
            os.getenv("GAS_DAQ_BRONKHORST_PORT", "COM3"),
        ),
        mfc_baudrate=_env_int(
            "GAS_DAQ_MFC_BAUDRATE",
            _env_int("GAS_DAQ_BRONKHORST_BAUDRATE", 38400),
        ),
        mfc_address=_env_optional_int("GAS_DAQ_MFC_ADDRESS")
        if os.getenv("GAS_DAQ_MFC_ADDRESS") is not None
        else _env_optional_int("GAS_DAQ_BRONKHORST_ADDRESS"),
        multimeter_resource=os.getenv(
            "GAS_DAQ_MULTIMETER_RESOURCE",
            os.getenv("GAS_DAQ_KEITHLEY_RESOURCE", ""),
        ),
        default_air_flow_sccm=_env_float("GAS_DAQ_DEFAULT_AIR_FLOW", 100.0),
        data_directory=os.getenv("GAS_DAQ_DATA_DIR", "data"),
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


def _env_optional_int(name):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None

    try:
        return int(value)
    except ValueError:
        return None


DEFAULT_SETTINGS = load_device_settings()
