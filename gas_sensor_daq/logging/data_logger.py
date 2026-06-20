import csv
import os

from openpyxl import Workbook

from gas_sensor_daq.models.records import FIELDNAMES


BOOLEAN_FIELDS = {"humidity_on", "heating_on"}


def row_for_file(record):
    row = record.to_dict()
    normalized = {}
    for field in FIELDNAMES:
        value = row.get(field, "")
        if field in BOOLEAN_FIELDS:
            value = "true" if bool(value) else "false"
        normalized[field] = value
    return normalized


class CSVLogger:
    def __init__(self, filename):
        os.makedirs(os.path.dirname(filename) or "data", exist_ok=True)
        self.file = open(filename, "w", newline="")
        self.writer = csv.DictWriter(self.file, fieldnames=FIELDNAMES)
        self.writer.writeheader()

    def write(self, record):
        # FIELDNAMES controls column order and filters accidental extra keys.
        self.writer.writerow(row_for_file(record))
        self.file.flush()

    def close(self):
        self.file.close()


class ExcelLogger:
    def __init__(self, filename):
        os.makedirs(os.path.dirname(filename) or "data", exist_ok=True)
        self.filename = filename
        self.workbook = Workbook()
        self.sheet = self.workbook.active
        self.sheet.title = "Data"
        self.sheet.append(FIELDNAMES)

    def write(self, record):
        row = row_for_file(record)
        # Save on every row so a long experiment still leaves a usable file if
        # the app or device connection fails before close() is called.
        self.sheet.append([row.get(field, "") for field in FIELDNAMES])
        self.workbook.save(self.filename)

    def close(self):
        self.workbook.save(self.filename)
