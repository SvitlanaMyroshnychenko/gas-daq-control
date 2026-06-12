import math
import random
import time

from gas_sensor_daq.models.records import MeasurementRecord


class FakeMultimeter:
    def __init__(self):
        self.temperature_c = 25.0
        self.reset_time()

    def reset_time(self):
        self.start_time = time.time()

    def read(self, control_state):
        elapsed = time.time() - self.start_time
        sensor_state = control_state.to_sensor_state()

        # The fake response is intentionally simple but directional: NH3 and
        # humidity lower resistance, heating raises temperature and resistance.
        baseline = 10000

        gas_effect = 0
        if sensor_state["nh3_flow"] > 0:
            gas_effect = -1500 * min(sensor_state["nh3_flow"] / 20, 1)

        humidity_effect = -300 if sensor_state["humidity_on"] else 0
        heating_effect = 300 if sensor_state["heating_on"] else 0

        drift = 50 * math.sin(elapsed / 30)
        noise = random.uniform(-30, 30)

        resistance = (
            baseline
            + gas_effect
            + humidity_effect
            + heating_effect
            + drift
            + noise
        )

        target_temperature = 40 if sensor_state["heating_on"] else 25
        self.temperature_c += (target_temperature - self.temperature_c) * 0.18
        temperature = self.temperature_c + random.uniform(-0.25, 0.25)

        return MeasurementRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            elapsed_s=elapsed,
            resistance_ohm=resistance,
            temperature_c=temperature,
            nh3_flow_sccm=control_state.nh3_flow_sccm,
            air_flow_sccm=control_state.air_flow_sccm,
            humidity_on=control_state.humidity_on,
            heating_on=control_state.heating_on,
            nh3_setpoint_sccm=control_state.nh3_setpoint_sccm,
            nh3_actual_sccm=control_state.nh3_actual_sccm,
            air_setpoint_sccm=control_state.air_setpoint_sccm,
            air_actual_sccm=control_state.air_actual_sccm,
            multimeter_status="SIMULATED OK",
            mfc_status=control_state.device_status,
            mfc_port=control_state.mfc_port,
            mfc_address=control_state.mfc_address,
            mfc_serial=control_state.mfc_serial,
            mfc_fluid=control_state.mfc_fluid,
            mfc_capacity_sccm=control_state.mfc_capacity_sccm,
            mfc_capacity_unit=control_state.mfc_capacity_unit,
            mfc_temperature_c=control_state.mfc_temperature_c,
            mfc_alarm_info=control_state.mfc_alarm_info,
        )

    def close(self):
        pass
