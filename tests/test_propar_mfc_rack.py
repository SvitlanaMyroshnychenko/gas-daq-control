import unittest
from unittest.mock import patch

from gas_sensor_daq.devices.propar_mfc_rack import ProparMFCRack
from gas_sensor_daq.devices.fake_mfc import FakeMFC
from gas_sensor_daq.models.records import MFCChannelState, MeasurementRecord
from gas_sensor_daq.settings import EXPECTED_MFC_NODES


class FakeDatabase:
    parameter_names = {
        8: "measure_raw",
        9: "setpoint_raw",
        21: "capacity",
        25: "fluid_name",
        28: "alarm_info",
        129: "capacity_unit",
        142: "temperature",
        205: "fmeasure",
        206: "fsetpoint",
    }

    def get_parameter(self, number):
        return {
            "proc_nr": 1,
            "parm_nr": number,
            "parm_type": 0,
            "parm_name": self.parameter_names[number],
        }


class FakeProparMaster:
    def __init__(self):
        self.db = FakeDatabase()
        self.stopped = False
        self.nodes = [
            {
                "address": node.address,
                "serial": node.serial,
                "type": "DMFC",
                "channels": 1,
            }
            for node in EXPECTED_MFC_NODES
        ]

    def get_nodes(self):
        return self.nodes

    def read_parameters(self, requests):
        request = requests[0]
        address = request["node"]
        name = request["parm_name"]
        values = {
            "capacity": 30.0,
            "fluid_name": "AiR",
            "capacity_unit": "mln/min",
            "temperature": 22.0 + address / 10,
            "alarm_info": 0,
            "fmeasure": float(address),
            "fsetpoint": float(address) + 0.5,
            "measure_raw": address * 1000,
            "setpoint_raw": address * 1000 + 100,
        }
        return [{"status": 0, "data": values[name]}]

    def stop(self):
        self.stopped = True


class ProparMFCRackTests(unittest.TestCase):
    def test_simulated_rack_has_six_known_channels(self):
        state = FakeMFC(nodes=EXPECTED_MFC_NODES).get_state()

        self.assertEqual(len(state.mfc_channels), 6)
        self.assertEqual(state.mfc_channels[0].address, 1)
        self.assertEqual(state.mfc_channels[5].serial, "M25217902D")
        self.assertEqual(state.mfc_channels[0].status, "SIMULATED")

    def test_simulated_rack_applies_a_setpoint_to_each_channel(self):
        mfc = FakeMFC(nodes=EXPECTED_MFC_NODES)
        mfc.set_channel_setpoints({
            1: 5.0,
            2: 0.0,
            3: 15.0,
            4: 5.0,
            5: 5.0,
            6: 0.0,
        })
        state = mfc.get_state()

        self.assertEqual(
            [channel.setpoint_sccm for channel in state.mfc_channels],
            [5.0, 0.0, 15.0, 5.0, 5.0, 0.0],
        )
        self.assertGreater(state.mfc_channels[2].actual_sccm, 0.0)

    def test_simulated_rack_rejects_setpoints_above_channel_capacity(self):
        mfc = FakeMFC(nodes=EXPECTED_MFC_NODES)

        with self.assertRaisesRegex(ValueError, "exceeds its 30 mln/min capacity"):
            mfc.set_channel_setpoints({
                1: 30.1,
                2: 0.0,
                3: 0.0,
                4: 0.0,
                5: 0.0,
                6: 0.0,
            })

    def test_simulated_rack_safe_shutdown_resets_all_channels(self):
        mfc = FakeMFC(nodes=EXPECTED_MFC_NODES)
        mfc.set_channel_setpoints({
            1: 5.0,
            2: 10.0,
            3: 15.0,
            4: 20.0,
            5: 25.0,
            6: 30.0,
        })
        mfc.get_state()
        mfc.safe_shutdown()
        state = mfc.get_state()

        self.assertTrue(all(value == 0.0 for value in mfc.channel_setpoints.values()))
        self.assertTrue(all(value == 0.0 for value in mfc.channel_actuals.values()))
        self.assertTrue(all(channel.setpoint_sccm == 0.0 for channel in state.mfc_channels))

    def test_reads_all_verified_nodes_and_flattens_them_for_logging(self):
        master = FakeProparMaster()
        with patch.object(ProparMFCRack, "_open_master", return_value=master):
            rack = ProparMFCRack("COM4", 38400, EXPECTED_MFC_NODES)
            state = rack.get_state()
            rack.close()

        self.assertTrue(master.stopped)
        self.assertEqual(len(state.mfc_channels), 6)
        self.assertEqual(state.mfc_channels[0].address, 1)
        self.assertEqual(state.mfc_channels[5].serial, "M25217902D")
        self.assertEqual(state.mfc_channels[3].actual_sccm, 4.0)
        self.assertEqual(state.mfc_channels[3].setpoint_sccm, 4.5)
        self.assertEqual(state.mfc_channels[3].status, "OK")

        record = MeasurementRecord(
            timestamp="2026-07-14 12:00:00",
            elapsed_s=0.0,
            resistance_ohm=10000.0,
            nh3_flow_sccm=0.0,
            air_flow_sccm=0.0,
            humidity_on=False,
            heating_on=False,
            mfc_channels=state.mfc_channels,
        )
        row = record.to_dict()
        self.assertEqual(row["mfc1_actual_sccm"], 1.0)
        self.assertEqual(row["mfc6_setpoint_sccm"], 6.5)
        self.assertEqual(row["mfc6_serial"], "M25217902D")

    def test_rejects_a_rack_with_a_wrong_serial_number(self):
        nodes = [
            {"address": node.address, "serial": node.serial}
            for node in EXPECTED_MFC_NODES
        ]
        nodes[2]["serial"] = "unexpected"

        verified, message = ProparMFCRack._verify_nodes(nodes, EXPECTED_MFC_NODES)

        self.assertFalse(verified)
        self.assertIn("serial mismatch", message)

    def test_discovery_marks_the_verified_port(self):
        master = FakeProparMaster()
        with patch.object(ProparMFCRack, "_open_master", return_value=master):
            discoveries = ProparMFCRack.discover(
                baudrate=38400,
                expected_nodes=EXPECTED_MFC_NODES,
                ports=["COM4"],
            )

        self.assertEqual(len(discoveries), 1)
        self.assertEqual(discoveries[0].port, "COM4")
        self.assertTrue(discoveries[0].verified)
        self.assertEqual(discoveries[0].addresses, (1, 2, 3, 4, 5, 6))


if __name__ == "__main__":
    unittest.main()
