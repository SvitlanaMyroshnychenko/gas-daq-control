# User Guide: Gas Sensor DAQ & MFC Control

This guide describes the normal, safe workflow. Follow the steps in order; when working with real gas hardware, do not improvise around an error message.

## 1. What The Main Terms Mean

| Term | Meaning |
| --- | --- |
| `mln/min` | Normalized millilitres per minute. This is the flow unit used by the application and the verified MFC rack. |
| Setpoint | The flow value requested from an MFC. |
| Actual | The flow value read back from an MFC. It can differ slightly from the setpoint while the controller settles. |
| Target total | The required total mixture flow for every schedule step, normally 150 mln/min. |
| Step total | The sum of MFC1 through MFC6 in one table row. It is calculated, not typed manually. |
| RH | Relative humidity target. In the calculator it determines the humid-air flow from MFC4 as a fraction of target total. |
| Event | A short description of the purpose of the step, such as `Baseline: dry air`, `Set 50% RH`, or `Gas 1 exposure`. It is written into every sample row recorded during that step. |

## 2. Before Opening The App

For a real experiment, first confirm with the laboratory responsible person:

1. The correct gas cylinders are connected to the intended MFC inputs.
2. Tubing reaches the mixing point, sensor chamber, and exhaust as intended.
3. Gas pressure and the exhaust path are safe.
4. The MFC rack is powered and connected to the PC.
5. The Keithley multimeter is connected to the sensor and visible over VISA.
6. It is safe to command every MFC setpoint to zero.

When any of these are uncertain, run only in **Simulated** mode.

## 3. Start The Application

From the project folder:

```powershell
.\.venv\Scripts\python.exe main.py
```

The application opens in simulated mode. This is intentional and safe for editing a schedule, practicing the workflow, and checking the UI without gas flow.

## 4. Choose Where Results Will Be Saved

1. In the upper **File** area, type the experiment file name if needed.
2. Press the folder button.
3. Select an existing folder to contain the experiment results.
4. Select `CSV` or `Excel` in **Format**.

The application adds the timestamp itself, for example:

```text
baseline_test_2026-08-12_10-30-00.csv
baseline_test_2026-08-12_10-30-00.metadata.json
```

There is no hidden default output folder for a normal run. If no folder is selected, Start is blocked.

## 5. Connect Devices

### Simulated devices

Use simulation to check the schedule, plots, file writing, and stop behavior. The MFC Monitor shows calculated setpoints and simulated actual values.

### Real multimeter

1. Open **Device Status**.
2. Set Multimeter mode to real.
3. Scan for VISA resources and choose the correct Keithley entry.
4. Connect it.
5. Confirm that **Current Readings** shows a plausible resistance.

### Real MFC rack

1. Set MFC Rack mode to real.
2. Scan the rack/COM ports.
3. Choose only a rack reported as verified.
4. Connect it.
5. Inspect **MFC Monitor**: all six channels must appear with their expected serial numbers, capacities, actual flows, and setpoints.

The application refuses a real rack if its node order, serial number, capacity, or reported unit does not match the configured rack. This prevents accidental control of a different installation.

## 6. Build An Experiment Schedule

Each row is one timed gas-mixture step. Enter only values which are physically valid for the connected MFCs.

| Table field | What you enter or observe |
| --- | --- |
| Step | Automatic row number. Hover it to see the Event description. |
| Step Total | Calculated sum of six MFC setpoints. Read-only. |
| Duration | Enter an explicit unit: `30 s`, `0.5 min`, `20 min`, or `2.5 min`. `2` without `s` or `min` is invalid. |
| RH (%) | Optional humidity target annotation for the row. It is editable. |
| MFC 1-6 | Direct setpoint values in mln/min. |
| Event | Short plain-language description of the selected step. |

Use **Add Step**, **Duplicate**, **Remove**, and **Clear all** before pressing Start. The table and action buttons are disabled while an experiment is running so the active plan cannot change mid-run.

### Required validation rules

Every active step must satisfy all of the following:

1. Duration is greater than zero and includes `s` or `min`.
2. Each MFC setpoint is zero or above and does not exceed that MFC's capacity.
3. Step Total equals the sum of MFC1 through MFC6.
4. Step Total equals Target total within 0.01 mln/min.

For the configured rack, individual limits are 10, 10, 10, 200, 200, and 30 mln/min for MFC1 through MFC6. The physical rack capacity is 460 mln/min, but the schedule Target total is the experiment's intended continuous flow.

## 7. Use The Mixture Calculator

The Mixture Calculator helps create a row but is not mandatory. You may edit the schedule cells directly, as long as the validation rules remain satisfied.

For the selected row, enter:

- RH percentage;
- desired MFC1, MFC2, and MFC3 flows;
- the amount of dry air to use from MFC5;
- duration with an explicit unit.

