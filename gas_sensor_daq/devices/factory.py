from gas_sensor_daq.devices.fake_mfc import FakeMFC
from gas_sensor_daq.devices.fake_multimeter import FakeMultimeter
from gas_sensor_daq.devices.real_bronkhorst_mfc import RealBronkhorstMFC
from gas_sensor_daq.devices.real_keithley_2450 import RealKeithley2450
from gas_sensor_daq.settings import DeviceSettings


def create_devices(settings: DeviceSettings):
    return (
        create_multimeter(settings),
        create_mfc(settings),
    )


def create_multimeter(settings: DeviceSettings, mode=None, resource_name=None):
    mode = (mode or settings.multimeter_mode).lower().strip()

    if mode == "simulation":
        return FakeMultimeter()

    if mode == "real":
        return RealKeithley2450(resource_name or settings.keithley_resource)

    raise ValueError(f"Unsupported multimeter mode: {settings.multimeter_mode}")


def create_mfc(settings: DeviceSettings):
    mode = settings.mfc_mode.lower().strip()

    if mode == "simulation":
        return FakeMFC(default_air_flow_sccm=settings.default_air_flow_sccm)

    if mode == "real":
        return RealBronkhorstMFC(settings.bronkhorst_port)

    raise ValueError(f"Unsupported MFC mode: {settings.mfc_mode}")
