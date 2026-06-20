import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gas_sensor_daq.ui.main_window import MainWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("Gas Sensor DAQ & MFC Control - UI Preview")
    window.resize(1600, 900)
    window.show()

    if "--smoke-test" in sys.argv:
        QTimer.singleShot(200, app.quit)


    sys.exit(app.exec())


if __name__ == "__main__":
    main()
