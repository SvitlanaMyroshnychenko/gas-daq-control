import argparse
import sys

import propar


def main():
    parser = argparse.ArgumentParser(
        description="Bronkhorst propar smoke test."
    )
    parser.add_argument(
        "--port",
        default="COM3",
        help="Serial port for the Bronkhorst master, default: COM3",
    )
    args = parser.parse_args()

    master = propar.master(args.port)
    instruments = master.get_nodes()

    print(f"Bronkhorst port: {args.port}")
    print("Found instruments:")
    print(instruments)

    return 0


if __name__ == "__main__":
    sys.exit(main())

