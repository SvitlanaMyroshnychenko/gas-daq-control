# Gas Sensor DAQ & MFC Control

Python desktop prototype for gas sensor experiments. The application replaces an older Excel-based workflow with a PySide6 interface for live data acquisition, plotting, logging, and device control.

## Current Status

The project currently supports:

- simulated multimeter readings;
- simulated MFC and environment controls;
- live resistance graph;
- live temperature graph in simulation mode;
- CSV and Excel logging;
- read-only log preview in the UI;
- experiment start/stop workflow;
- selectable data output folder;
- simple timed actions for NH3, air, humidity, and heating;
- safe shutdown of simulated active controls on Stop;
- real Keithley 2450 resistance measurement through PyVISA;
- real Bronkhorst/propar MFC read-only diagnostics;
- UI device selection between simulated and real modes.

Real MFC write/control mode is intentionally not enabled yet. The real MFC integration is read-only until gas testing and safety checks are approved.

## Hardware Context

Target laboratory chain:

```text
Gas cylinders
-> Bronkhorst MFCs
-> gas mixing / sensor chamber
-> gas sensor
-> Keithley 2450 multimeter
-> PC / Python application
```

Important: the gas sensor is not connected directly to the software. The application reads the sensor response electrically through the multimeter. MFCs control gas flow and will later be controlled from the application.

Known tested devices:

- Multimeter: Keithley 2450, tested over USB/VISA.
- MFC controller: Bronkhorst F-201CV family, tested over COM/propar in read-only mode.

The application code is being refactored toward generic device naming:

- `Multimeter` instead of hard-coding Keithley in application logic.
- `MFC Controller` instead of hard-coding Bronkhorst in application logic.
- Hardware-specific test scripts may still use exact device names because they are intended for physical device diagnostics.

## Project Structure

```text
gas_sensor_daq/
├── main.py
├── gas_sensor_daq/
│   ├── core/
│   │   └── acquisition_manager.py
│   ├── devices/
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── fake_mfc.py
│   │   ├── fake_multimeter.py
│   │   ├── propar_mfc_controller.py
│   │   └── scpi_resistance_multimeter.py
│   ├── logging/
│   │   └── data_logger.py
│   ├── models/
│   │   └── records.py
│   ├── ui/
│   │   ├── assets/
│   │   └── main_window.py
│   └── settings.py
├── hardware_tests/
│   ├── test_bronkhorst.py
│   └── test_keithley_2450.py
├── data/
└── requirements.txt
```

Legacy top-level files such as `f_multimeter.py` and `logger.py` are old prototype files and are no longer the main application architecture.

## Running the Application

From the project root:

```powershell
.\.venv\Scripts\python.exe main.py
```

The app starts in simulated mode by default. This is the safest mode for UI work and development without physical devices.

## Main UI Workflow

1. Select save format: CSV or Excel.
2. Select output folder with `Folder`.
3. Choose simulated or real devices in the Devices panel.
4. Press `Start`.
5. Watch live readings, graphs, and log preview.
6. Press `Stop` to finish the experiment.

When an experiment is stopped:

- acquisition stops;
- logger closes;
- save format and folder selection become available again;
- active simulated gas/environment controls return to a safe state;
- pressing Start again creates a new experiment file.

## Logged Data

Each acquisition row is prepared from the current reading and device state. Current logging includes:

- timestamp;
- elapsed time;
- resistance;
- temperature when available;
- NH3 setpoint/actual flow;
- air setpoint/actual flow;
- humidity state;
- heating state;
- event;
- device status fields.

The log preview in the UI shows a compact subset of the most recent rows. The CSV/Excel file stores the full experiment log.

## Real Multimeter Test

The Keithley 2450 has been tested successfully through PyVISA.

List available VISA resources:

```powershell
.\.venv\Scripts\python.exe hardware_tests\test_keithley_2450.py
```

Example tested resource:

```text
USB0::0x05E6::0x2450::04607254::INSTR
```

Measure resistance:

```powershell
.\.venv\Scripts\python.exe hardware_tests\test_keithley_2450.py --resource "USB0::0x05E6::0x2450::04607254::INSTR" --measure-resistance
```

The app uses a generic SCPI resistance multimeter adapter:

```text
gas_sensor_daq/devices/scpi_resistance_multimeter.py
```

## Real MFC Test

The Bronkhorst/propar MFC connection has been tested in read-only mode.

List nodes:

```powershell
.\.venv\Scripts\python.exe hardware_tests\test_bronkhorst.py --port COM3
```

Read diagnostics from a node:

```powershell
.\.venv\Scripts\python.exe hardware_tests\test_bronkhorst.py --port COM3 --read --address 3
```

Observed test result:

- one detected node at address `3`;
- serial `M25217902C`;
- capacity around `10 mln/min`;
- fluid name `AiR`;
- measured flow and setpoint read as `0` when no gas flow is active.

The app uses a generic propar MFC adapter:

```text
gas_sensor_daq/devices/propar_mfc_controller.py
```

At this stage it reads real MFC status only. Flow setpoint writes are disabled for safety.

## Environment Variables

Optional configuration can be provided through environment variables:

```text
GAS_DAQ_DEVICE_MODE
GAS_DAQ_MULTIMETER
GAS_DAQ_MFC
GAS_DAQ_INTERVAL_MS
GAS_DAQ_MULTIMETER_RESOURCE
GAS_DAQ_MFC_PORT
GAS_DAQ_MFC_BAUDRATE
GAS_DAQ_MFC_ADDRESS
GAS_DAQ_DEFAULT_AIR_FLOW
GAS_DAQ_DATA_DIR
```

Older names are still supported as fallback:

```text
GAS_DAQ_KEITHLEY_RESOURCE
GAS_DAQ_BRONKHORST_PORT
GAS_DAQ_BRONKHORST_BAUDRATE
GAS_DAQ_BRONKHORST_ADDRESS
```

## Safety Notes

- Use simulated mode when hardware is not connected.
- Real MFC control is read-only for now.
- Do not enable real MFC setpoint writes until gas supply, exhaust, pressure, tubing, and lab safety procedures are confirmed.
- The real multimeter adapter measures resistance only.
- If a real device disconnects during an experiment, acquisition stops and the error is logged in a readable form.

## Current Development Focus

Near-term priorities:

- keep UI stable and usable on non-fullscreen windows;
- continue separating generic device interfaces from vendor-specific implementations;
- keep real MFC integration read-only until safe gas tests are possible;
- add manual MFC write control only after hardware/safety approval;
- later package the app as a desktop executable for lab laptops.
