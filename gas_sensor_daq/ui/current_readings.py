from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from gas_sensor_daq.ui.widgets.cards import compact_section_card


class CurrentReadingsPanel:
    """Compact presentation of the latest sensor and total-flow readings."""

    def __init__(
        self,
        resistance,
        resistance_2,
        rack_capacity,
        setpoint_total,
        actual_total,
    ):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for name, description, value, color in (
            ("Resistance", "Sensor measurement", resistance, "blue"),
            ("Resistance 2", "Second measurement", resistance_2, "orange"),
            ("Rack capacity", "Maximum available flow", rack_capacity, "slate"),
            ("Current setpoint flow", "Target flow", setpoint_total, "teal"),
            ("Current actual flow", "Measured flow", actual_total, "purple"),
        ):
            layout.addWidget(self._row(name, description, value, color))
        self.card = compact_section_card("Current Readings", layout)

    @staticmethod
    def _row(name, description, value_label, color):
        row = QFrame()
        row.setObjectName("compactReadingRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        name_label = QLabel(name)
        name_label.setObjectName("compactReadingName")
        description_label = QLabel(description)
        description_label.setObjectName("compactReadingDescription")
        text_layout.addWidget(name_label)
        text_layout.addWidget(description_label)

        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_label.setProperty("compactMetric", True)
        value_label.setProperty("readingMetric", False)
        value_label.setProperty("readingColor", color)
        value_label.style().unpolish(value_label)
        value_label.style().polish(value_label)

        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(value_label)
        return row
