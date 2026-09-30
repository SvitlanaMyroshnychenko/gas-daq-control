from dataclasses import dataclass
import os

# Second multimeter added

@dataclass(frozen=True)
class MFCNodeConfig:
    address: int
    serial: str
    capacity_mln_min: float
    gas_name: str


EXPECTED_MFC_NODES = (
    MFCNodeConfig(address=1, serial="M25217902C", capacity_mln_min=10.0, gas_name="Gas 1"),
    MFCNodeConfig(address=2, serial="M25217902A", capacity_mln_min=10.0, gas_name="Gas 2"),
    MFCNodeConfig(address=3, serial="M25217902B", capacity_mln_min=10.0, gas_name="Gas 3"),
    MFCNodeConfig(address=4, serial="M25217902E", capacity_mln_min=200.0, gas_name="Humid air"),
    MFCNodeConfig(address=5, serial="M25217902F", capacity_mln_min=200.0, gas_name="Dry air"),
    MFCNodeConfig(address=6, serial="M25217902D", capacity_mln_min=30.0, gas_name="Dry air"),
)


@dataclass(frozen=True)
class DeviceSettings:
    mode: str = "simulation"
    multimeter_mode: str = "simulation"
    mfc_mode: str = "simulation"
    acquisition_interval_ms: int = 2000
    mfc_port: str = "COM3"
    mfc_baudrate: int = 38400
    mfc_nodes: tuple[MFCNodeConfig, ...] = EXPECTED_MFC_NODES
    multimeter_resource: str = ""
    # Second multimeter added
    multimeter_2_mode: str = "disabled"
    multimeter_2_resource: str = ""
    # The user selects an output location in the UI before each experiment.
    data_directory: str = ""


def load_device_settings():
    return DeviceSettings(
        mode=os.getenv("GAS_DAQ_DEVICE_MODE", "simulation"),
        multimeter_mode=os.getenv(
            "GAS_DAQ_MULTIMETER",
            os.getenv("GAS_DAQ_DEVICE_MODE", "simulation"),
        ),
        # Second multimeter added
        multimeter_2_mode=os.getenv("GAS_DAQ_MULTIMETER_2", "disabled").strip().lower(),
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
        multimeter_resource=os.getenv(
            "GAS_DAQ_MULTIMETER_RESOURCE",
            os.getenv("GAS_DAQ_KEITHLEY_RESOURCE", ""),
        ),
        # Second multimeter added
        multimeter_2_resource=os.getenv(
            "GAS_DAQ_MULTIMETER_2_RESOURCE",
            "",
        ).strip(),
        data_directory=os.getenv("GAS_DAQ_DATA_DIR", "").strip(),
    )


def _env_int(name, default):
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


DEFAULT_SETTINGS = load_device_settings()
