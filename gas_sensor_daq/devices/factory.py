from gas_sensor_daq.devices.fake_mfc import FakeMFC
from gas_sensor_daq.devices.fake_multimeter import FakeMultimeter
from gas_sensor_daq.devices.propar_mfc_controller import ProparMFCController
from gas_sensor_daq.devices.scpi_resistance_multimeter import ScpiResistanceMultimeter
from gas_sensor_daq.settings import DeviceSettings


def create_devices(settings: DeviceSettings):
    return (
        create_multimeter(settings),
        create_mfc(settings),
    )


def create_multimeter(settings: DeviceSettings, mode=None, resource_name=None):
    # The rest of the app asks for "simulation" or "real" only. Concrete
    # adapter classes stay hidden here so future devices can be swapped in.
    mode = (mode or settings.multimeter_mode).lower().strip()

    if mode == "simulation":
        return FakeMultimeter()

    if mode == "real":
        return ScpiResistanceMultimeter(resource_name or settings.multimeter_resource)

    raise ValueError(f"Unsupported multimeter mode: {settings.multimeter_mode}")


def create_mfc(settings: DeviceSettings, mode=None, port=None, address=None):
    # Keep MFC creation symmetric with the multimeter factory: UI/core code
    # should not need to know whether the backend is fake or propar-based.
    mode = (mode or settings.mfc_mode).lower().strip()

    if mode == "simulation":
        return FakeMFC(default_air_flow_sccm=settings.default_air_flow_sccm)

    if mode == "real":
        selected_address = (
            settings.mfc_address if address is None else address
        )
        return ProparMFCController(
            port or settings.mfc_port,
            baudrate=settings.mfc_baudrate,
            address=selected_address,
            default_air_flow_sccm=settings.default_air_flow_sccm,
        )

    raise ValueError(f"Unsupported MFC mode: {settings.mfc_mode}")
