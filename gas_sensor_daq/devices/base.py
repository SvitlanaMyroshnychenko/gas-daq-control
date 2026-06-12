from typing import Protocol

from gas_sensor_daq.models.records import ControlState, MeasurementRecord


class MultimeterDevice(Protocol):
    def reset_time(self):
        ...

    def read(self, control_state: ControlState) -> MeasurementRecord:
        ...

    def close(self):
        ...


class MFCDevice(Protocol):
    def set_nh3_flow(self, value_sccm):
        ...

    def set_air_flow(self, value_sccm):
        ...

    def air_purge(self):
        ...

    def set_humidity(self, enabled):
        ...

    def set_heating(self, enabled):
        ...

    def safe_shutdown(self):
        ...

    def get_state(self) -> ControlState:
        ...

    def close(self):
        ...
