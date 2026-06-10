import csv
import os

from openpyxl import Workbook

from gas_sensor_daq.models.records import FIELDNAMES


class CSVLogger:
    def __init__(self, filename):
        os.makedirs(os.path.dirname(filename) or "data", exist_ok=True)
        self.file = open(filename, "w", newline="")
        self.writer = csv.DictWriter(self.file, fieldnames=FIELDNAMES)
        self.writer.writeheader()

    def write(self, record):
        row = record.to_dict()
        self.writer.writerow(row)
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
        row = record.to_dict()
        self.sheet.append([row.get(field, "") for field in FIELDNAMES])
        self.workbook.save(self.filename)

    def close(self):
        self.workbook.save(self.filename)