Then press **Calculate mixture**. The calculator applies:

```text
MFC4 = Target total x RH / 100
MFC6 = Target total - (MFC1 + MFC2 + MFC3 + MFC4 + MFC5)
```

This reflects the current laboratory convention: MFC4 supplies humid air, MFC5 and MFC6 supply dry air, and MFC1-MFC3 carry analyte streams. The UI does not measure RH itself. It uses the entered ratio to calculate the humid-air share, so any laboratory calibration assumptions must be confirmed separately.

Example for a target total of 150 mln/min and 50% RH:

```text
RH = 50%     -> MFC4 = 75
MFC1 = 1.5
MFC5 = 50
MFC2 = MFC3 = 0
MFC6 = 150 - (75 + 1.5 + 50) = 23.5 mln/min
```

If the computed MFC6 value is negative or exceeds 30 mln/min, change RH, analyte flows, MFC5 dry-air allocation, or Target total. The calculator will not write an invalid mixture into the schedule.

## 8. Run The Experiment

1. Re-read all schedule rows and Event text.
2. Check that the save folder and format are correct.
3. For a real run, confirm Device Status shows a connected verified rack and connected multimeter.
4. Press **START**.
5. Observe:
   - Current Readings: resistance, rack capacity, total setpoint and actual flow;
   - MFC Monitor: actual and setpoint for every channel;
   - Live Measurement: resistance or MFC-flow graph;
   - Experiment Status: active step, planned/elapsed/remaining time and rate;
   - Log Preview: newest recorded data rows and Event.

At each transition, the program lowers channels that need less flow before it raises channels that need more flow. This avoids briefly adding both mixtures together and exceeding the old/new step total during a change.

## 9. Stop And Verify Shutdown

Press **STOP** to end a run early. When the final schedule step finishes, the same stop sequence runs automatically:

1. Data acquisition and schedule timers stop.
2. The program commands every MFC setpoint to zero.
3. It confirms those zero setpoints from the real rack when possible.
4. The output CSV/Excel and metadata JSON are closed and finalized.
5. The application reads actual MFC flows briefly after the zero command.

If a warning says that actual flow remains, do not assume the setup is safe just because setpoints show zero. Check the physical gas rack, valves, tubing, and outlet with laboratory supervision.

The **Zero all setpoints** button in MFC Monitor is available only when an experiment is not running. It is an explicit manual safety action for a connected, verified real rack.

## 10. Output Files And Log Preview

CSV/Excel contains one measurement row per sampling interval. `Event` is present in every row of an active schedule step. JSON metadata is a companion file containing the static experiment context: schedule, MFC identity and capacities, device mode, sampling rate, and completion information.

Log Preview is only a bounded on-screen view. Its Rows control changes the number of stored recent rows shown in the table; it does not alter the file.

## 11. Common Errors And What To Do

| Message or symptom | Likely cause | What to do |
| --- | --- | --- |
| `Choose a save location before starting` | No output folder was selected. | Use the folder button and choose an existing folder. |
| Schedule issue badge or red cells | A duration, total, or MFC value is invalid. | Read the red message; correct the highlighted cell. |
| `MFC n must be between 0 and ...` | A channel setpoint exceeds its configured capacity or is negative. | Reduce the value; do not increase capacity in the UI. |
| `Step total must equal ... target flow` | The six MFC values do not sum to Target total. | Correct the mixture manually or use Calculate mixture. |
| `Invalid MFC 4, 6` from calculator | Calculated humid or dry-air flow is outside its MFC limit. | Adjust RH, MFC1-3, MFC5, or Target total. |
| Rack not verified / cannot connect | Wrong COM port, missing node, unexpected serial/capacity/unit, cable/power issue. | Stop, inspect the rack, scan again. Never select an unverified rack. |
| Multimeter scan finds nothing | VISA driver/cable/device not available. | Verify USB connection and VISA installation, then scan again. |
| `MFC alarm detected during experiment` | Controller reported an alarm. | Experiment stops automatically; inspect the physical controller and gas setup. |
| `CRITICAL: MFC zero setpoints could not be confirmed` | Zero command or readback failed. | Treat as a lab safety issue; check hardware immediately. |
| Actual flow remains after stop | Gas flow is still sensed after zero setpoint. | Inspect physical valves, tubing, pressure, and outlet. Do not start a new run until resolved. |
| CSV/XLSX cannot be written | Folder unavailable, permission issue, file open in Excel, or invalid path. | Choose a writable folder and close any open result file. |

## 12. What Not To Do

- Do not start a real run with an unverified MFC rack.
- Do not treat a zero setpoint as proof that actual flow is immediately zero.
- Do not edit schedule values while a run is active.
- Do not use `ml/min` or `mL/min` in the Duration field; duration accepts only time values such as `30 s` or `2 min`.
- Do not remove or rename the metadata JSON independently of its data file.

