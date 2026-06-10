import math
import time

import pyvisa

from gas_sensor_daq.models.records import MeasurementRecord


OPEN_CIRCUIT_THRESHOLD_OHM = 1e20


class RealKeithley2450:
    def __init__(self, resource_name):
        if not resource_name:
            raise ConnectionError(
                "Keithley VISA resource is empty. Set GAS_DAQ_KEITHLEY_RESOURCE."
            )

        self.resource_name = resource_name
        self.resource_manager = None
        self.instrument = None
        self.reset_time()
        self.connect()

    def connect(self):
        self.resource_manager = pyvisa.ResourceManager()
        self.instrument = self.resource_manager.open_resource(self.resource_name)
        self.instrument.timeout = 10000
        self.instrument.write_termination = "\n"
        self.instrument.read_termination = "\n"

        idn = self.instrument.query("*IDN?").strip()
        if "2450" not in idn:
            self.close()
            raise ConnectionError(f"Unexpected instrument response: {idn}")

        self._configure_resistance()

    def reset_time(self):
        self.start_time = time.time()

    def read(self, control_state):
        if self.instrument is None:
            raise ConnectionError("Keithley 2450 is not connected.")

        elapsed = time.time() - self.start_time
        raw_value = self._read_resistance_raw()
        resistance = self._parse_resistance(raw_value)
        device_status = self._device_status(resistance)
        resistance_for_plot = math.nan if device_status == "OPEN CIRCUIT" else resistance

        return MeasurementRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            elapsed_s=elapsed,
            resistance_ohm=resistance_for_plot,
            temperature_c=math.nan,
            nh3_flow_sccm=control_state.nh3_flow_sccm,
            air_flow_sccm=control_state.air_flow_sccm,
            humidity_on=control_state.humidity_on,
            heating_on=control_state.heating_on,
            nh3_setpoint_sccm=control_state.nh3_setpoint_sccm,
            nh3_actual_sccm=control_state.nh3_actual_sccm,
            air_setpoint_sccm=control_state.air_setpoint_sccm,
            air_actual_sccm=control_state.air_actual_sccm,
            device_status=f"KEITHLEY 2450 {device_status}",
        )

    def close(self):
        if self.instrument is not None:
            try:
                self.instrument.write(":OUTP OFF")
            except Exception:
                pass
            self.instrument.close()
            self.instrument = None

        if self.resource_manager is not None:
            self.resource_manager.close()
            self.resource_manager = None

    def _configure_resistance(self):
        self.instrument.write("*CLS")
        self.instrument.write(":SENS:FUNC \"RES\"")
        self.instrument.write(":SENS:RES:RANG:AUTO ON")
        self.instrument.write(":SENS:RES:NPLC 1")
        self.instrument.write(":OUTP OFF")

    def _read_resistance_raw(self):
        self.instrument.write(":OUTP ON")
        try:
            time.sleep(0.1)
            return self.instrument.query(":READ?").strip()
        finally:
            self.instrument.write(":OUTP OFF")

    @staticmethod
    def _parse_resistance(raw_value):
        first_value = raw_value.split(",")[0]
        try:
            return float(first_value)
        except ValueError as exc:
            raise ValueError(f"Could not parse Keithley resistance value: {raw_value}") from exc

    @staticmethod
    def _device_status(resistance):
        if not math.isfinite(resistance):
            return "INVALID READING"

        if resistance >= OPEN_CIRCUIT_THRESHOLD_OHM:
            return "OPEN CIRCUIT"

        return "OK"
