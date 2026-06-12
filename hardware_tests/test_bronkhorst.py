import argparse
import sys
import time

import propar


DIAGNOSTIC_DDE_PARAMETERS = [
    8,    # Measure, raw 0..32000-ish
    9,    # Setpoint, raw 0..32000-ish
    12,   # Control Mode
    21,   # Capacity 100%
    23,   # Capacity Unit Index
    25,   # Fluid Name
    28,   # Alarm Info
    45,   # Readout Unit
    129,  # Capacity Unit
    142,  # Temperature
    205,  # Fmeasure, engineering units when available
    206,  # Fsetpoint, engineering units when available
    418,  # Instrument NAMUR Status
]


MONITOR_DDE_PARAMETERS = [
    8,    # Measure, raw 0..32000-ish
    9,    # Setpoint, raw 0..32000-ish
    28,   # Alarm Info
    142,  # Temperature
    205,  # Fmeasure, engineering units when available
    206,  # Fsetpoint, engineering units when available
]


def _format_value(value):
    if isinstance(value, bytes):
        return value.decode(errors="replace").strip("\x00")
    if isinstance(value, str):
        return value.strip("\x00")
    return value


def _read_parameter(master, address, parameter):
    request = {
        "node": address,
        "proc_nr": parameter["proc_nr"],
        "parm_nr": parameter["parm_nr"],
        "parm_type": parameter["parm_type"],
        "parm_name": parameter["parm_name"],
    }
    if "parm_size" in parameter:
        request["parm_size"] = parameter["parm_size"]

    response = master.read_parameters([request])
    if response:
        result = response[0]
        result.setdefault("parm_name", parameter["parm_name"])
        return result

    return {
        "parm_name": parameter["parm_name"],
        "status": "no response",
        "data": None,
    }


def _read_diagnostics(master, address):
    print(f"\nRead-only diagnostics for node {address}:")

    for parameter in master.db.get_parameters(DIAGNOSTIC_DDE_PARAMETERS):
        result = _read_parameter(master, address, parameter)
        name = result.get("parm_name", parameter["parm_name"])
        status = result.get("status")
        value = _format_value(result.get("data"))
        if status == 0:
            print(f"  {name}: {value}")
        else:
            print(f"  {name}: unavailable (status={status}, data={value})")


def _read_monitor_values(master, address):
    values = {}
    for parameter in master.db.get_parameters(MONITOR_DDE_PARAMETERS):
        result = _read_parameter(master, address, parameter)
        name = result.get("parm_name", parameter["parm_name"])
        status = result.get("status")
        value = _format_value(result.get("data"))
        values[name] = value if status == 0 else f"unavailable:{status}"
    return values


def _monitor(master, address, duration_s, interval_s):
    print(
        f"\nRead-only monitor for node {address}: "
        f"duration={duration_s:.1f}s, interval={interval_s:.1f}s"
    )
    print(
        "elapsed_s | measure | setpoint | fmeasure | fsetpoint | "
        "temperature_c | alarm_info"
    )

    started_at = time.monotonic()
    try:
        while True:
            elapsed_s = time.monotonic() - started_at
            if elapsed_s > duration_s:
                break

            values = _read_monitor_values(master, address)
            print(
                f"{elapsed_s:8.1f} | "
                f"{values.get('Measure', '--')} | "
                f"{values.get('Setpoint', '--')} | "
                f"{values.get('Fmeasure', '--')} | "
                f"{values.get('Fsetpoint', '--')} | "
                f"{values.get('Temperature', '--')} | "
                f"{values.get('Alarm Info', '--')}"
            )
            time.sleep(interval_s)
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")


def main():
    parser = argparse.ArgumentParser(
        description="Bronkhorst propar smoke test."
    )
    parser.add_argument(
        "--port",
        default="COM3",
        help="Serial port for the Bronkhorst master, default: COM3",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=38400,
        help="Serial baudrate, default: 38400",
    )
    parser.add_argument(
        "--read",
        action="store_true",
        help="Read safe diagnostic parameters from discovered instruments.",
    )
    parser.add_argument(
        "--address",
        type=int,
        help="Read diagnostics only from this node address.",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Continuously read safe parameters without writing to the MFC.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Monitor duration in seconds, default: 60.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Monitor interval in seconds, default: 2.",
    )
    args = parser.parse_args()

    if args.duration <= 0:
        parser.error("--duration must be greater than 0.")
    if args.interval <= 0:
        parser.error("--interval must be greater than 0.")

    master = propar.master(args.port, args.baudrate)
    try:
        instruments = master.get_nodes()

        print(f"Bronkhorst port: {args.port}")
        print(f"Bronkhorst baudrate: {args.baudrate}")
        print("Found instruments:")
        print(instruments)

        if args.read:
            addresses = [args.address] if args.address is not None else [
                instrument["address"] for instrument in instruments
            ]
            if not addresses:
                print("\nNo node addresses available for diagnostics.")
            for address in addresses:
                _read_diagnostics(master, address)

        if args.monitor:
            addresses = [args.address] if args.address is not None else [
                instrument["address"] for instrument in instruments
            ]
            if not addresses:
                print("\nNo node addresses available for monitoring.")
            for address in addresses:
                _monitor(master, address, args.duration, args.interval)
    finally:
        master.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
