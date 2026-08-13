# Architecture

## Purpose And Boundaries

The project is a PySide6 desktop application. The UI coordinates an experiment, but hardware communication, state, schedule validation, and file writing live outside the visual components. This separation keeps a layout change from altering MFC safety behavior.

## Dependency Flow

```text
main.py
  -> ui.main_window.MainWindow
       -> ui.* panels, tables, plots, styles
       -> core.acquisition_manager.AcquisitionManager
            -> devices.factory
                 -> simulated adapters OR real Propar/VISA adapters
            -> logging.data_logger
            -> models.records
       -> core.experiment_design
       -> settings
```

`MainWindow` is the presentation coordinator. It owns widget state and turns user edits into schedule dictionaries. `AcquisitionManager` owns experiment timers, device state, safe stopping, sampling, and log dispatch. Device adapters own only protocol-specific I/O. Loggers own only file persistence.

## Runtime Lifecycle

```text
User edits schedule
  -> MainWindow validates visual cells
  -> Start
  -> AcquisitionManager validates schedule again
  -> real rack: verifies zero-setpoint preflight
  -> create CSV/XLSX + metadata JSON
  -> apply first six-MFC step
  -> sample MFC state + resistance at configured rate
  -> write record and update UI
  -> timer advances step or Stop requested
  -> safe_shutdown: command and confirm zero on all MFCs
  -> finalize data and metadata files
```

The manager repeats validation even when the UI already checked it. This is a deliberate safety boundary: hardware commands must never rely only on visuals.

## Modules

### Root

| File | Responsibility | Depends on |
| --- | --- | --- |
| `main.py` | Creates `QApplication`, instantiates/shows `MainWindow`. | PySide6, `ui.main_window` |
| `requirements.txt` | Runtime dependency list. | pip |
| `.gitignore` | Excludes environments, data output, IDE/cache artifacts from Git. | Git |

### Configuration And Models

| File | Responsibility | Used by |
| --- | --- | --- |
| `gas_sensor_daq/settings.py` | Defines the expected six-node rack, serials, capacities, default COM settings, and environment-variable overrides. | manager, rack, UI |
| `gas_sensor_daq/models/records.py` | Defines MFC-channel snapshots, control state, measurement records, and the stable CSV/Excel schema. | devices, manager, logger, UI |

The configured expected rack is:

```text
1 M25217902C 10 mln/min  Gas 1
2 M25217902A 10 mln/min  Gas 2
3 M25217902B 10 mln/min  Gas 3
4 M25217902E 200 mln/min Humid air
5 M25217902F 200 mln/min Dry air
6 M25217902D 30 mln/min  Dry air
```

### Experiment Core

| File | Responsibility | Used by |
| --- | --- | --- |
| `core/experiment_design.py` | Flow constants, target-total comparison, theoretical rack-capacity calculation, and explicit duration parsing. | UI, manager |
| `core/acquisition_manager.py` | Central state machine: Start/Stop, recipe steps, timers, sampling, errors, metadata, MFC zeroing and residual-flow warning. | `MainWindow` |

`AcquisitionManager` is the owner of safety-sensitive behavior. In particular, it validates every schedule step, starts real hardware only after preflight, applies reduced flows before increased flows at a transition, and calls `safe_shutdown_controls()` on Stop, completion, and normal close.

### Device Layer

| File | Responsibility | Parent/consumer |
| --- | --- | --- |
| `devices/base.py` | Device interface contracts. | factory and adapters |
| `devices/factory.py` | Creates simulated or real device adapters from settings. | acquisition manager |
| `devices/fake_multimeter.py` | Simulated resistance values. | factory |
| `devices/fake_mfc.py` | Six-channel simulated MFC rack with capacity validation. | factory |
| `devices/scpi_resistance_multimeter.py` | Real SCPI/VISA resistance measurement adapter. | factory |
| `devices/visa_discovery.py` | VISA resource scan helper. | UI/device selection |
| `devices/propar_mfc_rack.py` | Real six-node Bronkhorst/propar rack: discovery, verification, readback, write/confirm setpoints, safe zeroing. | factory, manager |

