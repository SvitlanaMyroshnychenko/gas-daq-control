from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout

from gas_sensor_daq.ui.widgets.cards import state_row


class ExperimentStatusPanel:
    """Visual status card for the active or planned experiment."""

    def __init__(self):
        self.card = QFrame()
        self.card.setObjectName("experimentStatusCard")
        self.card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(12, 10, 12, 11)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Experiment Status")
        title.setObjectName("sectionTitle")
        self.state_badge = QLabel("IDLE")
        self.state_badge.setObjectName("experimentStateBadge")
        self.state_badge.setAlignment(Qt.AlignCenter)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.state_badge)
        layout.addLayout(header)

        self.step_caption = self._caption("Step")
        self.step_value = self._value("Not started")
        self.event_value = QLabel("0 of 0 steps")
        self.event_value.setObjectName("experimentEventValue")
        layout.addWidget(self.step_caption)
        layout.addWidget(self.step_value)
        layout.addWidget(self.event_value)

        self.time_caption = self._caption("Time remaining")
        self.remaining_value = self._value("--:--:--", "experimentTimeValue")
        self.progress = QProgressBar()
        self.progress.setObjectName("experimentProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.time_caption)
        layout.addWidget(self.remaining_value)
        layout.addWidget(self.progress)

        details = QVBoxLayout()
        details.setSpacing(0)
        self.sampling_rate_value = self._value("--")
        self.total_time_value = self._value("--")
        self.elapsed_value = self._value("00:00:00")
        details.addWidget(state_row("Sampling rate", self.sampling_rate_value))
        details.addWidget(state_row("Planned", self.total_time_value))
        details.addWidget(state_row("Elapsed", self.elapsed_value))
        layout.addLayout(details)

    @staticmethod
    def _caption(text):
        label = QLabel(text)
        label.setObjectName("experimentStatusCaption")
        return label

    @staticmethod
    def _value(text, object_name="experimentStatusValue"):
        label = QLabel(text)
        label.setObjectName(object_name)
        return label
