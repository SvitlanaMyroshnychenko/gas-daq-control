from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)


class Stepper(QWidget):
    def __init__(self, minimum=0, maximum=100, value=0, suffix="", step=1, parent=None):
        super().__init__(parent)
        self.spinbox = QSpinBox()
        self.spinbox.setRange(minimum, maximum)
        self.spinbox.setSingleStep(step)
        self.spinbox.setValue(value)
        self.spinbox.setSuffix(suffix)
        self.spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinbox.setAlignment(Qt.AlignCenter)

        self.minus_button = QPushButton("-")
        self.plus_button = QPushButton("+")
        self.minus_button.setObjectName("stepButton")
        self.plus_button.setObjectName("stepButton")
        self.minus_button.setFixedWidth(30)
        self.plus_button.setFixedWidth(30)

        self.minus_button.clicked.connect(self.spinbox.stepDown)
        self.plus_button.clicked.connect(self.spinbox.stepUp)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.minus_button)
        layout.addWidget(self.spinbox, 1)
        layout.addWidget(self.plus_button)
        self.setLayout(layout)

    def value(self):
        return self.spinbox.value()

    def setValue(self, value):
        self.spinbox.setValue(int(value))


class RateStepper(QWidget):
    def __init__(self, value=0.5, parent=None):
        super().__init__(parent)
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(0.1, 10.0)
        self.spinbox.setSingleStep(0.1)
        self.spinbox.setDecimals(1)
        self.spinbox.setValue(value)
        self.spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinbox.setAlignment(Qt.AlignCenter)
        self.spinbox.setObjectName("rateSpinBox")
        self.spinbox.setFixedSize(58, 26)

        self.minus_button = QPushButton("-")
        self.plus_button = QPushButton("+")
        for button in (self.minus_button, self.plus_button):
            button.setObjectName("rateStepButton")
            button.setFixedSize(28, 26)

        self.minus_button.clicked.connect(self.spinbox.stepDown)
        self.plus_button.clicked.connect(self.spinbox.stepUp)

        self.unit_label = QLabel("Hz")
        self.unit_label.setObjectName("rateUnit")
        self.unit_label.setFixedSize(20, 26)
        self.unit_label.setAlignment(Qt.AlignCenter)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.minus_button)
        layout.addWidget(self.spinbox)
        layout.addWidget(self.plus_button)
        layout.addWidget(self.unit_label)
        self.setLayout(layout)

    def value(self):
        return self.spinbox.value()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        for widget in (
            self.minus_button,
            self.spinbox,
            self.plus_button,
            self.unit_label,
        ):
            widget.setEnabled(enabled)
