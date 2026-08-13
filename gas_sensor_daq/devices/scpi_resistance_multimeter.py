import math
import time

import pyvisa

from gas_sensor_daq.models.records import MeasurementRecord


OPEN_CIRCUIT_THRESHOLD_OHM = 1e20


class ScpiResistanceMultimeter:
    """Generic SCPI resistance reader for a VISA-connected source meter.

    Tested with Keithley 2450, but the class avoids model-specific names so a
    similar SCPI instrument can be added later without changing the core logic.
    """

    def __init__(self, resource_name):
        if not resource_name:
            raise ConnectionError(
                "VISA resource is empty. Select a multimeter resource before connecting."
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

        self.idn = self.instrument.query("*IDN?").strip()

        self._configure_resistance()

    def reset_time(self):
        self.start_time = time.time()

    def read(self, control_state):
        if self.instrument is None:
            raise ConnectionError("VISA resistance multimeter is not connected.")

        elapsed = time.time() - self.start_time
        raw_value = self._read_resistance_raw()
        resistance = self._parse_resistance(raw_value)
        device_status = self._device_status(resistance)
        resistance_for_plot = math.nan if device_status == "OPEN CIRCUIT" else resistance

        return MeasurementRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            elapsed_s=elapsed,
            resistance_ohm=resistance_for_plot,
            multimeter_status=f"SCPI MULTIMETER {device_status}",
            mfc_channels=control_state.mfc_channels,
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
        # Keep the source output off except during an actual reading. This is
        # safer for sensors and mirrors the manual test procedure we validated.
        self.instrument.write("*CLS")
        self.instrument.write(":SENS:FUNC \"RES\"")
        self.instrument.write(":SENS:RES:RANG:AUTO ON")
        self.instrument.write(":SENS:RES:NPLC 1")
        self.instrument.write(":OUTP OFF")

    def _read_resistance_raw(self):
        # The output is enabled only for the short READ? window, then disabled
        # in finally so a timeout or parse error does not leave it on.
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
            raise ValueError(f"Could not parse resistance value: {raw_value}") from exc

    @staticmethod
    def _device_status(resistance):
        # Keithley-style open circuits can come back as very large sentinel
        # values. Treat them as status, not as plottable sensor resistance.
        if not math.isfinite(resistance):
            return "INVALID READING"

        if resistance >= OPEN_CIRCUIT_THRESHOLD_OHM:
            return "OPEN CIRCUIT"

        return "OK"
