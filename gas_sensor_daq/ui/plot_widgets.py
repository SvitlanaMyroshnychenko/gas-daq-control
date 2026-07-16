from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

import pyqtgraph as pg


def create_plot(title, left_label, units, color):
    plot = pg.PlotWidget()
    plot.setBackground("w")
    plot.setLabel("left", f"{left_label} ({units})", **{"color": "#334155", "font-size": "11px"})
    plot.setLabel("bottom", "Time (s)", **{"color": "#334155", "font-size": "11px"})
    plot.showGrid(x=True, y=True, alpha=0.18)
    plot.setMinimumSize(0, 120)
    plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    plot.getPlotItem().setContentsMargins(6, 2, 8, 4)
    plot.getPlotItem().layout.setContentsMargins(4, 2, 8, 4)
    plot.getAxis("left").setPen(pg.mkPen("#cbd5e1"))
    plot.getAxis("bottom").setPen(pg.mkPen("#cbd5e1"))
    plot.getAxis("left").setTextPen(pg.mkPen("#475569"))
    plot.getAxis("bottom").setTextPen(pg.mkPen("#475569"))
    plot.getAxis("left").setWidth(58)
    plot.getAxis("bottom").setHeight(42)
    plot.getAxis("left").setStyle(tickTextOffset=7)
    plot.getAxis("bottom").setStyle(tickTextOffset=7)
    plot.getPlotItem().getViewBox().setBorder(None)
    return plot


def create_mfc_flow_legend(channel_colors):
    legend = QWidget()
    layout = QHBoxLayout()
    layout.setContentsMargins(68, 0, 0, 0)
    layout.setSpacing(14)

    for index, color in channel_colors.items():
        item = QHBoxLayout()
        item.setContentsMargins(0, 0, 0, 0)
        item.setSpacing(5)
        dot = QLabel()
        dot.setObjectName("compactDot")
        dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        dot.setFixedSize(10, 10)
        label = QLabel(f"MFC {index}")
        label.setObjectName("metricName")
        item.addWidget(dot)
        item.addWidget(label)
        layout.addLayout(item)

    layout.addStretch()
    legend.setLayout(layout)
    return legend
