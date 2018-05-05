import re

from PyQt5 import QtWidgets, QtGui

props_re = re.compile("([^_]+)_(color_)?(.+)_([^_]+)")

def color_button_factory(button, button_name):
    def color_button_dialog():
        col = QtWidgets.QColorDialog.getColor()
        if col.isValid():
            button.setStyleSheet("QWidget#%s { background-color: %s }" %
                                 (button_name, col.name()))
            # button.palette().color(QtWidgets.QPalette.Background).name()

    return color_button_dialog


def populate_properties_dialog(properties_ui,
                               item,
                               update_data_only=False,
                               **kwargs):
    dialog_widgets = vars(properties_ui)
    for widget_name in dialog_widgets:
        parsed_widget = props_re.match(widget_name)
        if parsed_widget is None:
            continue
        widget = dialog_widgets[widget_name]
        category, is_color, widget_item, prop_name = parsed_widget.groups()
        if category == "prop":
            item_props = item.get_item_props(widget_item)
            if is_color:
                if not update_data_only:
                    widget.clicked.connect(
                        color_button_factory(widget, widget_name))
                widget.setStyleSheet("QWidget#%s { background-color: %s }" %
                                     (widget_name, item_props[prop_name]))
            # http://stackoverflow.com/a/22798753/1457481
            elif type(widget) == QtWidgets.QComboBox:
                index = widget.findText(item_props[prop_name])
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif type(widget) == QtWidgets.QCheckBox or type(
                    widget) == QtWidgets.QRadioButton:
                widget.setChecked(item_props[prop_name])
            elif type(widget) == QtWidgets.QLineEdit or type(
                    widget) == QtWidgets.QLabel:
                widget.setText(item_props[prop_name])
            elif type(widget) == QtWidgets.QTextEdit:
                widget.clear()
                widget.insertPlainText(item_props[prop_name])
            else:
                widget.setValue(item_props[prop_name])
        if category == "show":
            if widget_item in kwargs:
                attribute = kwargs[widget_item][prop_name]
            else:
                item_data = getattr(item, widget_item)
                attribute = getattr(item_data, prop_name)
            if type(widget) == QtWidgets.QTextEdit:
                widget.clear()
                widget.insertPlainText(attribute)
            elif type(widget) == QtWidgets.QLineEdit or type(
                    widget) == QtWidgets.QLabel:
                widget.setText(attribute)
        if category == "do" and not update_data_only:
            if widget_item in kwargs:
                action = kwargs[widget_item][prop_name]
            else:
                item_data = getattr(item, widget_item)
                action = getattr(item_data, prop_name)
            if type(widget) == QtWidgets.QPushButton:
                widget.clicked.connect(action)


def parse_properties_dialog(properties_ui, item, post_hook=None):
    dialog_widgets = vars(properties_ui)
    for widget_name in dialog_widgets:
        parsed_widget = props_re.match(widget_name)
        if parsed_widget is None:
            continue
        widget = dialog_widgets[widget_name]
        category, is_color, widget_item, prop_name = parsed_widget.groups()
        if category == "prop":
            item_props = item.get_item_props(widget_item)
            if is_color:
                item_props[prop_name] = widget.palette().color(
                    QtGui.QPalette.Background).name()
            # http://stackoverflow.com/a/6062987/1457481
            elif type(widget) == QtWidgets.QComboBox:
                item_props[prop_name] = str(widget.currentText())
            elif type(widget) == QtWidgets.QCheckBox or type(
                    widget) == QtWidgets.QRadioButton:
                item_props[prop_name] = widget.isChecked()
            elif type(widget) == QtWidgets.QLineEdit or type(
                    widget) == QtWidgets.QLabel:
                item_props[prop_name] = widget.text()
            elif type(widget) == QtWidgets.QTextEdit:
                item_props[prop_name] = widget.toPlainText()
            else:
                item_props[prop_name] = widget.value()
    if post_hook is not None:
        for f in post_hook:
            f()  # could pass self to post_hook?


def update_data_button_factory(item, post_hook=None):
    def update_data():
        data_table = item.item_table_ui.data_table
        data = []
        m = data_table.rowCount()
        n = data_table.columnCount()
        for i in range(m):
            row = []
            row_empty = True
            for j in range(n):
                cell = data_table.item(i, j)
                if cell is not None:
                    row_empty = False
                    if cell.text():
                        row.append(cell.text())
                    else:
                        row.append('0')
                else:
                    row.append('0')
            if not row_empty:
                data.append(row)
        item.auttitude_data.input_data = data
        item.reload_data_from_internal()
        selected = data_table.selectedIndexes()
        si = sj = 0
        if len(selected) == 1:
            si = selected[0].row()
            sj = selected[0].column()
        if post_hook is not None:
            for f in post_hook:
                f()
        set_selected_item(data_table, si, sj)
    return update_data


# TODO: abstract these to a class, should be better by now
def clear_table(table):
    for i in reversed(range(table.rowCount())):
        table.removeRow(i)
    table.setRowCount(0)
    table.setColumnCount(0)

def set_selected_item(table, i, j):
    m = table.rowCount()
    n = table.columnCount()
    i = min(i, m)
    j = min(j, n)
    cell = table.item(i, j)
    #table.scrollToItem(cell)
    table.setCurrentItem(cell)


def populate_item_table(item):  # TODO: keep selection
    data = item.auttitude_data.input_data
    table = item.item_table_ui.data_table
    clear_table(table)
    m = len(data)
    n = len(data[0])
    table.setRowCount(m + 10)
    table.setColumnCount(n)
    if item.kwargs["data_headers"] is not None:
        table.setHorizontalHeaderLabels(item.kwargs["data_headers"])
    for i in range(m):
        for j in range(n):
            table.setItem(
                i, j, QtWidgets.QTableWidgetItem(str(data[i][j])))