`ProparMFCRack` accepts a connection only if the discovered rack matches the configured nodes. Before a real recipe starts it checks readiness and requires all current setpoints to be zero. During a step transition it first writes decreases and then increases, avoiding a temporary total-flow spike.

### Logging

| File | Responsibility | Called by |
| --- | --- | --- |
| `logging/data_logger.py` | CSV and Excel writers; adjacent JSON metadata; stable export-field order. | acquisition manager |

CSV uses a `DictWriter`. Excel uses a `Data` sheet plus a `Metadata` sheet. Both formats use the same per-sample fields. The separate metadata JSON is intended for reproducibility and contains identity/configuration information which should not be duplicated in every data row.

### UI Composition

| File | Responsibility | Parent/consumer |
| --- | --- | --- |
| `ui/main_window.py` | Connects panels to the manager, validates/edit schedule, updates all displayed state, controls UI enablement. | `main.py` |
| `ui/toolbar.py` | File name/path, format, folder selection, Start and Stop controls. | `MainWindow` |
| `ui/current_readings.py` | Resistance, rack capacity, current total setpoint and actual flow panel. | `MainWindow` |
| `ui/live_measurement.py` | Resistance/MFC-flow view composition. | `MainWindow` |
| `ui/plot_widgets.py` | Pyqtgraph plot widgets and presentation helpers. | live measurement / main window |
| `ui/mfc_monitor.py` | Six-channel actual/setpoint monitor, serial detail, and manual zero-all control. | `MainWindow` |
| `ui/device_status.py` | Device mode, scan, selection, verification and connection controls. | `MainWindow` |
| `ui/experiment_status.py` | Idle/running/completed/stopped/error experiment status summary. | `MainWindow` |
| `ui/experiment_schedule.py` | Schedule card layout, event actions, target/rate controls, and expandable mixture calculator. | `MainWindow` |
| `ui/recipe_table.py` | Schedule table presentation and editing behavior. | `MainWindow` |
| `ui/log_preview.py` | Bounded recent-record preview table, row selector and column sizing. | `MainWindow` |
| `ui/log_table.py` | Log-preview formatting/presentation helpers. | log UI |
| `ui/formatting.py` | Shared text/number presentation helpers. | UI modules |
| `ui/styles.py` | Application-wide Qt stylesheet. | `MainWindow` |
| `ui/widgets/cards.py` | Reusable section-card containers. | UI panels |
| `ui/assets/*` | Icons used by the desktop UI. | UI modules/styles |

UI modules should not issue serial/VISA commands directly. They ask `AcquisitionManager` to do so, then render the manager's signals and snapshots.

## Schedule And Mixture Rules

The schedule stores a direct setpoint for each physical MFC. The normal target is 150 mln/min, but it is a chosen experimental constraint, not the physical rack capacity. Every step must satisfy:

```text
0 <= MFCn <= MFCn capacity
MFC1 + MFC2 + MFC3 + MFC4 + MFC5 + MFC6 = Step Total
Step Total = Target total
Duration has an explicit s or min unit and is > 0
```

The calculator is a convenience layer. Given RH, MFC1-3, and MFC5 dry air, it calculates:

```text
MFC4 = Target total x RH / 100
MFC6 = Target total - (MFC1 + MFC2 + MFC3 + MFC4 + MFC5)
```

It never replaces final validation. Directly edited table values go through the same validation before a run may start.

## Signals And UI State

The manager emits state, acquired data, elapsed time, active step, errors, flow warnings, experiment start, and experiment stop signals. `MainWindow` maps those signals to panels. It disables schedule mutation, output settings, sampling-rate edits, and the manual zero button when a run is active.

## Tests

| File | Coverage |
| --- | --- |
| `tests/test_acquisition_manager_shutdown.py` | Start-location requirement; Stop/completion file closure; all-channel zeroing; critical failure reporting. |
| `tests/test_propar_mfc_rack.py` | Node/capacity/unit/serial verification; six-channel reads; per-channel capacity limits; controlled recipe transitions; zero confirmation. |

Run all tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
