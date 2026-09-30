import csv
import tempfile
import unittest
from pathlib import Path

from gas_sensor_daq.logging.data_logger import CSVLogger, row_for_file
from gas_sensor_daq.models.records import FIELDNAMES, MeasurementRecord


class DataLoggerTests(unittest.TestCase):
    def test_second_resistance_is_exported_to_csv(self):
        record = MeasurementRecord(
            timestamp="2026-09-30 12:00:00",
            elapsed_s=1.0,
            resistance_ohm=100.0,
            resistance_2_ohm=200.0,
            multimeter_2_status="SIMULATED OK",
        )

        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "experiment.csv"
            logger = CSVLogger(str(filename))
            logger.write(record)
            logger.close()

            with filename.open(newline="") as data_file:
                row = next(csv.DictReader(data_file))

        self.assertIn("resistance_2_ohm", FIELDNAMES)
        self.assertIn("measurement_2_status", FIELDNAMES)
        self.assertEqual(row["resistance_ohm"], "100.0")
        self.assertEqual(row["resistance_2_ohm"], "200.0")
        self.assertEqual(row["measurement_2_status"], "SIMULATED OK")

    def test_disabled_second_multimeter_exports_an_empty_value(self):
        record = MeasurementRecord(
            timestamp="2026-09-30 12:00:00",
            elapsed_s=1.0,
            resistance_ohm=100.0,
        )

        row = row_for_file(record)

        self.assertIsNone(row["resistance_2_ohm"])
        self.assertEqual(row["measurement_2_status"], "Disabled")


if __name__ == "__main__":
    unittest.main()
