import math
import random
import time

from gas_sensor_daq.models.records import MeasurementRecord


class FakeMultimeter:
    def __init__(self):
        self.reset_time()

    def reset_time(self):
        self.start_time = time.time()

    def read(self, control_state):
        elapsed = time.time() - self.start_time
        channels = {channel.index: channel for channel in control_state.mfc_channels}

        # The fake response is intentionally simple but follows the six-MFC
        # setup: analyte MFCs and the humid-air channel lower resistance.
        baseline = 10000
        analyte_flow = sum(channels.get(index).actual_sccm for index in range(1, 4) if index in channels)
        humid_air_flow = channels.get(4).actual_sccm if 4 in channels else 0.0
        total_flow = sum(channel.actual_sccm for channel in channels.values())
        gas_effect = -1500 * min(analyte_flow / 20, 1)
        humidity_effect = -300 * min(humid_air_flow / max(total_flow, 1.0), 1)

        drift = 50 * math.sin(elapsed / 30)
        noise = random.uniform(-30, 30)

        resistance = (
            baseline
            + gas_effect
            + humidity_effect
            + drift
            + noise
        )

        return MeasurementRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            elapsed_s=elapsed,
            resistance_ohm=resistance,
            multimeter_status="SIMULATED OK",
            mfc_channels=control_state.mfc_channels,
        )

    def close(self):
        pass
