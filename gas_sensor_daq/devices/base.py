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
    def set_channel_setpoints(self, setpoints):
        ...

    def safe_shutdown(self):
        ...

    def get_state(self) -> ControlState:
        ...

    def close(self):
        ...
