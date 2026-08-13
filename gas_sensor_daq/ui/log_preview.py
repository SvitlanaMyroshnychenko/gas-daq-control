from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QSizePolicy, QTableWidget, QTableWidgetItem


class LogPreviewTable(QTableWidget):
    """Bounded, responsive table used for the on-screen experiment log preview."""

    HEADERS = (
        "Time",
        "Elapsed",
        "Step",
        "Resistance\n(Ohm)",
        "Setpoint total\n(mln/min)",
        "Actual total\n(mln/min)",
        "Event",
    )
    DEFAULT_WIDTHS = (110, 68, 56, 100, 118, 118, 190)
    WIDTH_RATIOS = (0.16, 0.09, 0.07, 0.14, 0.14, 0.14, 0.26)
    MAX_STORED_RECORDS = 50

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.max_rows = 5
        self.records = []
        self._adjusting_columns = False

        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setObjectName("logPreviewTable")
        self.setMinimumHeight(160)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(52)
        for column, width in enumerate(self.DEFAULT_WIDTHS):
            self.setColumnWidth(column, width)
        header.sectionResized.connect(self._on_section_resized)
        self.viewport().installEventFilter(self)
        self.verticalHeader().setDefaultSectionSize(26)
        QTimer.singleShot(0, self.apply_default_column_widths)

    def append_record(self, values):
        self.records.append(tuple(str(value) for value in values))
        self.records = self.records[-self.MAX_STORED_RECORDS:]
        self.refresh()

    def clear_records(self):
        self.records.clear()
        self.setRowCount(0)

    def set_max_rows(self, value):
        self.max_rows = int(value)
        self.refresh()

    def refresh(self):
        self.setRowCount(0)
        for values in self.records[-self.max_rows:]:
            row = self.rowCount()
            self.insertRow(row)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.setItem(row, column, item)
        self.scrollToBottom()

    def apply_default_column_widths(self):
        if self._adjusting_columns:
            return

        viewport_width = self.viewport().width()
        if viewport_width <= 0:
            return

        self._adjusting_columns = True
        try:
            minimum_width = self.horizontalHeader().minimumSectionSize()
            used_width = 0
            last_column = self.columnCount() - 1
            for column, ratio in enumerate(self.WIDTH_RATIOS):
                if column == last_column:
                    width = max(minimum_width, viewport_width - used_width)
                else:
                    width = max(minimum_width, round(viewport_width * ratio))
                    used_width += width
                self.setColumnWidth(column, width)
        finally:
            self._adjusting_columns = False

    def eventFilter(self, source, event):
        if source is self.viewport() and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self.fit_columns_to_viewport)
        return super().eventFilter(source, event)

    def _on_section_resized(self, logical_index, _old_size, _new_size):
        if not self._adjusting_columns:
            self.fit_columns_to_viewport(priority_column=logical_index)

    def fit_columns_to_viewport(self, priority_column=None):
        if self._adjusting_columns:
            return

        self._adjusting_columns = True
        try:
            minimum_width = self.horizontalHeader().minimumSectionSize()
            columns = range(self.columnCount())
            viewport_width = self.viewport().width()
            total_width = sum(self.columnWidth(column) for column in columns)

            if total_width > viewport_width:
                excess = total_width - viewport_width
                for column in reversed(range(self.columnCount())):
                    if column == priority_column or excess <= 0:
                        continue
                    width = self.columnWidth(column)
                    shrink_by = min(excess, max(0, width - minimum_width))
                    if shrink_by:
                        self.setColumnWidth(column, width - shrink_by)
                        excess -= shrink_by
                if excess > 0 and priority_column is not None:
                    width = self.columnWidth(priority_column)
                    shrink_by = min(excess, max(0, width - minimum_width))
                    if shrink_by:
                        self.setColumnWidth(priority_column, width - shrink_by)
            elif total_width < viewport_width and self.columnCount():
                last_column = self.columnCount() - 1
                self.setColumnWidth(
                    last_column,
                    self.columnWidth(last_column) + viewport_width - total_width,
                )
        finally:
            self._adjusting_columns = False
