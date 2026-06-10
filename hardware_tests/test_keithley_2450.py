import argparse
import sys
import time

import pyvisa


def list_resources(resource_manager):
    resources = resource_manager.list_resources()
    print("Available VISA resources:")
    if not resources:
        print("  No resources found.")
        return

    for resource in resources:
        print(f"  {resource}")


def query_error_queue(instrument):
    try:
        return instrument.query(":SYST:ERR?").strip()
    except pyvisa.errors.VisaIOError:
        return "Could not read error queue"


def measure_resistance_2wire(instrument):
    print("\nConfiguring 2-wire resistance measurement...")
    print("Use only a passive resistor between FORCE HI and FORCE LO.")

    instrument.write("*CLS")
    instrument.write(":SENS:FUNC \"RES\"")
    instrument.write(":SENS:RES:RANG:AUTO ON")
    instrument.write(":SENS:RES:NPLC 1")

    instrument.write(":OUTP ON")
    try:
        time.sleep(0.2)
        raw_value = instrument.query(":READ?").strip()
    finally:
        instrument.write(":OUTP OFF")

    print(f":READ? -> {raw_value}")

    first_value = raw_value.split(",")[0]
    try:
        resistance_ohm = float(first_value)
        print(f"Resistance -> {resistance_ohm:.6g} Ohm")
    except ValueError:
        print("Could not parse resistance value.")

    print(f"Instrument error queue -> {query_error_queue(instrument)}")


def main():
    parser = argparse.ArgumentParser(
        description="Keithley 2450 PyVISA smoke test."
    )
    parser.add_argument(
        "--resource",
        help="VISA resource string, for example USB0::...::INSTR",
    )
    parser.add_argument(
        "--measure-resistance",
        action="store_true",
        help="Also send MEAS:RES? after *IDN?. Use only with a safe test resistor.",
    )
    args = parser.parse_args()

    rm = pyvisa.ResourceManager()
    list_resources(rm)

    if not args.resource:
        print("\nRun again with --resource once you know the Keithley VISA address.")
        return 0

    instrument = rm.open_resource(args.resource)
    instrument.timeout = 10000
    instrument.write_termination = "\n"
    instrument.read_termination = "\n"

    try:
        idn = instrument.query("*IDN?").strip()
        print(f"\n*IDN? -> {idn}")

        if args.measure_resistance:
            measure_resistance_2wire(instrument)
    finally:
        try:
            instrument.write(":OUTP OFF")
        except pyvisa.errors.VisaIOError:
            pass
        instrument.close()
        rm.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
