import unittest

from gas_sensor_daq.core.experiment_design import (
    calculate_mixture_setpoints,
    parse_duration_seconds,
)


class ExperimentDesignTests(unittest.TestCase):
    def test_calculates_humid_and_dry_air_split(self):
        setpoints = calculate_mixture_setpoints(150, 50, 1.5, 0, 0, 50)

        self.assertEqual(
            setpoints,
            {1: 1.5, 2: 0.0, 3: 0.0, 4: 75.0, 5: 50.0, 6: 23.5},
        )

    def test_calculates_baseline_as_mfc5_only(self):
        setpoints = calculate_mixture_setpoints(150, 0, 0, 0, 0, 150)

        self.assertEqual(
            setpoints,
            {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 150.0, 6: 0.0},
        )

    def test_rejects_invalid_calculator_inputs(self):
        with self.assertRaisesRegex(ValueError, "RH"):
            calculate_mixture_setpoints(150, 101, 0, 0, 0, 0)
        with self.assertRaisesRegex(ValueError, "Target total"):
            calculate_mixture_setpoints(0, 0, 0, 0, 0, 0)

    def test_duration_requires_an_explicit_unit(self):
        self.assertEqual(parse_duration_seconds("30 s"), 30)
        self.assertEqual(parse_duration_seconds("0.5 min"), 30)
        self.assertIsNone(parse_duration_seconds("30"))


if __name__ == "__main__":
    unittest.main()
