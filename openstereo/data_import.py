import re
import csv
from io import StringIO
import xlrd
from os import path

from PyQt5 import QtWidgets

from openstereo.ui.import_dialog_ui import Ui_Dialog as import_dialog_Ui_Dialog

keep_chars = re.compile("\W+")


class ImportDialog(QtWidgets.QDialog, import_dialog_Ui_Dialog):
    direction_names = ["direction", "dipdirection", "dd", "clar"]
    dip_names = [
        "dip",
    ]
    trend_names = ["trend", "azimuth," "direction", "dipdirection"]
    plunge_names = ["plunge", "dip"]
    alpha_names = ["alpha", "angle", "semiapicalangle", "opening"]
    sample_size = 1024

    def __init__(self,
                 parent=None,
                 data_type=None,
                 direction=False,
                 fname=None):
        super(ImportDialog, self).__init__(parent)
        self.setupUi(self)

        self.csv_sniffer = csv.Sniffer()
        self.sample = None
        self.ext = None
        self.fname.editingFinished.connect(self.on_file_changed)
        self.browse.clicked.connect(self.on_browse)
        for widget in (self.lines, self.planes, self.small_circle,
                       self.circular):
            widget.toggled.connect(self.on_type_changed)
        self.planetype.currentIndexChanged.connect(self.on_type_changed)
        self.delimiter.editingFinished.connect(self.on_delimiter_changed)
        self.has_header.stateChanged.connect(self.on_header_changed)
        self.header_row.valueChanged.connect(self.on_header_changed)
        self.do_skip.stateChanged.connect(self.on_skip_rows)
        self.skip_rows.valueChanged.connect(self.on_skip_rows)
        self.header = []
        self.dialect = None
        self.geoeas = False
        self.on_type_changed()
        if data_type:
            self.data_type = data_type
        if direction:
            self.planetype.setCurrentIndex(1)
        if fname:
            self.fname.setText(fname)
            self.on_file_changed()

    def get_header(self):
        if self.ext not in [".xlsx", ".xls"]:
            if self.geoeas:
                return self.header
            else:
                reader = csv.reader(StringIO(self.sample), self.dialect)
                header_row = self.header_row.value()
                if self.do_skip.isChecked():
                    header_row += self.skip_rows.value()
                for lineno in range(header_row + 1):
                    header = next(reader)
                return header
        else:
            book = xlrd.open_workbook(self.fname.text())
            sheet = book.sheet_by_name(self.worksheet.currentText())
            header_row = self.header_row.value()
            if self.do_skip.isChecked():
                header_row += self.skip_rows.value()
            return sheet.row_values(header_row)

    def set_headers_on_dialog(self, headers):
        for widget in (self.longitude, self.colatitude, self.alpha):
            widget.clear()
            for header in headers:
                widget.addItem(str(header))

    def sniff_columns(self):
        n_headers = self.longitude.count()
        self.longitude.setCurrentIndex(min(n_headers, 0))
        self.colatitude.setCurrentIndex(min(n_headers, 1))
        self.alpha.setCurrentIndex(min(n_headers, 2))
        if self.lines.isChecked() or self.small_circle.isChecked()\
                or self.circular.isChecked():
            for i, column in enumerate(self.header):
                if keep_chars.sub('', column).lower() in self.trend_names:
                    self.longitude.setCurrentIndex(i)
                    break
            for i, column in enumerate(self.header):
                if keep_chars.sub('', column).lower() in self.plunge_names:
                    self.colatitude.setCurrentIndex(i)
                    break
            if self.small_circle.isChecked():
                for i, column in enumerate(self.header):
                    if keep_chars.sub('', column).lower() in self.alpha_names:
                        self.alpha.setCurrentIndex(i)
                        break
        elif self.planes.isChecked():
            for i, column in enumerate(self.header):
                if keep_chars.sub('', column).lower() in self.direction_names:
                    self.longitude.setCurrentIndex(i)
                    break
            for i, column in enumerate(self.header):
                if keep_chars.sub('', column).lower() in self.dip_names:
                    self.colatitude.setCurrentIndex(i)
                    break

    def sniff_geoEAS(self, f):
        self.title = f.readline().strip()
        try:
            nvars = int(f.readline())
        except ValueError:
            self.geoeas = False
            f.seek(0)
            return False
        self.header = [f.readline().strip() for i in range(nvars)]
        self.offset = f.tell()
        self.geoeas = True
        return True

    def sniff_dialect(self):
        self.dialect = self.csv_sniffer.sniff(self.sample)
        return self.dialect

    def sniff_header(self, header):
        for field in header:
            try:
                float(str(field))
                return False
            except ValueError:
                pass
        return True

    def on_file_changed(self):
        fname = self.fname.text()
        if not path.exists(fname):
            return
        name, self.ext = path.splitext(fname)
        if self.ext in [".xls", ".xlsx"]:
            self.worksheet.clear()
            self.worksheet.setEnabled(True)
            self.offset = 0
            self.do_skip.setChecked(False)
            self.skip_rows.setValue(0)
            self.header_row.setValue(0)
            self.delimiter.setEnabled(False)
            self.delimiter.setText('')

            book = xlrd.open_workbook(self.fname.text())
            worksheets = book.sheet_names()
            for worksheet in worksheets:
                self.worksheet.addItem(worksheet)

            self.header = self.get_header()
            if self.sniff_header(self.header):
                self.has_header.setChecked(True)
            else:
                self.has_header.setChecked(False)

            self.on_worksheet_changed()
            self.dialect = None
        elif self.ext in [".ply", ".shp"]:
            pass
        else:
            self.worksheet.clear()
            self.worksheet.setEnabled(False)
            self.offset = 0
            self.do_skip.setChecked(False)
            self.skip_rows.setValue(0)
            self.header_row.setValue(0)
            self.delimiter.setEnabled(True)

            # try:
            with open(fname, "r") as f:
                geoeas = self.sniff_geoEAS(f)
                if geoeas:
                    self.has_header.setEnabled(False)
                    self.header_row.setEnabled(False)
                else:
                    self.has_header.setEnabled(True)
                    self.header_row.setEnabled(True)
                current_pos = f.tell()
                self.sample = f.read(self.sample_size)
                f.seek(current_pos)
                self.dialect = self.sniff_dialect()
                self.delimiter.setText(repr(self.dialect.delimiter))
                self.header = self.get_header()
                if self.csv_sniffer.has_header(self.sample) or geoeas:
                    self.has_header.setChecked(True)
                else:
                    self.has_header.setChecked(False)
                self.header_row.setValue(0)
                self.on_header_changed()
                self.sniff_columns()

    def on_worksheet_changed(self):
        self.on_header_changed()

    def on_delimiter_changed(self):
        self.dialect.delimiter = str(
            self.delimiter.text()).strip("'").strip('"')
        self.on_header_changed()

    def on_skip_rows(self):
        fname = self.fname.text()
        name, self.ext = path.splitext(fname)
        if self.ext in [".xls", ".xlsx"]:
            pass
        else:
            if self.do_skip.isChecked():
                skip_rows = self.skip_rows.value()
            else:
                skip_rows = 0
            with open(fname, "r") as f:
                f.seek(self.offset)
                for i in range(skip_rows):
                    f.readline()
                self.sample = f.read(self.sample_size)
        self.on_header_changed()

    def on_header_changed(self):
        self.header = self.get_header()
        if self.has_header.isChecked():
            self.set_headers_on_dialog(self.header)
        else:
            self.set_headers_on_dialog(list(range(len(self.header))))
        self.sniff_columns()

    def on_type_changed(self):
        if self.lines.isChecked() or self.small_circle.isChecked()\
                or self.circular.isChecked():
            self.longitude_label.setText("Trend")
            self.longitude.setEnabled(True)
            self.colatitude_label.setText("Plunge")
            self.colatitude.setEnabled(not self.circular.isChecked())
            self.alpha.setEnabled(self.small_circle.isChecked())
        elif self.planes.isChecked():
            if self.planetype.currentIndex() == 0:
                self.longitude_label.setText("Dip Direction")
            else:
                self.longitude_label.setText("Direction")
            self.longitude.setEnabled(True)
            self.colatitude_label.setText("Dip")
            self.colatitude.setEnabled(True)
            self.alpha.setEnabled(False)
        self.sniff_columns()

    def on_browse(self):
        fname, extension =\
            QtWidgets.QFileDialog.getOpenFileName(self, 'Import Data')
        if not fname:
            return
        self.fname.setText(fname)
        self.on_file_changed()

    @property
    def import_kwargs(self):
        kwargs = {
            "worksheet":
            self.worksheet.currentIndex(),
            "keep_input":
            True,
            "line":
            self.lines.isChecked() or self.small_circle.isChecked(),
            "dip_direction":
            self.planetype.currentIndex() == 0,
            "dipdir_column":
            self.longitude.currentIndex(),
            "dip_column":
            self.colatitude.currentIndex(),
            "alpha_column":
            self.alpha.currentIndex(),
            "circular":
            self.circular.isChecked(),
            "data_headers":
            self.header if self.has_header.isChecked() else None,
            "has_header":
            self.has_header.isChecked(),
            "header_row":
            self.header_row.value() if self.has_header.isChecked() else None,
            "skip_rows":
            self.skip_rows.value() if self.do_skip.isChecked() else None,
            "is_geoeas":
            self.geoeas,
            "geoeas_offset":
            self.offset if self.geoeas else None
        }
        if self.dialect is not None:
            kwargs["dialect_data"] = {
                "delimiter": self.dialect.delimiter,
                "doublequote": self.dialect.doublequote,
                "escapechar": self.dialect.escapechar,
                "lineterminator": self.dialect.lineterminator,
                "quotechar": self.dialect.quotechar,
                "quoting": self.dialect.quoting,
                "skipinitialspace": self.dialect.skipinitialspace
            }
        return kwargs

    @import_kwargs.setter
    def import_kwargs(self, kwargs):
        pass

    @property
    def data_type(self):
        if self.lines.isChecked():
            return "line_data", "L"
        elif self.small_circle.isChecked():
            return "smallcircle_data", "SC"
        elif self.circular.isChecked():
            return "circular_data", "AZ"
        elif self.planes.isChecked():
            return "plane_data", "P"

    @data_type.setter
    def data_type(self, data_type):
        if data_type == "line_data":
            self.lines.setChecked(True)
        elif data_type == "smallcircle_data":
            self.small_circle.setChecked(True)
        elif data_type == "circular_data":
            self.circular.setChecked(True)
        elif data_type == "plane_data":
            self.planes.setChecked(True)

    def get_data(self):
        fname = self.fname.text()
        name, self.ext = path.splitext(fname)
        if self.ext in [".xls", ".xlsx"]:
            book = xlrd.open_workbook(fname)
            sheet = book.sheet_by_name(self.worksheet.currentText())
            header_row = 0
            if self.has_header.isChecked():
                header_row += self.header_row.value() + 1
            if self.do_skip.isChecked():
                header_row += self.skip_rows.value()
            return [
                sheet.row_values(i) for i in range(header_row, sheet.nrows)
            ]
        else:
            f = open(fname, "r")
            f.seek(self.offset)
            if self.do_skip.isChecked():
                skip_rows = self.skip_rows.value()
            else:
                skip_rows = 0
            if self.has_header.isChecked():
                skip_rows += self.header_row.value() + 1
            reader = csv.reader(f, self.dialect)
            for i in range(skip_rows):
                next(reader)
            return reader


def get_data(fname, kwargs):
    name, ext = path.splitext(fname)
    if ext in [".xls", ".xlsx"]:
        book = xlrd.open_workbook(fname)
        sheet = book.sheet_by_name(kwargs['booksheet'])
        header_row = 0 if\
            kwargs['header_row'] is None else kwargs['header_row'] + 1
        header_row += 0\
            if kwargs['skip_rows'] is None else kwargs['skip_rows']
        return [sheet.row_values(i) for i in range(header_row, sheet.nrows)]
    else:
        f = open(fname, "r")
        if kwargs['is_geoeas']:
            f.seek(kwargs['geoeas_offset'])
        skip_rows = 0\
            if kwargs['header_row'] is None else kwargs['header_row'] + 1
        skip_rows += 0\
            if kwargs['skip_rows'] is None else kwargs['skip_rows']
        dialect_data = {}
        for key, item in list(kwargs["dialect_data"].items()):
            dialect_data[key] = str(item) if isinstance(item, str) else item
        reader = csv.reader(f, **dialect_data)
        for i in range(skip_rows):
            next(reader)
        return reader
