from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QSizePolicy, QTableWidgetItem


DEFAULT_RECIPE_EVENTS = (
    "Baseline: dry air",
    "Set 50% RH",
    "Gas 1 exposure",
    "Recovery at 50% RH",
    "Purge: dry air",
)

def configure_recipe_table(recipe_table):
    recipe_table.setEditTriggers(
        QAbstractItemView.DoubleClicked
        | QAbstractItemView.EditKeyPressed
        | QAbstractItemView.SelectedClicked
    )
    recipe_table.setSelectionBehavior(QAbstractItemView.SelectRows)
    recipe_table.setAlternatingRowColors(True)
    recipe_table.setWordWrap(False)
    recipe_table.verticalHeader().setVisible(False)
    recipe_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    recipe_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    recipe_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    recipe_table.verticalHeader().setDefaultSectionSize(24)

    header = recipe_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.Fixed)
    recipe_table.setColumnWidth(0, 54)
    for column in range(1, recipe_table.columnCount()):
        header.setSectionResizeMode(column, QHeaderView.Stretch)

    defaults = [
        ("1", "150", "60 min", "0", "0", "0", "0", "0", "150", "0"),
        ("2", "150", "20 min", "50", "0", "0", "0", "75", "75", "0"),
        ("3", "150", "0.5 min", "50", "1.5", "0", "0", "75", "50", "23.5"),
        ("4", "150", "20 min", "50", "0", "0", "0", "75", "75", "0"),
        ("5", "150", "30 min", "0", "0", "0", "0", "0", "150", "0"),
    ]
    for row_index, row_values in enumerate(defaults):
        for column, value in enumerate(row_values):
            item = recipe_item(value, editable=column not in (0, 1, 3))
            item.setTextAlignment(Qt.AlignCenter)
            if column == 1:
                style_recipe_total_item(item)
            if column == 3:
                style_recipe_rh_item(item)
            if column == 0:
                item.setData(Qt.UserRole, DEFAULT_RECIPE_EVENTS[row_index])
            recipe_table.setItem(row_index, column, item)


def add_recipe_step(recipe_table):
    row = recipe_table.rowCount()
    recipe_table.insertRow(row)
    populate_recipe_row(recipe_table, row, str(row + 1))
    recipe_table.selectRow(row)


def duplicate_recipe_step(recipe_table):
    selected_rows = recipe_table.selectionModel().selectedRows()
    source_row = selected_rows[0].row() if selected_rows else recipe_table.rowCount() - 1
    if source_row < 0:
        add_recipe_step(recipe_table)
        return

    target_row = source_row + 1
    recipe_table.insertRow(target_row)
    for column in range(recipe_table.columnCount()):
        source_item = recipe_table.item(source_row, column)
        item = recipe_item(
            source_item.text() if source_item else "", editable=column not in (0, 1, 3)
        )
        item.setTextAlignment(Qt.AlignCenter)
        if column == 1:
            style_recipe_total_item(item)
        if column == 3:
            style_recipe_rh_item(item)
        if column == 0 and source_item is not None:
            item.setData(Qt.UserRole, source_item.data(Qt.UserRole))
        recipe_table.setItem(target_row, column, item)
    renumber_recipe_steps(recipe_table)
    recipe_table.selectRow(target_row)


def remove_recipe_step(recipe_table):
    if recipe_table.rowCount() <= 1:
        return
    selected_rows = recipe_table.selectionModel().selectedRows()
    row = selected_rows[0].row() if selected_rows else recipe_table.rowCount() - 1
    recipe_table.removeRow(row)
    renumber_recipe_steps(recipe_table)
    recipe_table.selectRow(max(0, row - 1))


def clear_recipe_steps(recipe_table):
    recipe_table.setRowCount(1)
    populate_recipe_row(recipe_table, 0, "1")
    recipe_table.selectRow(0)


def populate_recipe_row(recipe_table, row, step_number):
    values = [step_number, "0", "0 min", "0", "0", "0", "0", "0", "0", "0"]
    for column, value in enumerate(values):
        item = recipe_item(value, editable=column not in (0, 1, 3))
        item.setTextAlignment(Qt.AlignCenter)
        if column == 1:
            style_recipe_total_item(item)
        if column == 3:
            style_recipe_rh_item(item)
        recipe_table.setItem(row, column, item)


def renumber_recipe_steps(recipe_table):
    for row in range(recipe_table.rowCount()):
        item = recipe_table.item(row, 0)
        if item is None:
            item = recipe_item("", editable=False)
            item.setTextAlignment(Qt.AlignCenter)
            recipe_table.setItem(row, 0, item)
        item.setText(str(row + 1))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)


def recipe_item(value, editable=True):
    item = QTableWidgetItem(value)
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    if editable:
        flags |= Qt.ItemIsEditable
    item.setFlags(flags)
    return item


def recipe_event(recipe_table, row):
    item = recipe_table.item(row, 0)
    return str(item.data(Qt.UserRole) or "") if item is not None else ""


def set_recipe_event(recipe_table, row, event_name):
    item = recipe_table.item(row, 0)
    if item is not None:
        item.setData(Qt.UserRole, event_name.strip())


def style_recipe_total_item(item):
    """Visually distinguish the read-only, calculated Step Total column."""
    item.setData(Qt.BackgroundRole, QColor("#eff6ff"))
    item.setData(Qt.ForegroundRole, QColor("#1d4ed8"))
    item.setToolTip("Calculated from the six MFC setpoints.")


def style_recipe_rh_item(item):
    """Visually distinguish the read-only humidity derived from MFC4."""
    item.setData(Qt.BackgroundRole, QColor("#f5f3ff"))
    item.setData(Qt.ForegroundRole, QColor("#6d28d9"))
    item.setToolTip("Calculated from MFC4 flow and the target total flow.")


def set_recipe_editable(recipe_table, action_buttons, enabled):
    triggers = (
        QAbstractItemView.DoubleClicked
        | QAbstractItemView.EditKeyPressed
        | QAbstractItemView.SelectedClicked
        if enabled
        else QAbstractItemView.NoEditTriggers
    )
    recipe_table.setEditTriggers(triggers)
    recipe_table.setEnabled(enabled)
    recipe_table.setStyleSheet(
        """
        QTableWidget {
            background: #f1f5f9;
            alternate-background-color: #f8fafc;
            border-color: #dbe3ee;
            color: #94a3b8;
            selection-background-color: #f1f5f9;
            selection-color: #94a3b8;
        }
        QTableWidget::item {
            background: #f1f5f9;
            color: #94a3b8;
            border-radius: 0;
        }
        QHeaderView::section {
            background: #e8edf3;
            color: #94a3b8;
        }
        """
        if not enabled
        else ""
    )
    for button in action_buttons:
        button.setEnabled(enabled)
