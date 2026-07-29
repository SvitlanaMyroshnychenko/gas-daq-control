import random
from types import SimpleNamespace

from gas_sensor_daq.models.records import ControlState, MFCChannelState


class FakeMFC:
    CHANNEL_CAPACITY_SCCM = 30.0

    def __init__(self, default_air_flow_sccm=100.0, nodes=()):
        self.nodes = tuple(nodes) or tuple(
            SimpleNamespace(address=index, serial=f"SIM-MFC-{index}")
            for index in range(1, 7)
        )
        self.channel_setpoints = {index: 0.0 for index in range(1, 7)}
        self.channel_actuals = {index: 0.0 for index in range(1, 7)}
        self.channel_capacities = {
            index: float(getattr(node, "capacity_mln_min", self.CHANNEL_CAPACITY_SCCM))
            for index, node in enumerate(self.nodes, start=1)
        }
        self.state = ControlState(
            air_setpoint_sccm=float(default_air_flow_sccm),
            air_actual_sccm=float(default_air_flow_sccm),
            device_status="SIMULATED",
        )

    def set_nh3_flow(self, value_sccm):
        self.state.nh3_setpoint_sccm = float(value_sccm)

    def set_channel_setpoints(self, setpoints):
        """Apply one simulated recipe step to all six MFC channels."""
        for index in self.channel_setpoints:
            try:
                value = float(setpoints[index])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Missing or invalid setpoint for MFC {index}.") from exc
            if value < 0:
                raise ValueError(f"Setpoint for MFC {index} cannot be negative.")
            capacity = self.channel_capacities[index]
            if value > capacity:
                raise ValueError(
                    f"Setpoint for MFC {index} exceeds its {capacity:g} mln/min capacity."
                )
            self.channel_setpoints[index] = value

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
        for index in self.channel_setpoints:
            self.channel_setpoints[index] = 0.0
            self.channel_actuals[index] = 0.0

    def get_state(self):
        self._update_actual_flows()
        self._update_rack_channels()
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

    def _update_rack_channels(self):
        channels = []
        for index, node in enumerate(self.nodes, start=1):
            setpoint = self.channel_setpoints[index]
            self.channel_actuals[index] = self._approach(
                self.channel_actuals[index],
                setpoint,
                noise=0.0,
            )
            channels.append(MFCChannelState(
                index=index,
                address=node.address,
                serial=node.serial,
                fluid_name="Air",
                capacity_sccm=self.channel_capacities[index],
                capacity_unit="mln/min",
                setpoint_sccm=setpoint,
                actual_sccm=self.channel_actuals[index],
                temperature_c=22.0,
                status="SIMULATED",
            ))
        self.state.mfc_channels = tuple(channels)

    @staticmethod
    def _approach(actual, target, noise):
        delta = target - actual
        next_value = actual + delta * 0.65

        if abs(delta) < noise * 2:
            next_value = target

        if target > 0:
            next_value += random.uniform(-noise, noise)

        return max(0.0, next_value)
