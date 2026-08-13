# Gas Sensor DAQ & MFC Control

Desktop application for gas-sensor experiments with a Keithley resistance multimeter and a verified six-channel Bronkhorst MFC rack. It provides an experiment schedule, live resistance and flow monitoring, acquisition logging, and safe MFC shutdown.

## What The Application Does

- controls an experiment as a sequence of timed gas-mixture steps;
- supports six MFC channels with verified serial numbers and individual flow capacities;
- acquires sensor resistance from a simulated or real SCPI/VISA multimeter;
- displays MFC setpoints and actual flows during the experiment;
- writes a CSV or Excel measurement file plus adjacent JSON metadata;
- validates the schedule before Start and prevents invalid MFC setpoints;
- sends all MFC setpoints to zero after Stop, schedule completion, and normal application close; then monitors residual actual flow for a short period.

The interface and all flow values use `mln/min`, the normalized-flow unit reported by the verified MFC rack.

## Quick Start

1. Create and activate/install the Python environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Start the application:

   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

3. Choose a directory with the folder button in the **File** area. Recording cannot start until an output directory is selected.
4. Keep both devices in **Simulated** mode unless the laboratory setup is ready.
5. Edit the **Experiment Schedule**, validate any warnings, then press **START**.

For the complete laboratory workflow and error recovery, read [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## Hardware Configuration

The expected verified MFC rack is defined in `gas_sensor_daq/settings.py`:

| Channel | Node | Serial | Capacity | Intended stream |
| --- | ---: | --- | ---: | --- |
| MFC 1 | 1 | M25217902C | 10 mln/min | Gas 1 |
| MFC 2 | 2 | M25217902A | 10 mln/min | Gas 2 |
| MFC 3 | 3 | M25217902B | 10 mln/min | Gas 3 |
| MFC 4 | 4 | M25217902E | 200 mln/min | Humid air |
| MFC 5 | 5 | M25217902F | 200 mln/min | Dry air |
| MFC 6 | 6 | M25217902D | 30 mln/min | Dry air |

The theoretical rack capacity is 460 mln/min. The **Target total** in the schedule is a separate experimental limit: it is normally 150 mln/min, but the operator may set another value within the installed MFC capacities.

Real-rack discovery probes available COM ports and accepts a connection only when all six node addresses, serial numbers, capacities, and `mln/min` units match this configuration. The default bus settings are `COM3`, `38400` baud.

## Files Created Per Experiment

For each Start, the app creates a timestamped data file in the selected folder:

- `name_YYYY-MM-DD_HH-MM-SS.csv`, or
- `name_YYYY-MM-DD_HH-MM-SS.xlsx`.

It also writes `name_YYYY-MM-DD_HH-MM-SS.metadata.json`. The JSON file records the schedule, selected device modes, sampling rate, MFC identities/capacities, and start/end metadata. It is not a second stream of measurements.

The per-sample CSV/Excel columns are:

```text
timestamp, elapsed_s, step_number, event, resistance_ohm,
total_setpoint_mln_min, total_actual_mln_min, measurement_status,
mfc1_setpoint_mln_min, mfc1_actual_mln_min, ...,
mfc6_setpoint_mln_min, mfc6_actual_mln_min
```

## Safety

- Use simulated mode until the laboratory setup is ready.
- Verify gas supply, pressure, tubing, exhaust, sensor chamber, and laboratory procedure before using real MFC control.
- A real run starts only after the rack has been verified and all existing MFC setpoints are confirmed at zero.
- Do not bypass a schedule validation error.
- **STOP** attempts to set every verified MFC to zero and confirms the command. If that confirmation fails, treat the message as critical and inspect the rack.
- A post-stop warning about residual actual flow requires a physical check of the gas rack and outlet; zero setpoint does not prove that gas has stopped moving immediately.

## Development

Run the unit tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The technical module map and control flow are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

