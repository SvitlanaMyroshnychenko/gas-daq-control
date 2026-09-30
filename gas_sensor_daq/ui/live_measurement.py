from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from gas_sensor_daq.ui.widgets.cards import graph_card


class LiveMeasurementPanel:
    """Visual container for switching between resistance and MFC flow plots."""

    def __init__(
        self,
        resistance_plot,
        flow_plot,
        resistance_colors,
        channel_colors,
        set_active_plot,
    ):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.resistance_button = self._mode_button("Resistance", "start")
        self.flow_button = self._mode_button("MFC Flow", "end")
        self.resistance_button.setChecked(True)
        self.resistance_button.clicked.connect(lambda: set_active_plot("resistance"))
        self.flow_button.clicked.connect(lambda: set_active_plot("flow"))
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(0)
        controls.addWidget(self.resistance_button)
        controls.addWidget(self.flow_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.resistance_legend = self._resistance_legend(resistance_colors)
        layout.addWidget(self.resistance_legend)

        self.flow_legend = self._legend(channel_colors)
        self.flow_legend.hide()
        layout.addWidget(self.flow_legend)

        self.event_summary = QFrame()
        self.event_summary.setObjectName("eventSummary")
        event_layout = QHBoxLayout(self.event_summary)
        event_layout.setContentsMargins(8, 4, 8, 4)
        event_layout.setSpacing(7)
        self.event_summary_dot = QFrame()
        self.event_summary_dot.setFixedSize(7, 7)
        self.event_summary_dot.setStyleSheet(
            "background: #64748b; border: none; border-radius: 3px;"
        )
        self.event_summary_label = QLabel()
        self.event_summary_label.setObjectName("eventSummaryLabel")
        event_layout.addWidget(self.event_summary_dot)
        event_layout.addWidget(self.event_summary_label, 1)
        self.event_summary.hide()
        layout.addWidget(self.event_summary)
        layout.addSpacing(6)

        self.plot_stack = QStackedWidget()
        self.plot_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_stack.layout().setContentsMargins(0, 0, 0, 0)
        self.plot_stack.addWidget(resistance_plot)
        self.plot_stack.addWidget(flow_plot)
        layout.addWidget(self.plot_stack, 1)
        self.card = graph_card("Live measurement", "#3b82f6", layout)

    @staticmethod
    def _mode_button(text, position):
        button = QPushButton(text)
        button.setObjectName("plotModeButton")
        button.setProperty("position", position)
        button.setCheckable(True)
        button.setFixedHeight(28)
        return button

    @staticmethod
    def _legend(channel_colors):
        legend = QWidget()
        legend.setObjectName("flowLegend")
        layout = QHBoxLayout(legend)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        for index, color in channel_colors.items():
            entry = QWidget()
            entry_layout = QHBoxLayout(entry)
            entry_layout.setContentsMargins(0, 0, 0, 0)
            entry_layout.setSpacing(5)
            marker = QFrame()
            marker.setFixedSize(8, 8)
            marker.setStyleSheet(
                f"background: {color}; border: none; border-radius: 4px;"
            )
            label = QLabel(f"MFC {index}")
            label.setObjectName("flowLegendItem")
            entry_layout.addWidget(marker)
            entry_layout.addWidget(label)
            layout.addWidget(entry)
        layout.addStretch()
        return legend

    @staticmethod
    def _resistance_legend(resistance_colors):
        legend = QWidget()
        legend.setObjectName("flowLegend")
        layout = QHBoxLayout(legend)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        for label_text, color in resistance_colors.items():
            entry = QWidget()
            entry_layout = QHBoxLayout(entry)
            entry_layout.setContentsMargins(0, 0, 0, 0)
            entry_layout.setSpacing(5)
            marker = QFrame()
            marker.setFixedSize(8, 8)
            marker.setStyleSheet(
                f"background: {color}; border: none; border-radius: 4px;"
            )
            label = QLabel(label_text)
            label.setObjectName("flowLegendItem")
            entry_layout.addWidget(marker)
            entry_layout.addWidget(label)
            layout.addWidget(entry)
        layout.addStretch()
        return legend
