import math
import unittest

from PySide6.QtCore import QCoreApplication

from gas_sensor_daq.core.acquisition_manager import AcquisitionManager
from gas_sensor_daq.settings import DeviceSettings


class ClosingLogger:
    def __init__(self):
        self.close_calls = 0
        self.metadata_updates = []

    def update_metadata(self, updates):
        self.metadata_updates.append(dict(updates))

    def close(self):
        self.close_calls += 1


class FailingShutdownMFC:
    def safe_shutdown(self):
        raise ConnectionError("write confirmation failed")


class CapturingLogger(ClosingLogger):
    def __init__(self):
        super().__init__()
        self.records = []

    def write(self, record):
        self.records.append(record)


class FailingSecondMultimeter:
    def read(self, _state):
        raise ConnectionError("second instrument did not respond")

    def close(self):
        pass


class AcquisitionManagerShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.manager = AcquisitionManager()
        self.messages = []
        self.manager.experiment_stopped.connect(self.messages.append)

    def tearDown(self):
        self.manager.close()

    def activate_run(self):
        self.manager.mfc.set_channel_setpoints({
            1: 1.0,
            2: 0.0,
            3: 0.0,
            4: 0.0,
            5: 5.0,
            6: 0.0,
        })
        self.manager.mfc.get_state()
        self.manager.logger = ClosingLogger()
        self.manager.acquisition_timer.start(1_000)
        self.manager.elapsed_timer.start(1_000)

    def assert_run_is_safely_closed(self):
        self.assertFalse(self.manager.acquisition_timer.isActive())
        self.assertFalse(self.manager.elapsed_timer.isActive())
        self.assertIsNone(self.manager.logger)
        self.assertTrue(
            all(value == 0.0 for value in self.manager.mfc.channel_setpoints.values())
        )

    def test_last_recipe_step_stops_timers_closes_file_and_zeros_mfcs(self):
        self.activate_run()
        logger = self.manager.logger
        self.manager.recipe_steps = ({"duration_ms": 1_000},)
        self.manager.recipe_step_index = 0

        self.manager.advance_recipe()

        self.assert_run_is_safely_closed()
        self.assertEqual(logger.close_calls, 1)
        self.assertEqual(
            self.messages[-1], "Experiment completed; MFC setpoints reset to zero"
        )

    def test_stop_closes_file_and_zeros_mfcs(self):
        self.activate_run()
        logger = self.manager.logger

        self.manager.stop_experiment("Stopped by operator")

        self.assert_run_is_safely_closed()
        self.assertEqual(logger.close_calls, 1)
        self.assertEqual(self.messages[-1], "Stopped by operator")

    def test_stop_reports_a_critical_message_when_zeroing_cannot_be_confirmed(self):
        self.manager.mfc = FailingShutdownMFC()
        self.manager.logger = ClosingLogger()

        self.manager.stop_experiment("Stopped by operator")

        self.assertIn("CRITICAL", self.messages[-1])
        self.assertIn("could not be confirmed", self.messages[-1])

    def test_start_requires_a_selected_save_location(self):
        manager = AcquisitionManager(settings=DeviceSettings(data_directory=""))
        self.addCleanup(manager.close)

        with self.assertRaisesRegex(ValueError, "Choose a save location"):
            manager.start_experiment("CSV", data_directory="")

        self.assertIsNone(manager.logger)
        self.assertFalse(manager.acquisition_timer.isActive())

    def test_second_simulated_multimeter_is_acquired_in_the_same_row(self):
        manager = AcquisitionManager(
            settings=DeviceSettings(multimeter_2_mode="simulation")
        )
        self.addCleanup(manager.close)
        logger = CapturingLogger()
        manager.logger = logger

        manager.acquire_once()

        self.assertEqual(len(logger.records), 1)
        self.assertTrue(math.isfinite(logger.records[0].resistance_ohm))
        self.assertTrue(math.isfinite(logger.records[0].resistance_2_ohm))
        self.assertEqual(logger.records[0].multimeter_2_status, "SIMULATED OK")

    def test_disabled_second_multimeter_leaves_second_resistance_empty(self):
        manager = AcquisitionManager(settings=DeviceSettings())
        self.addCleanup(manager.close)
        logger = CapturingLogger()
        manager.logger = logger

        manager.acquire_once()

        self.assertEqual(len(logger.records), 1)
        self.assertIsNone(logger.records[0].resistance_2_ohm)
        self.assertEqual(logger.records[0].multimeter_2_status, "Disabled")

    def test_second_multimeter_failure_stops_the_experiment(self):
        manager = AcquisitionManager(
            settings=DeviceSettings(multimeter_2_mode="simulation")
        )
        self.addCleanup(manager.close)
        logger = CapturingLogger()
        manager.logger = logger
        manager.multimeter_2 = FailingSecondMultimeter()
        manager.acquisition_timer.start(1_000)

        manager.acquire_once()

        self.assertFalse(manager.acquisition_timer.isActive())
        self.assertEqual(len(logger.records), 1)
        self.assertTrue(math.isnan(logger.records[0].resistance_ohm))
        self.assertTrue(math.isnan(logger.records[0].resistance_2_ohm))
        self.assertEqual(logger.records[0].multimeter_2_status, "ERROR")


if __name__ == "__main__":
    unittest.main()
