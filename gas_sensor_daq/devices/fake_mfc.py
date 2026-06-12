import random

from gas_sensor_daq.models.records import ControlState


class FakeMFC:
    def __init__(self, default_air_flow_sccm=100.0):
        self.state = ControlState(
            air_setpoint_sccm=float(default_air_flow_sccm),
            air_actual_sccm=float(default_air_flow_sccm),
            device_status="SIMULATED",
        )

    def set_nh3_flow(self, value_sccm):
        self.state.nh3_setpoint_sccm = float(value_sccm)

    def set_air_flow(self, value_sccm):
        self.state.air_setpoint_sccm = float(value_sccm)

    def air_purge(self):
        self.set_nh3_flow(0)
        self.set_air_flow(100)

    def set_humidity(self, enabled):
        self.state.humidity_on = bool(enabled)

    def set_heating(self, enabled):
        self.state.heating_on = bool(enabled)

    def safe_shutdown(self):
        # Simulation mirrors the safety policy expected from real hardware:
        # Stop should leave all active flows and environment outputs off.
        self.state.nh3_setpoint_sccm = 0.0
        self.state.nh3_actual_sccm = 0.0
        self.state.air_setpoint_sccm = 0.0
        self.state.air_actual_sccm = 0.0
        self.state.humidity_on = False
        self.state.heating_on = False
        self.state.device_status = "SIMULATED SAFE STOP"

    def get_state(self):
        self._update_actual_flows()
        return self.state

    def close(self):
        self.state.device_status = "SIMULATED CLOSED"

    def _update_actual_flows(self):
        # Actual flow approaches the setpoint instead of jumping instantly, so
        # UI/logging tests resemble real controller settling behavior.
        self.state.nh3_actual_sccm = self._approach(
            self.state.nh3_actual_sccm,
            self.state.nh3_setpoint_sccm,
            noise=0.03,
        )
        self.state.air_actual_sccm = self._approach(
            self.state.air_actual_sccm,
            self.state.air_setpoint_sccm,
            noise=0.12,
        )
        self.state.device_status = "SIMULATED OK"

    @staticmethod
    def _approach(actual, target, noise):
        delta = target - actual
        next_value = actual + delta * 0.65

        if abs(delta) < noise * 2:
            next_value = target

        if target > 0:
            next_value += random.uniform(-noise, noise)

        return max(0.0, next_value)
