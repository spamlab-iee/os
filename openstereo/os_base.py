#!/usr/bin/python
# -*- coding: utf-8 -*-
import csv
import json
import shutil
import sys
from sys import argv
import zipfile
import os
from datetime import datetime
from itertools import tee
from os import path
from tempfile import mkdtemp
import traceback
import webbrowser
import codecs
from math import degrees

utf8_reader = codecs.getreader("utf-8")

from appdirs import user_data_dir

# data_dir = user_data_dir("OpenStereo")
# if not path.exists(data_dir):
#     os.makedirs(data_dir)

# import importlib_resources

import matplotlib

matplotlib.use("Qt5Agg")  # noqa: E402
import numpy as np
import shapefile
from PyQt5 import QtCore, QtGui, QtWidgets

_translate = QtCore.QCoreApplication.translate

import openstereo.os_auttitude as autti
import auttitude as au
from openstereo.io import get_data, ImportDialog, Importer
from openstereo.data_models import (
    AttitudeData,
    CircularData,
    LineData,
    PlaneData,
    SmallCircleData,
)
from openstereo.data_models import FaultData
from openstereo.data_models import (
    SinglePlane,
    SingleArc,
    SingleLine,
    SingleSmallCircle,
    Slope,
)
from openstereo.data_models import DataItem, GroupItem
from openstereo.os_math import net_grid, bearing, haversine, dcos_lines
from openstereo.os_plot import ClassificationPlot, RosePlot, StereoPlot
from openstereo.plot_data import (
    CirclePlotData,
    ClassificationPlotData,
    ProjectionPlotData,
    RosePlotData,
)
from openstereo.projection_models import EqualAngleProj, EqualAreaProj
from openstereo.tools.mesh_process import MeshDialog
from openstereo.ui.merge_data_ui import Ui_Dialog as merge_data_Ui_Dialog
from openstereo.ui.openstereo_ui import Ui_MainWindow
from openstereo.ui.os_settings_ui import Ui_Dialog as os_settings_Ui_Dialog
from openstereo.ui.rotate_data_ui import Ui_Dialog as rotate_data_Ui_Dialog
from openstereo.ui.difference_vectors_ui import (
    Ui_Dialog as difference_vectors_Ui_Dialog,
)
from openstereo.ui.fault_data_ui import Ui_Dialog as fault_data_Ui_Dialog
from openstereo.ui.item_table_ui import Ui_Dialog as item_table_Ui_Dialog
from openstereo.ui.ui_interface import (
    parse_properties_dialog,
    populate_properties_dialog,
    update_data_button_factory,
    populate_item_table,
    apply_action_factory,
)
from openstereo.ui import waiting_effects
from openstereo.ui import openstereo_rc
from openstereo.ui.languages import os_languages
from ply2atti import extract_colored_faces

extract_colored_faces = waiting_effects(extract_colored_faces)

print(sys.version)
# print("current data_dir:", data_dir)

__version__ = "0.9u"

os_qsettings = QtCore.QSettings("OpenStereo", "OpenStereo")


def memory_usage_psutil():
    # return the memory usage in MB
    import psutil
    import os

    process = psutil.Process(os.getpid())
    mem = process.memory_info()[0] / float(2 ** 20)
    return mem


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return list(zip(a, b))


class OSSettings(object):
    def __init__(self):
        self.rotation_settings = {"azim": 0.0, "plng": 0.0, "rake": 0.0}
        self.projection_settings = {
            "gcspacing": 10.0,
            "scspacing": 10.0,
            "cardinalborder": 2.0,
        }
        self.GC_settings = {
            "linewidths": 0.25,
            "colors": "#808080",
            "linestyles": "-",
        }
        self.SC_settings = {
            "linewidths": 0.25,
            "colors": "#808080",
            "linestyles": "-",
        }
        self.mLine_settings = {
            "linewidth": 1.00,
            "color": "#00CCCC",
            "linestyle": "-",
        }
        self.mGC_settings = {
            "linewidth": 1.00,
            "color": "#555555",
            "linestyle": ":",
        }
        self.check_settings = {
            "grid": False,
            "rotate": False,
            "cardinal": True,
            "cardinalborder": True,
            "colorbar": True,
            "colorbarpercentage": True,
            "measurelinegc": True,
        }
        self.rose_check_settings = {
            "outer": True,
            "autoscale": False,
            "scaletxt": True,
            "rings": True,
            "diagonals": True,
            "360d": True,
            "180d": False,
            "interval": False,
        }
        self.rose_settings = {
            "outerperc": 10.0,
            "ringsperc": 2.5,
            "diagonalsang": 22.5,
            "diagonalsoff": 0.0,
            "outerwidth": 1.0,
            "ringswidth": 0.5,
            "diagonalswidth": 0.5,
            "from": 0.0,
            "to": 180.0,
            "scaleaz": 90.0,
            "outerc": "#000000",
            "ringsc": "#555555",
            "diagonalsc": "#555555",
        }
        self.general_settings = {
            "fontsize": "x-small",
            "projection": "Equal-Area",
            "hemisphere": "Lower",
            "colorbar": "",
            "title": "",
            "description": "",
            "author": "",
            "lastsave": "",
            "packeddata": "no",
        }

    @property
    def item_settings(self):
        all_settings = {}
        for name, settings in list(vars(self).items()):
            if name.endswith("_settings"):
                all_settings[name] = settings.copy()
        return all_settings

    @item_settings.setter
    def item_settings(self, data):
        for name, settings in list(data.items()):
            setattr(self, name, settings)

    def get_item_props(self, item_name):
        return getattr(self, item_name.replace(" ", "_") + "_settings")


class Main(QtWidgets.QMainWindow, Ui_MainWindow):
    data_types = {
        data_type.data_type: data_type
        for data_type in (
            AttitudeData,
            PlaneData,
            LineData,
            SmallCircleData,
            CircularData,
            FaultData,
            SinglePlane,
            SingleArc,
            SingleLine,
            SingleSmallCircle,
            Slope,
        )
    }

    max_recent_projects = 5

    def __init__(self):
        super(Main, self).__init__()
        self.setupUi(self)

        self.OS_settings = OSSettings()
        self.settings = {
            "fontsize": "x-small",
            "title": "",
            "summary": "",
            "description": "",
            "author": "",
            "credits": "",
            "last_saved": "",
        }

        self.id_counter = 0

        self.projections = {
            "Equal-Area": EqualAreaProj(self.OS_settings),
            "Equal-Angle": EqualAngleProj(self.OS_settings),
        }

        # self.projection_option = QtWidgets.QActionGroup(self, exclusive=True)
        # self.projection_option.addAction(self.actionEqual_Area)
        # self.projection_option.addAction(self.actionEqual_Angle)

        self.actionImport_Plane_Data_DD.triggered.connect(
            lambda: self.import_files(
                data_type="plane_data",
                direction=False,
                dialog_title=_translate("main", "Import plane data"),
            )
        )
        self.actionImport_Plane_Data_Dir.triggered.connect(
            lambda: self.import_files(
                data_type="plane_data",
                direction=True,
                dialog_title=_translate("main", "Import plane data"),
            )
        )
        self.actionImport_Line_Data_Trend.triggered.connect(
            lambda: self.import_files(
                data_type="line_data",
                direction=False,
                dialog_title=_translate("main", "Import line data"),
            )
        )
        self.actionImport_Small_Circle_Data.triggered.connect(
            lambda: self.import_files(
                data_type="smallcircle_data",
                direction=False,
                dialog_title=_translate("main", "Import Small Circle data"),
            )
        )
        self.actionImport_Circular_Data_Trend.triggered.connect(
            lambda: self.import_files(
                data_type="circular_data",
                direction=False,
                dialog_title=_translate("main", "Import Azimuth data"),
            )
        )

        self.actionOpen_fault_data_Plane_Line_Sense.triggered.connect(
            lambda: self.import_fault_data(
                plane_columns=(0, 1), line_columns=(2, 3), sense_column=4
            )
        )

        self.actionOpen_fault_data_PlaneDir_Line_Sense.triggered.connect(
            lambda: self.import_fault_data(
                direction=True,
                plane_columns=(0, 1),
                line_columns=(2, 3),
                sense_column=4,
            )
        )

        self.actionOpen_TectonicsFP_Fault_Data.triggered.connect(
            lambda: self.import_fault_data(
                plane_columns=(1, 2),
                line_columns=(3, 4),
                sense_column=0,
                comment=";",
                delimiter=",",
                has_header=False,
            )
        )

        self.actionOpen_T_TECTO_Fault_Data.triggered.connect(
            lambda: self.import_fault_data(
                plane_columns=(2, 3),
                line_columns=(2, 3, 4),
                sense_column=1,
                rake_sense_column=5,
                delimiter=" ",
                has_header=False,
            )
        )

        self.actionAdd_Plane.triggered.connect(
            lambda: self.add_single_data(
                "singleplane_data",
                _translate("main", "Plane"),
                dialog_title=_translate("main", "Add Plane"),
            )
        )
        self.actionAdd_Line.triggered.connect(
            lambda: self.add_single_data(
                "singleline_data",
                _translate("main", "Line"),
                dialog_title=_translate("main", "Add Line"),
            )
        )
        self.actionAdd_Small_Circle.triggered.connect(
            lambda: self.add_single_data(
                "singlesc_data",
                _translate("main", "Small Circle"),
                dialog_title=_translate("main", "Add Small Circle"),
            )
        )
        self.actionAdd_Slope.triggered.connect(
            lambda: self.add_single_data(
                "slope_data",
                _translate("main", "Slope"),
                dialog_title=_translate("main", "Add Slope"),
            )
        )
        self.actionAdd_Arc.triggered.connect(
            lambda: self.add_single_data(
                "singlearc_data",
                _translate("main", "Arc"),
                dialog_title=_translate("main", "Add Arc"),
            )
        )
        self.actionAssemble_Fault.triggered.connect(
            lambda: self.fault_data_dialog()
        )
        self.actionAdd_Group.triggered.connect(
            lambda: self.add_group(name="Group")
        )

        self.actionNew.triggered.connect(self.new_project)
        self.actionSave.triggered.connect(self.save_project_dialog)
        self.actionSave_as.triggered.connect(self.save_project_as_dialog)
        self.actionOpen.triggered.connect(self.open_project_dialog)
        self.actionSave_as_Packed_Project.triggered.connect(
            lambda: self.save_project_as_dialog(pack=True)
        )
        self.actionImport.triggered.connect(self.import_dialog)

        self.actionSettings.triggered.connect(self.show_settings_dialog)
        self.actionPreferences.triggered.connect(self.show_preferences_dialog)

        self.actionChange_Language.triggered.connect(self.show_language_dialog)

        self.actionRotate_on_Drag.triggered.connect(self.set_drag_rotate_mode)

        self.actionUnpack_Project_to.triggered.connect(self.unpack_data_dialog)

        self.actionMerge_Data.triggered.connect(
            lambda: self.merge_data_dialog()
        )
        self.actionRotate_Data.triggered.connect(
            lambda: self.rotate_data_dialog()
        )

        self.actionConvert_Shapefile_to_Azimuth_data.triggered.connect(
            self.import_shapefile
        )
        self.actionConvert_Mesh_to_Plane_Data.triggered.connect(
            self.import_mesh
        )

        self.actionCalculate_difference_vectors.triggered.connect(
            lambda: self.difference_vectors_dialog()
        )

        self.recent_projects = []
        for i in range(self.max_recent_projects):
            self.recent_projects.append(
                QtWidgets.QAction(
                    self, visible=False, triggered=self.open_recent_project
                )
            )

        for i in range(self.max_recent_projects):
            self.menuFile.insertAction(
                self.actionSave, self.recent_projects[i]
            )

        self.recent_projects_separator = self.menuFile.insertSeparator(
            self.actionSave
        )
        self.recent_projects_separator.setVisible(False)

        self.actionAbout.triggered.connect(self.show_about)
        self.actionDocumentation.triggered.connect(self.show_documentation)
        self.actionTutorial.triggered.connect(self.show_tutorial)
        self.actionSubmit_Issue.triggered.connect(self.show_submit_issue)

        self.plotButton.clicked.connect(self.plot_data)
        self.settingsButton.clicked.connect(self.show_settings_dialog)
        self.clearButton.clicked.connect(self.clear_plot)

        self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(
            self.tree_context_menu
        )
        # http://stackoverflow.com/a/4170541/1457481
        self.treeWidget.setDragDropMode(
            QtWidgets.QAbstractItemView.InternalMove
        )

        self.save_shortcut = QtWidgets.QShortcut(
            "Ctrl+S", self, self.save_project_dialog
        )
        self.save_as_shortcut = QtWidgets.QShortcut(
            "Ctrl+Shift+S", self, self.save_project_as_dialog
        )
        self.open_shortcut = QtWidgets.QShortcut(
            "Ctrl+O", self, self.open_project_dialog
        )

        self.rename_shortcut = QtWidgets.QShortcut(
            "F2", self, self.rename_dataitem
        )

        self.copy_shortcut = QtWidgets.QShortcut(
            "Ctrl+C", self, self.copy_props_dataitem
        )
        self.paste_shortcut = QtWidgets.QShortcut(
            "Ctrl+V", self, self.paste_props_dataitem
        )

        self.plot_shortcut = QtWidgets.QShortcut(
            "Ctrl+P", self, self.plot_data
        )
        self.clear_shortcut = QtWidgets.QShortcut(
            "Ctrl+L", self, self.clear_plot
        )
        self.settings_shortcut = QtWidgets.QShortcut(
            "Ctrl+,", self, self.show_settings_dialog
        )

        self.add_plane_shortcut = QtWidgets.QShortcut(
            "Ctrl+1", self, self.add_single_plane_from_plot
        )
        self.add_line_shortcut = QtWidgets.QShortcut(
            "Ctrl+2", self, self.add_single_line_from_plot
        )
        self.add_sc_shortcut = QtWidgets.QShortcut(
            "Ctrl+3", self, self.add_single_sc_from_plot
        )

        self.add_diff_line_shortcut = QtWidgets.QShortcut(
            "Shift+2", self, self.add_single_diff_line_from_plot
        )

        self.add_arc_shortcut = QtWidgets.QShortcut(
            "Shift+1", self, self.add_arc_from_plot
        )

        # experimental
        self.set_drag_rotate_mode_shortcut = QtWidgets.QShortcut(
            "Ctrl+R", self, self.set_drag_rotate_mode
        )

        self.cb = QtWidgets.QApplication.clipboard()

        self.current_project = None
        self.old_project = None
        self.packed_project = False
        self.temp_dir = None
        self.update_recent_projects()
        self.statusBar().showMessage("Ready")
        self.set_title()
        # self.check_save_guard()

    def projection(self):
        return self.projections[
            self.OS_settings.general_settings["projection"]
        ]

    def clear_plot(self):
        self.projection_plot.plot_projection_net()
        self.projection_plot.draw_plot()
        self.rose_plot.draw_plot()
        self.classification_plot.draw_plot()
        self.statusBar().showMessage(_translate("main", "Ready"))

    def add_plots(self):
        self.projection_plot = StereoPlot(
            self.OS_settings, self.projection, self.projectionTab
        )
        self.rose_plot = RosePlot(self.OS_settings, self.roseTab)
        self.classification_plot = ClassificationPlot(
            self.OS_settings, self.classificationTab
        )
        self.clear_plot()

    def set_title(self):
        title = _translate("main", "OpenStereo - ")
        if self.OS_settings.general_settings["title"]:
            title += self.OS_settings.general_settings["title"]
        elif self.current_project is not None:
            title += self.current_project
        else:
            title += _translate(
                "main", "Open-source, Multiplatform Stereonet Analysis"
            )
        self.setWindowTitle(title)

    def show_language_dialog(self):
        languages = os_languages.keys()
        data, ok = QtWidgets.QInputDialog.getItem(
            self,
            _translate("main", "Choose OpenStereo language"),
            _translate("main", "Language:"),
            languages,
            0,
            False,
        )
        if ok:
            os_qsettings.setValue("locale", os_languages[data])
            QtWidgets.QMessageBox.information(
                self,
                _translate("main", "Restart OpenStereo"),
                _translate(
                    "main",
                    "Please restart OpenStereo to use the changed language.",
                ),
            )

    def import_data(
        self, data_type, name, item_id=None, item_parent=None, **kwargs
    ):
        if item_parent is None:
            item_parent = self.treeWidget
        if item_id is None:
            item_id = self.assign_id()
        item = self.data_types[data_type](
            name=name, parent=item_parent, item_id=item_id, **kwargs
        )
        item.set_root(self)
        return item

    def assign_id(self):
        item_id = self.id_counter
        self.id_counter += 1
        return item_id

    def import_files(self, data_type, direction, dialog_title):
        fnames, extension = QtWidgets.QFileDialog.getOpenFileNames(
            self, dialog_title
        )
        if not fnames:
            return
        for fname in fnames:
            dialog = ImportDialog(
                parent=self,
                fname=fname,
                data_type=data_type,
                direction=direction,
                rake=False,
            )
            fname = dialog.fname.text()
            data_type, letter = dialog.data_type
            data_name = "({}) {}".format(letter, path.basename(fname))
            reader = dialog.get_data()
            self.import_data(
                data_type,
                data_name,
                data_path=fname,
                data=reader,
                **dialog.importer.import_data()
            )

    def import_dialog(
        self,
        item=None,
        try_default=False,
        data_type=None,
        direction=False,
        fname=None,
        dialog_title=_translate("main", "Import data"),
    ):
        if fname is None:
            fname, extension = QtWidgets.QFileDialog.getOpenFileName(
                self, dialog_title
            )
        if try_default and not fname:
            return
        dialog = ImportDialog(
            parent=self,
            fname=fname,
            data_type=data_type,
            direction=direction,
            rake=False,
        )
        if try_default or dialog.exec_():
            fname = dialog.fname.text()
            data_type, letter = dialog.data_type
            data_name = "({}){}".format(letter, path.basename(fname))
            reader = dialog.get_data()
            return self.import_data(
                data_type,
                data_name,
                data_path=fname,
                data=reader,
                **dialog.importer.import_data()
            )

    def add_group(self, name, parent=None):
        parent = parent if parent is not None else self.treeWidget
        return GroupItem(name=name, parent=parent, item_id=self.assign_id())

    def import_fault_data(
        self,
        plane_columns,
        line_columns,
        sense_column,
        direction=False,
        rake_sense_column=None,
        delimiter=None,
        has_header=None,
        comment=None,
        **importer_kwargs
    ):
        fnames, extension = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Import Fault Data (Plane/Line/Sense)"
        )
        if not fnames:
            return
        for fname in fnames:
            importer = Importer(
                fname=fname, data_type="plane", direction=direction
            )
            importer.process_file()
            if has_header is not None:
                importer.has_header = has_header
            if delimiter is not None:
                importer.dialect["delimiter"] = delimiter
            if comment is not None:
                importer.comment_marker = comment
            importer.longitude, importer.colatitude = plane_columns
            planes_import_data = importer.import_data()
            planes_data_reader = list(importer.get_data())
            planes_data_name = "(P) {}".format(path.basename(fname))
            if len(line_columns) == 2:
                importer.longitude, importer.colatitude = line_columns
                importer.data_type = "line"
            elif len(line_columns) == 3:
                importer.longitude, importer.colatitude, importer.obliquity = (
                    line_columns
                )
                importer.data_type = "rake"
            else:
                pass  # toolbar invalid data for ttecto?

            importer.direction = False
            lines_import_data = importer.import_data()
            lines_data_reader = list(importer.get_data())
            lines_data_name = "(L) {}".format(path.basename(fname))

            planes_item = self.import_data(
                "plane_data",
                planes_data_name,
                data_path=fname,
                data=planes_data_reader,
                **planes_import_data
            )

            lines_item = self.import_data(
                "line_data",
                lines_data_name,
                data_path=fname,
                data=lines_data_reader,
                obliquity_sense_column=rake_sense_column,
                **lines_import_data
            )

            merged_name = _translate("main", "(F) {}").format(
                path.basename(fname)
            )
            faults_item = self.import_data(
                "fault_data", merged_name, data=[planes_item, lines_item]
            )
            if sense_column is not None:
                faults_item.data_settings["sensecolumn"] = sense_column
                faults_item.data_settings["sensecolumncheck"] = True
            else:
                faults_item.data_settings["sensecolumncheck"] = False
            return planes_item, lines_item, faults_item

    def import_shapefile(self):
        fname, extension = QtWidgets.QFileDialog.getOpenFileName(
            self,
            _translate("main", "Select Shapefile to convert"),
            filter="ESRI Shapefile (*.shp);;All Files (*.*)",
        )
        if not fname:
            return
        name, ext = path.splitext(fname)

        fname_out, extension = QtWidgets.QFileDialog.getSaveFileName(
            self,
            _translate("main", "Save azimuth data as"),
            name + ".txt",
            filter="Text Files (*.txt);;All Files (*.*)",
        )
        if not fname_out:
            return
        with open(fname_out, "w") as f:
            sf = shapefile.Reader(fname)
            f.write("azimuth;length\n")
            for shape in sf.shapes():
                for A, B in pairwise(shape.points):
                    f.write(
                        "{};{}\n".format(
                            bearing(A[0], B[0], A[1], B[1]),
                            haversine(A[0], B[0], A[1], B[1]),
                        )
                    )
        self.import_dialog(
            try_default=True,
            fname=fname_out,
            data_type="circular_data",
            direction=False,
            dialog_title=_translate("main", "Import Azimuth data"),
        )

    def import_mesh(self):
        fname, extension = QtWidgets.QFileDialog.getOpenFileName(
            self,
            _translate("main", "Select Mesh to convert"),
            filter="Stanford Polygon (*.ply);;All Files (*.*)",
        )
        if not fname:
            return
        name, ext = path.splitext(fname)
        dialog = MeshDialog(self)
        if dialog.exec_():
            self.statusBar().showMessage(
                _translate("main", "Processing Mesh {}...").format(fname)
            )
            colors = dialog.colors
            if not colors:
                return
            with open(fname, "rb") as f:
                output = extract_colored_faces(f, colors)
            self.statusBar().showMessage(_translate("main", "Ready"))
            if dialog.check_separate.isChecked():
                dirname = QtWidgets.QFileDialog.getExistingDirectory(
                    self, _translate("main", "Save data files to")
                )
                if not dirname:
                    return
                color_filenames = []
                for color in list(output.keys()):
                    color_filename = "{0}_{1}.txt".format(name, color[:-1])
                    color_filenames.append((color, color_filename))
                    # https://stackoverflow.com/a/3191811/1457481
                    with open(color_filename, "w", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(
                            ["dip_direction", "dip", "X", "Y", "Z", "trace"]
                        )
                        for line in output[color]:
                            writer.writerow(line)
                for color, color_filename in color_filenames:
                    item = self.import_dialog(
                        try_default=True,
                        fname=color_filename,
                        data_type="plane_data",
                        direction=False,
                        dialog_title=_translate("main", "Import plane data"),
                    )
                    item.point_settings["c"] = "#%02x%02x%02x" % color[:-1]
                return
            else:
                fname_out, extension = QtWidgets.QFileDialog.getSaveFileName(
                    self,
                    _translate("main", "Save plane data as"),
                    name + ".txt",
                    filter="Text Files (*.txt);;All Files (*.*)",
                )
                if not fname_out:
                    return
                with open(fname_out, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            "dip_direction",
                            "dip",
                            "X",
                            "Y",
                            "Z",
                            "trace",
                            "R",
                            "G",
                            "B",
                        ]
                    )
                    for color in list(output.keys()):
                        for line in output[color]:
                            writer.writerow(line + color[:-1])
                item = self.import_dialog(
                    try_default=True,
                    fname=fname_out,
                    data_type="plane_data",
                    direction=False,
                    dialog_title=_translate("main", "Import plane data"),
                )

    def add_single_data(self, data_type, data_name, dialog_title, **kwargs):
        # TODO: change the way data is stored to pave the way for internal data
        data, ok = QtWidgets.QInputDialog.getText(
            self, dialog_title, _translate("main", "Attitude:")
        )
        if ok:
            name = "{} ({})".format(data_name, data)
            return self.import_data(
                data_type=data_type, name=name, data=data, **kwargs
            )

    def add_extracted_data(
        self, data_name, source_dataset, data_type, item_data, **kwargs
    ):
        # TODO: add the name of the source data?
        name = "{} ({})".format(data_name, source_dataset)
        item = self.import_data(data_type=data_type, name=name, **kwargs)
        item.item_settings = item_data
        return item

    def add_single_plane_from_plot(self):
        if self.projection_plot.last_from_measure is None:
            return
        else:
            a = au.Plane(self.projection_plot.last_from_measure)
        if self.projection_plot.last_to_measure is None:
            dd, d = a.attitude
            attitude = "{:.2f}/{:.2f}".format(dd, d)
            name = "Plane ({})".format(attitude)
            return self.import_data(
                data_type="singleplane_data", name=name, data=attitude
            )
        else:
            plane = au.Plane(
                a.normalized_cross_with(self.projection_plot.last_to_measure)
            )
            dd, d = plane.attitude
            attitude = "{:.2f}/{:.2f}".format(dd, d)
            name = "Plane ({})".format(attitude)
            return self.import_data(
                data_type="singleplane_data", name=name, data=attitude
            )

    def add_single_line_from_plot(self):
        if self.projection_plot.last_from_measure is None:
            return
        else:
            a = au.Line(self.projection_plot.last_from_measure)
        if self.projection_plot.last_to_measure is None:
            tr, pl = a.attitude
            attitude = "{:.2f}/{:.2f}".format(tr, pl)
            name = "Line ({})".format(attitude)
            return self.import_data(
                data_type="singleline_data", name=name, data=attitude
            )
        else:
            line = au.Line(
                a.normalized_cross_with(self.projection_plot.last_to_measure)
            )
            tr, pl = line.attitude
            attitude = "{:.2f}/{:.2f}".format(tr, pl)
            name = "Line ({})".format(attitude)
            return self.import_data(
                data_type="singleline_data", name=name, data=attitude
            )

    def add_arc_from_plot(self):
        if self.projection_plot.last_from_measure is None:
            return
        else:
            a = au.Line(self.projection_plot.last_from_measure)
        if self.projection_plot.last_to_measure is None:
            # TODO: message on toolbar
            return
        else:
            b = self.projection_plot.last_to_measure
            tr_a, pl_a = a.attitude
            tr_b, pl_b = b.attitude
            attitude_a = "{:.2f}/{:.2f}".format(tr_a, pl_a)
            attitude_b = "{:.2f}/{:.2f}".format(tr_b, pl_b)
            name = "Arc from {} to {}".format(attitude_a, attitude_b)
            return self.import_data(
                data_type="singlearc_data",
                name=name,
                data="{},{}".format(attitude_a, attitude_b),
            )

    def add_single_diff_line_from_plot(self):
        if self.projection_plot.last_from_measure is None:
            return
        else:
            a = au.Line(self.projection_plot.last_from_measure)
        if self.projection_plot.last_to_measure is None:
            # TODO: message on toolbar
            return
        else:
            b = self.projection_plot.last_to_measure
            line = a - b
            line /= line.length
            tr, pl = line.attitude
            attitude = "{:.2f}/{:.2f}".format(tr, pl)
            name = "Difference Vector ({})".format(attitude)
            return self.import_data(
                data_type="singleline_data", name=name, data=attitude
            )

    def add_single_sc_from_plot(self):
        if self.projection_plot.last_center is None:
            return
        else:
            a = au.Line(self.projection_plot.last_center)
            dd, d = a.attitude
            theta = self.projection_plot.last_theta
            attitude = "{:.2f}/{:.2f}/{:.2f}".format(dd, d, degrees(theta))
            name = "Small Circle ({})".format(attitude)
            return self.import_data(
                data_type="singlesc_data", name=name, data=attitude
            )

    def show_documentation(self):
        webbrowser.open("http://openstereo.readthedocs.io")

    def show_tutorial(self):
        webbrowser.open(
            "https://openstereo.readthedocs.io/en/latest/tutorial.html"
        )

    def show_about(self):
        msg = QtWidgets.QMessageBox()
        # msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setWindowTitle(_translate("main", "About OpenStereo 1.0"))
        msg.setText(
            _translate(
                "main",
                """
        (C) 2009-2011,2017 Carlos H. Grohmann, Ginaldo A.C. Campanha,
            Arthur Endlein Correia

        OpenStereo is a Open-source, multiplatform software for
        structural geology analysis using stereonets.
        
        OpenStereo is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version. 

        OpenStereo is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with OpenStereo.  If not, see http://www.gnu.org/licenses/.""",
            )
        )
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

    def show_submit_issue(self):
        msg = QtWidgets.QMessageBox()
        # msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setWindowTitle(
            _translate("main", "Submit report to issue tracker")
        )
        msg.setText(
            _translate(
                "main",
                """
        If something doesn't work in OpenStereo, or if you have any suggestion
        for further development, please submit an issue to our github
        repository or send an email to <arthur.correia@usp.br>.
        
        If possible, add extra information such as OpenStereo and python
        version, operating system and sample data.""",
            )
        )
        msg.addButton(
            _translate("main", "Submit Issue"),
            QtWidgets.QMessageBox.AcceptRole,
        )
        msg.setStandardButtons(QtWidgets.QMessageBox.Cancel)
        button_reply = msg.exec_()
        if button_reply == 0:  # 0 means Accept
            webbrowser.open("https://github.com/endarthur/os/issues")

    def merge_data_dialog(self, current_item=None):
        merge_dialog = QtWidgets.QDialog(self)
        merge_dialog_ui = merge_data_Ui_Dialog()
        merge_dialog_ui.setupUi(merge_dialog)
        data_items = {
            item.text(0): item
            for item in self.get_data_items()
            if isinstance(item, CircularData)
        }
        if not data_items:
            self.statusBar().showMessage(
                _translate("main", "No items to merge")
            )
            return
        for item_name in list(data_items.keys()):
            merge_dialog_ui.A.addItem(item_name)

        def A_changed(event=None):
            merge_dialog_ui.B.clear()
            A = data_items[merge_dialog_ui.A.currentText()]
            for item_name, item in list(data_items.items()):
                if item.data_type == A.data_type:
                    merge_dialog_ui.B.addItem(item_name)
            B_changed()

        def B_changed(event=None):
            A = data_items[merge_dialog_ui.A.currentText()]
            B = data_items[merge_dialog_ui.B.currentText()]
            A_name, A_ext = path.splitext(A.data_path)
            merge_dialog_ui.savename.setText(
                A_name
                + "+"
                + path.splitext(path.basename(B.data_path))[0]
                + ".txt"
            )

        # http://stackoverflow.com/a/22798753/1457481
        if current_item is not None:
            index = merge_dialog_ui.A.findText(current_item)
            if index >= 0:
                merge_dialog_ui.A.setCurrentIndex(index)
        A_changed()

        def on_browse():
            fname, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, _translate("main", "Save merged data")
            )
            if not fname:
                return
            merge_dialog_ui.savename.setText(fname)

        merge_dialog_ui.A.activated[str].connect(A_changed)
        merge_dialog_ui.B.activated[str].connect(B_changed)
        merge_dialog_ui.browse.clicked.connect(on_browse)
        if merge_dialog.exec_():
            A = data_items[merge_dialog_ui.A.currentText()]
            B = data_items[merge_dialog_ui.B.currentText()]
            merged_data = autti.concatenate(A.auttitude_data, B.auttitude_data)
            merged_name = A.text(0) + "+" + B.text(0)
            merged_fname = merge_dialog_ui.savename.text()
            if merged_data.d == 3:
                np.savetxt(merged_fname, merged_data.data_sphere)
            else:
                np.savetxt(merged_fname, merged_data.data_circle)
            if merge_dialog_ui.keep.isChecked():
                merged_item = self.data_types[A.data_type](
                    name=merged_name,
                    data_path=merged_fname,
                    data=merged_data,
                    parent=self.treeWidget,
                    **A.kwargs
                )
                merged_item.item_settings = A.item_settings
            self.statusBar().showMessage(
                _translate("main", "Merged items {} and {} as {}").format(
                    A.text(0), B.text(0), merged_name
                )
            )

    def fault_data_dialog(self, current_item=None):
        fault_dialog = QtWidgets.QDialog(self)
        fault_dialog_ui = fault_data_Ui_Dialog()
        fault_dialog_ui.setupUi(fault_dialog)
        plane_items = {
            item.text(0): item
            for item in self.get_data_items()
            if isinstance(item, PlaneData)
        }
        line_items = {
            item.text(0): item
            for item in self.get_data_items()
            if isinstance(item, LineData)
        }
        if not plane_items or not line_items:
            self.statusBar().showMessage(
                _translate("main", "No items to build faults")
            )
            return
        for item_name in plane_items:
            fault_dialog_ui.A.addItem(item_name)
        for item_name in line_items:
            fault_dialog_ui.B.addItem(item_name)

        # http://stackoverflow.com/a/22798753/1457481
        if current_item is not None:
            index = fault_dialog_ui.A.findText(current_item)
            if index >= 0:
                fault_dialog_ui.A.setCurrentIndex(index)
            index = fault_dialog_ui.B.findText(current_item)
            if index >= 0:
                fault_dialog_ui.B.setCurrentIndex(index)

        if fault_dialog.exec_():
            A = plane_items[fault_dialog_ui.A.currentText()]
            B = line_items[fault_dialog_ui.B.currentText()]
            merged_name = _translate("main", "Faults ({}, {})").format(
                A.text(0), B.text(0)
            )
            self.import_data("fault_data", merged_name, data=[A, B])
            self.statusBar().showMessage(
                _translate(
                    "main", "Built Fault set using {} and {} as {}"
                ).format(A.text(0), B.text(0), merged_name)
            )

    def rotate_data_dialog(self, current_item=None):
        rotate_dialog = QtWidgets.QDialog(self)
        rotate_dialog_ui = rotate_data_Ui_Dialog()
        rotate_dialog_ui.setupUi(rotate_dialog)
        data_items = {
            item.text(0): item
            for item in self.get_data_items()
            if isinstance(item, AttitudeData)
        }
        if not data_items:
            self.statusBar().showMessage(
                _translate("main", "No items to rotate")
            )
            return
        for item_name in list(data_items.keys()):
            rotate_dialog_ui.A.addItem(item_name)

        def data_changed(event=None):
            A = data_items[rotate_dialog_ui.A.currentText()]
            A_name, A_ext = path.splitext(A.data_path)
            rotate_dialog_ui.savename.setText(
                A_name
                + "-rot_{}_{}_{}.txt".format(
                    rotate_dialog_ui.trend.value(),
                    rotate_dialog_ui.plunge.value(),
                    rotate_dialog_ui.angle.value(),
                )
            )

        # http://stackoverflow.com/a/22798753/1457481
        def on_browse():
            fname, extension = QtWidgets.QFileDialog.getSaveFileName(
                self, _translate("main", "Save rotated data")
            )
            if not fname:
                return
            rotate_dialog_ui.savename.setText(fname)

        if current_item is not None:
            index = rotate_dialog_ui.A.findText(current_item)
            if index >= 0:
                rotate_dialog_ui.A.setCurrentIndex(index)
        data_changed()
        rotate_dialog_ui.A.activated[str].connect(data_changed)
        rotate_dialog_ui.trend.valueChanged.connect(data_changed)
        rotate_dialog_ui.plunge.valueChanged.connect(data_changed)
        rotate_dialog_ui.angle.valueChanged.connect(data_changed)
        rotate_dialog_ui.browse.clicked.connect(on_browse)
        if rotate_dialog.exec_():
            A = data_items[rotate_dialog_ui.A.currentText()]
            u = dcos_lines(
                np.radians(
                    (
                        rotate_dialog_ui.trend.value(),
                        rotate_dialog_ui.plunge.value(),
                    )
                )
            )
            rotated_data = autti.rotate(
                A.auttitude_data, u, rotate_dialog_ui.angle.value()
            )
            rotated_name = A.text(0) + "-rot_{}_{}_{}".format(
                rotate_dialog_ui.trend.value(),
                rotate_dialog_ui.plunge.value(),
                rotate_dialog_ui.angle.value(),
            )
            rotated_fname = rotate_dialog_ui.savename.text()
            np.savetxt(rotated_fname, rotated_data.data_sphere)
            if rotate_dialog_ui.keep.isChecked():
                rotated_item = self.data_types[A.data_type](
                    name=rotated_name,
                    data_path=rotated_fname,
                    data=rotated_data,
                    parent=self.treeWidget,
                    item_id=self.assign_id(),
                    **A.kwargs
                )
                rotated_item.item_settings = A.item_settings
            self.statusBar().showMessage(
                _translate("main", "Rotated item {} to {}").format(
                    A.text(0), rotated_name
                )
            )

    def difference_vectors_dialog(self, current_item=None):
        diff_dialog = QtWidgets.QDialog(self)
        diff_dialog_ui = difference_vectors_Ui_Dialog()
        diff_dialog_ui.setupUi(diff_dialog)
        data_items = {
            item.text(0): item
            for item in self.get_data_items()
            if isinstance(item, AttitudeData)
        }
        if not data_items:
            self.statusBar().showMessage(
                _translate("main", "No items to calculate difference vectors")
            )
            return
        for item_name in list(data_items.keys()):
            diff_dialog_ui.A.addItem(item_name)

        if current_item is not None:
            index = diff_dialog_ui.A.findText(current_item)
            if index >= 0:
                diff_dialog_ui.A.setCurrentIndex(index)

        # rotate_dialog_ui.A.activated[str].connect(data_changed)
        # rotate_dialog_ui.trend.valueChanged.connect(data_changed)
        # rotate_dialog_ui.plunge.valueChanged.connect(data_changed)
        # rotate_dialog_ui.angle.valueChanged.connect(data_changed)
        # rotate_dialog_ui.browse.clicked.connect(on_browse)
        if diff_dialog.exec_():
            A = data_items[diff_dialog_ui.A.currentText()]
            fname, extension = QtWidgets.QFileDialog.getSaveFileName(
                self,
                _translate("main", "Save difference vectors data"),
                "{} (diff).txt".format(A.text(0)),
                filter="Text Files (*.txt);;All Files (*.*)",
            )
            if not fname:
                return
            diff_data = []
            lengths = []
            n = A.au_object.shape[0]
            for i in range(n):
                for j in range(i + 1, n):
                    diff = A.au_object[i] - A.au_object[j]
                    length = diff.length
                    if length == 0.0:
                        continue
                    diff_data.append(diff / length)
                    lengths.append(length)
            m = len(diff_data)
            diff_data = np.array(diff_data)[np.argsort(-np.array(lengths))]

            if diff_dialog_ui.do_percentage.isChecked():
                m_kept = int(
                    m * diff_dialog_ui.percentage_largest.value() / 100.0
                )
            else:
                m_kept = int(min(m, int(diff_dialog_ui.n_largest.text())))

            diff_data = au.VectorSet(diff_data[:m_kept])

            np.savetxt(fname, diff_data.attitude)

            # if rotate_dialog_ui.keep.isChecked():
            #     rotated_item = self.data_types[A.data_type](
            #         name=rotated_name,
            #         data_path=rotated_fname,
            #         data=rotated_data,
            #         parent=self.treeWidget,
            #         item_id=self.assign_id(),
            #         **A.kwargs
            #     )
            #     rotated_item.item_settings = A.item_settings
            self.statusBar().showMessage(
                _translate(
                    "main", "Calculated difference vectors for {}"
                ).format(A.text(0))
            )

    def plot_tree_item(self, item):
        if item.checkState(0):
            if isinstance(item, GroupItem):
                for i in range(item.childCount() - 1, -1, -1):
                    subitem = item.child(i)
                    self.plot_tree_item(subitem)
            else:
                for plot_item in item.checked_plots:
                    if (
                        isinstance(plot_item, ProjectionPlotData)
                        and self.tabWidget.currentIndex() == 0
                    ):
                        self.projection_plot.plot_data(plot_item)
                    if (
                        isinstance(plot_item, RosePlotData)
                        and self.tabWidget.currentIndex() == 1
                    ):
                        self.rose_plot.plot_data(plot_item)
                    if (
                        isinstance(plot_item, ClassificationPlotData)
                        and self.tabWidget.currentIndex() == 2
                    ):
                        self.classification_plot.plot_data(plot_item)

    # @waiting_effects
    def plot_data(self):
        self.statusBar().showMessage(_translate("main", "Plotting data..."))

        # experimental
        if self.tabWidget.currentIndex() == 0:
            self.projection_plot.clear_plot_element_data()

        for index in range(self.treeWidget.topLevelItemCount() - 1, -1, -1):
            item = self.treeWidget.topLevelItem(index)
            self.plot_tree_item(item)
        if (
            self.OS_settings.check_settings["grid"]
            and self.tabWidget.currentIndex() == 0
        ):
            gc, sc = self.plot_grid()
            self.projection_plot.plot_data(gc)
            self.projection_plot.plot_data(sc)
        if self.tabWidget.currentIndex() == 0:
            self.projection_plot.draw_plot()
        elif self.tabWidget.currentIndex() == 1:
            self.rose_plot.draw_plot()
        elif self.tabWidget.currentIndex() == 2:
            self.classification_plot.draw_plot()
        self.statusBar().showMessage("Ready")

    def plot_on_update_if_checked(self):  # TODO: check this name
        if self.actionPlot_on_Update_Table.isChecked():
            self.plot_data()

    def plot_grid(self):
        gc, sc = net_grid(
            gcspacing=self.OS_settings.projection_settings["gcspacing"],
            scspacing=self.OS_settings.projection_settings["scspacing"],
        )
        return (
            CirclePlotData(gc, self.OS_settings.GC_settings),
            CirclePlotData(sc, self.OS_settings.SC_settings),
        )

    def set_drag_rotate_mode(self):
        if not self.projection_plot.drag_rotate_mode:
            self.statusBar().showMessage(
                "Drag rotation mode enabled (Ctrl+R to disable)."
            )
            self.projection_plot.drag_rotate_mode = True
            self.actionRotate_on_Drag.setChecked(True)
        else:
            self.statusBar().showMessage("Drag rotation mode disabled.")
            self.projection_plot.drag_rotate_mode = False
            self.actionRotate_on_Drag.setChecked(False)

    def new_project(self):
        self.remove_all()
        self.clear_plot()
        self.current_project = None
        self.packed_project = False

    def open_project_dialog(self):
        fname, extension = QtWidgets.QFileDialog.getOpenFileName(
            self,
            _translate("main", "Open project"),
            filter="Openstereo Project Files (*.openstereo);;All Files (*.*)",
        )  # noqa: E501
        if not fname:
            return
        self.new_project()
        self.open_project(fname)
        self.update_current_project(fname)
        self.statusBar().showMessage(
            _translate("main", "Loaded project from {}").format(fname)
        )
        self.set_title()

    def update_current_project(self, fname):
        self.current_project = fname

        projects = os_qsettings.value("recentProjectList", [])

        try:
            projects.remove(fname)
        except ValueError:
            pass

        projects.insert(0, fname)
        del projects[self.max_recent_projects :]

        os_qsettings.setValue("recentProjectList", projects)
        self.update_recent_projects()

    # https://github.com/Werkov/PyQt4/blob/master/examples/mainwindows/recentfiles.py
    def update_recent_projects(self):
        projects = os_qsettings.value("recentProjectList", [])

        num_recent_projects = min(len(projects), self.max_recent_projects)
        for i in range(num_recent_projects):
            text = path.splitext(path.basename(projects[i]))[0]
            self.recent_projects[i].setText(text)
            self.recent_projects[i].setData(projects[i])
            self.recent_projects[i].setVisible(True)

        for j in range(num_recent_projects, self.max_recent_projects):
            self.recent_projects[j].setVisible(False)

        self.recent_projects_separator.setVisible(num_recent_projects > 0)

    def open_recent_project(self):
        action = self.sender()
        if action:
            fname = action.data()
            self.new_project()
            self.open_project(fname)
            self.update_current_project(fname)
            self.statusBar().showMessage(
                _translate("main", "Loaded project from {}").format(fname)
            )
            self.set_title()

    def save_project_dialog(self):
        if self.current_project is None:
            fname, extension = QtWidgets.QFileDialog.getSaveFileName(
                self,
                _translate("main", "Save project"),
                filter="Openstereo Project Files (*.openstereo);;All Files (*.*)",
            )  # noqa: E501
            if not fname:
                return
            self.update_current_project(fname)
        self.save_project(self.current_project)
        self.statusBar().showMessage(
            _translate("main", "Saved project to {}").format(
                self.current_project
            )
        )
        self.set_title()

    def save_project_as_dialog(self, pack=False):
        fname, extension = QtWidgets.QFileDialog.getSaveFileName(
            self,
            _translate("main", "Save project"),
            filter="Openstereo Project Files (*.openstereo);;All Files (*.*)",
        )  # noqa: E501
        if not fname:
            return
        self.old_project = self.current_project
        self.update_current_project(fname)
        if pack:
            self.OS_settings.general_settings["packeddata"] = "yes"
        self.save_project(fname)
        self.statusBar().showMessage(
            _translate("main", "Saved project to {}").format(fname)
        )
        self.set_title()

    def save_project(self, fname):
        ozf = zipfile.ZipFile(fname, mode="w")
        self.OS_settings.general_settings["lastsave"] = str(datetime.now())
        project_data = {
            "global_settings": self.OS_settings.item_settings,
            "version": __version__,
            "id_counter": self.id_counter,
            "items": [],
        }
        project_dir = path.dirname(fname)
        if self.old_project is not None:
            old_project_dir = path.dirname(self.old_project)
        else:
            old_project_dir = None
        pack = (
            True
            if self.OS_settings.general_settings["packeddata"] == "yes"
            else False
        )
        packed_paths = {}
        item_settings_fnames = set()
        for index in range(self.treeWidget.topLevelItemCount()):
            item = self.treeWidget.topLevelItem(index)
            self.save_project_item(
                item,
                project_data,
                ozf,
                pack,
                project_dir,
                old_project_dir,
                packed_paths,
                item_settings_fnames,
            )
        ozf.writestr("project_data.json", json.dumps(project_data, indent=3))
        ozf.close()

    def save_project_item(
        self,
        item,
        data,
        ozf,
        pack,
        project_dir,
        old_project_dir,
        packed_paths,
        item_settings_fnames,
    ):
        if isinstance(item, GroupItem):
            item_data = {
                "name": item.text(0),
                "id": getattr(item, "id", None),
                "checked": bool(item.checkState(0)),
                "items": [],
            }
            data["items"].append(item_data)
            for i in range(item.childCount()):
                subitem = item.child(i)
                self.save_project_item(
                    subitem,
                    item_data,
                    ozf,
                    pack,
                    project_dir,
                    old_project_dir,
                    packed_paths,
                    item_settings_fnames,
                )
        else:
            item_path = getattr(item, "data_path", None)
            if item_path is not None:
                item_fname = path.basename(item_path)
                name, ext = path.splitext(item_fname)
                if pack:
                    # as packed data are stored flat, this bellow is to avoid
                    # name colision.
                    i = 1
                    while (
                        item_fname in packed_paths
                        and item_path != packed_paths[item_fname]
                    ):
                        item_fname = "{}({}){}".format(name, i, ext)
                        i += 1
                    packed_paths[item_fname] = item_path
                    # item_path = item_fname
                    ozf.write(
                        path.normpath(
                            path.join(
                                project_dir
                                if self.old_project is None
                                else old_project_dir,
                                item_path,
                            )
                        ),
                        item_fname,
                    )
            item_settings_name = (
                name if item_path is not None else item.text(0)
            )
            item_settings_fname = item_settings_name + ".os_lyr"
            i = 1
            while item_settings_fname in item_settings_fnames:
                item_settings_fname = "{}({}){}".format(
                    item_settings_name, i, ".os_lyr"
                )
                i += 1
            item_settings_fnames.add(item_settings_fname)

            ozf.writestr(
                item_settings_fname, json.dumps(item.item_settings, indent=2)
            )
            if item_path is not None and not pack:
                item_path = path.relpath(
                    path.normpath(
                        path.join(
                            project_dir
                            if self.old_project is None
                            else old_project_dir,
                            item_path,
                        )
                    ),
                    project_dir,
                )
            if hasattr(item, "auttitude_data"):
                auttitude_kwargs = item.auttitude_data.kwargs
            else:
                auttitude_kwargs = None
            data["items"].append(
                {
                    "name": item.text(0),
                    "path": item_path,
                    "id": getattr(item, "id", None),
                    "layer_settings_file": item_settings_fname,
                    "checked": bool(item.checkState(0)),
                    "checked_plots": item.get_checked_status(),
                    "kwargs": auttitude_kwargs,
                }
            )

    def open_project(self, fname, ask_for_missing=False):
        ozf = zipfile.ZipFile(fname, mode="r")
        project_data = json.load(utf8_reader(ozf.open("project_data.json")))
        project_dir = path.dirname(fname)
        self.OS_settings.item_settings = project_data["global_settings"]
        self.id_counter = project_data.get("id_counter", 0)
        packed = (
            True
            if self.OS_settings.general_settings["packeddata"] == "yes"
            else False
        )
        self.temp_dir = mkdtemp() if packed else None
        found_dirs = {}

        for data in project_data["items"]:
            self.open_project_item(
                data,
                self.treeWidget,
                found_dirs,
                ask_for_missing,
                ozf,
                packed,
                project_dir,
            )
        ozf.close()

    def open_project_item(
        self,
        data,
        parent,
        found_dirs,
        ask_for_missing,
        ozf,
        packed,
        project_dir,
    ):
        item_path = data.get("path", None)
        item_id = data.get("id", None)
        item_subitems = data.get("items", None)
        if item_subitems is not None:  # item is a GroupItem
            item = self.add_group(name=data["name"], parent=parent)
            for subdata in item_subitems:
                self.open_project_item(
                    subdata,
                    item,
                    found_dirs,
                    ask_for_missing,
                    ozf,
                    packed,
                    project_dir,
                )
        else:
            if item_path is not None:  # item is a DataItem
                item_basename = path.basename(item_path)
                item_fname, ext = path.splitext(item_basename)
                item_settings_name = data.get(
                    "layer_settings_file", data["name"] + ".os_lyr"
                )
                item_file = (
                    ozf.extract(item_path, self.temp_dir)
                    if packed
                    else path.normpath(
                        path.join(project_dir, data["path"])
                    )  # TODO: change to item_path?
                )
                if not path.exists(item_file):
                    for original_dir, current_dir in list(found_dirs.items()):
                        possible_path = path.normpath(
                            path.join(
                                current_dir,
                                path.relpath(item_file, original_dir),
                            )
                        )
                        if path.exists(possible_path):
                            item_file = possible_path
                            break
                    else:
                        fname, extension = QtWidgets.QFileDialog.getOpenFileName(  # noqa: E501
                            self,
                            _translate(
                                "main", "Set data source for {}"
                            ).format(data["name"]),
                        )
                        if not fname:
                            return None
                        found_dirs[path.dirname(item_file)] = path.dirname(
                            fname
                        )
                        item_file = fname

            else:
                item_settings_name = data.get(
                    "layer_settings_file", data["name"] + ".os_lyr"
                )
                item_file = None
            item_settings = json.load(
                utf8_reader(ozf.open(item_settings_name))
            )
            data_type = list(item_settings.keys())[0]
            if item_file is not None:
                item_data = get_data(item_file, data["kwargs"])
            else:
                item_data = None
            if data["kwargs"] is not None:
                auttitude_kwargs = data["kwargs"]
            else:
                auttitude_kwargs = {}
            item = self.import_data(
                data_type,
                data["name"],
                data_path=item_path,
                data=item_data,
                item_id=item_id,
                item_parent=parent,
                **auttitude_kwargs
            )
            item.item_settings = item_settings
            item.set_checked(data["checked_plots"])
        item.setCheckState(
            0, QtCore.Qt.Checked if data["checked"] else QtCore.Qt.Unchecked
        )
        return item

    def unpack_data_dialog(self):
        if self.OS_settings.general_settings["packeddata"] == "no":
            self.statusBar().showMessage(
                _translate("main", "Project is not packed")
            )
            return
        # http://stackoverflow.com/a/22363617/1457481
        dirname = QtWidgets.QFileDialog.getExistingDirectory(
            self, _translate("main", "Unpack data to")
        )
        if not dirname:
            return
        packed_paths = {}
        for index in range(self.treeWidget.topLevelItemCount()):
            item = self.treeWidget.topLevelItem(index)
            self.unpack_item(item, packed_paths, dirname)
        self.OS_settings.general_settings["packeddata"] = "no"
        target_project_path = path.join(
            dirname, path.basename(self.current_project)
        )
        self.current_project = target_project_path
        self.save_project(target_project_path)
        self.statusBar().showMessage(
            _translate("main", "Project unpacked to {}").format(dirname)
        )
        populate_properties_dialog(
            self.settings_dialog_ui,
            self.OS_settings,
            file={"name": self.current_project},
            update_data_only=True,
        )

    def unpack_item(self, item, packed_paths, dirname):
        if isinstance(item, GroupItem):
            for i in range(item.childCount()):
                subitem = item.child(i)
                self.unpack_item(subitem, packed_paths, dirname)
        else:
            item_path = getattr(item, "data_path", None)
            if item_path is None:
                return
            item_fname = path.basename(item_path)
            name, ext = path.splitext(item_path)
            i = 1
            while (
                item_fname in packed_paths
                and item_path != packed_paths[item_fname]
            ):
                item_fname = "{}({}){}".format(name, i, ext)
                i += 1
            packed_paths[item_fname] = item_path
            target_path = path.join(dirname, item_fname)
            shutil.copy2(item_path, target_path)
            item.data_path = target_path

    def get_data_items(self):
        return [
            self.treeWidget.topLevelItem(index)
            for index in range(self.treeWidget.topLevelItemCount())
        ]

    def get_data_item_by_id(self, id, parent=None):
        if parent is None:
            for index in range(self.treeWidget.topLevelItemCount()):
                item = self.treeWidget.topLevelItem(index)
                if isinstance(item, GroupItem):
                    subitem = self.get_data_item_by_id(id, item)
                    if subitem is not None:
                        return subitem
                else:
                    if item.id == id:
                        return item
        else:  # parent is a group
            for index in range(parent.childCount()):
                item = parent.child(index)
                if isinstance(item, GroupItem):
                    subitem = self.get_data_item_by_id(id, item)
                    if subitem is not None:
                        return subitem
                else:
                    if item.id == id:
                        return item
        return None  # item not found

    def show_settings_dialog(self):
        if not hasattr(self, "settings_dialog"):
            self.settings_dialog = QtWidgets.QDialog(self)
            self.settings_dialog_ui = os_settings_Ui_Dialog()
            self.settings_dialog_ui.setupUi(self.settings_dialog)
            self.settings_dialog.accepted.connect(
                lambda: parse_properties_dialog(
                    self.settings_dialog_ui,
                    self.OS_settings,
                    post_hook=(self.set_title,),
                )
            )
            self.settings_dialog_ui.apply.clicked.connect(
                lambda: parse_properties_dialog(
                    self.settings_dialog_ui,
                    self.OS_settings,
                    post_hook=(self.set_title,),
                )
            )
            # http://stackoverflow.com/a/20021646/1457481
            self.settings_dialog_ui.apply.clicked.connect(
                lambda: self.plot_data()
                if self.actionPlot_on_Apply.isChecked()
                else None
            )
            self.settings_dialog_ui.ok_button.clicked.connect(
                lambda: self.plot_data()
                if self.actionPlot_on_Accept.isChecked()
                else None
            )
            populate_properties_dialog(
                self.settings_dialog_ui,
                self.OS_settings,
                file={"name": self.current_project},
                actions={"unpack": self.unpack_data_dialog},
            )
        else:
            populate_properties_dialog(
                self.settings_dialog_ui,
                self.OS_settings,
                file={"name": self.current_project},
                update_data_only=True,
            )
        self.settings_dialog.show()

    def show_preferences_dialog(self):
        pass

    def remove_all(self):
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
        for index in range(self.treeWidget.topLevelItemCount() - 1, -1, -1):
            item = self.treeWidget.topLevelItem(index)
            self.treeWidget.takeTopLevelItem(index)
        self.clear_plot()

    def expand_data(self, expand=True):
        for index in range(self.treeWidget.topLevelItemCount() - 1, -1, -1):
            item = self.treeWidget.topLevelItem(index)
            self.expand_item(item, expand)

    def expand_item(self, item, expand):
        if isinstance(item, GroupItem):
            item.setExpanded(expand)  # is this better?
            for i in range(item.childCount() - 1, -1, -1):
                subitem = item.child(i)
                self.expand_item(subitem, expand)
        else:
            item.setExpanded(expand)

    def remove_dataitem(self):
        item = self.get_selected()
        parent = item.parent()
        if parent is None:
            index = self.treeWidget.indexOfTopLevelItem(item)
            removed_item = self.treeWidget.takeTopLevelItem(index)
        else:  # parent is a GroupItem
            index = parent.indexOfChild(item)
            removed_item = parent.takeChild(index)
        return (removed_item, parent, index, item.isExpanded())
        self.statusBar().showMessage(
            _translate("main", "Removed item {}").format(item.text(0))
        )  # FIXME: never reached?

    def up_dataitem(self):
        item, parent, index, expanded = self.remove_dataitem()
        if parent is None:
            self.treeWidget.insertTopLevelItem(max(0, index - 1), item)
        else:
            parent.insertChild(max(0, index - 1), item)
        # item.setExpanded(expanded)

    def down_dataitem(self):
        item, parent, index, expanded = self.remove_dataitem()
        if parent is None:
            n_items = self.treeWidget.topLevelItemCount()
            self.treeWidget.insertTopLevelItem(
                min(n_items - 1, index + 1), item
            )
        else:
            n_items = parent.childCount()
            parent.insertChild(min(n_items - 1, index + 1), item)
        # item.setExpanded(expanded)

    def bottom_dataitem(self):
        item, parent, index, expanded = self.remove_dataitem()
        if parent is None:
            n_items = self.treeWidget.topLevelItemCount()
            self.treeWidget.insertTopLevelItem(n_items, item)
        else:
            n_items = parent.childCount()
            parent.insertChild(n_items - 1, item)

    def top_dataitem(self):
        item, parent, index, expanded = self.remove_dataitem()
        if parent is None:
            self.treeWidget.insertTopLevelItem(0, item)
        else:
            parent.insertChild(0, item)

    def rename_dataitem(self):
        item = self.get_selected()
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            _translate("main", "Rename Item"),
            _translate("main", "Name:"),
            QtWidgets.QLineEdit.Normal,
            item.text(0),
        )
        if ok:
            self.statusBar().showMessage(
                _translate("main", "Renamed item {} to {}").format(
                    item.text(0), name
                )
            )
            item.setText(0, name)

    def properties_dataitem(self):
        item = self.get_selected()
        # http://www.qtcentre.org/threads/16310-Closing-all-of-the-mainWindow-s-child-dialogs
        if not hasattr(item, "dialog"):
            item.dialog = QtWidgets.QDialog(self)
            item.dialog_ui = item.properties_ui()
            item.dialog_ui.setupUi(item.dialog)
            item.dialog.setWindowTitle(item.text(0))
            item.dialog.accepted.connect(
                lambda: parse_properties_dialog(item.dialog_ui, item)
            )
            item.dialog_ui.apply.clicked.connect(
                lambda: parse_properties_dialog(item.dialog_ui, item)
            )

            # http://stackoverflow.com/a/20021646/1457481
            apply_action = apply_action_factory(self, item)

            item.dialog_ui.apply.clicked.connect(lambda: apply_action())

            item.dialog_ui.ok_button.clicked.connect(
                lambda: self.plot_data()
                if self.actionPlot_on_Accept.isChecked()
                else None
            )

            populate_properties_dialog(item.dialog_ui, item)
        else:
            item.dialog.setWindowTitle(item.text(0))
            populate_properties_dialog(
                item.dialog_ui, item, update_data_only=True
            )
        item.dialog.show()

    def item_table(self):
        item = self.get_selected()
        if not hasattr(item, "item_table_dialog"):
            item.item_table_dialog = QtWidgets.QDialog(self)
            item.item_table_ui = item_table_Ui_Dialog()
            item.item_table_ui.setupUi(item.item_table_dialog)
            item.item_table_dialog.setWindowTitle(
                _translate("main", "Item table for {}").format(item.text(0))
            )
            item.item_table_ui.update_data_button.clicked.connect(
                update_data_button_factory(
                    item,
                    [
                        lambda: populate_item_table(item),
                        lambda: self.plot_on_update_if_checked(),
                    ],
                )
            )
            populate_item_table(item)
        item.item_table_dialog.show()

    def group_selected(self):
        items = self.get_selected(multiple_selection=True)
        parent = self.get_nearest_commmon_parent(items)
        group = self.add_group("Group", parent=parent)
        for item in items:
            item_object, parent, index, expanded = self.remove_dataitem()
            group.addChild(item_object)
            # if expanded:  # why not?
        return group

    def copy_props_dataitem(self):
        item = self.get_selected()
        if hasattr(item, "item_settings"):
            self.cb.setText(json.dumps(item.item_settings, indent=2))
            self.statusBar().showMessage(
                _translate(
                    "main", "Copied properties of {} to clipboard"
                ).format(item.text(0))
            )

    def export_props_dataitem(self):
        item = self.get_selected()
        fname, extension = QtWidgets.QFileDialog.getSaveFileName(
            self,
            _translate("main", "Export properties of {}").format(item.text(0)),
            filter="Openstereo Layer Files (*.os_lyr);;All Files (*.*)",
        )
        if not fname:
            return
        with open(fname, "w") as f:
            json.dump(item.item_settings, f, indent=2)
        self.statusBar().showMessage(
            _translate("main", "Exported properties of {} to {}").format(
                item.text(0), fname
            )
        )

    def paste_props_dataitem(self):
        item = self.get_selected()
        if not hasattr(item, "item_settings"):
            return
        try:
            item.item_settings = json.loads(self.cb.text())
            self.statusBar().showMessage(
                _translate(
                    "main", "Pasted properties to {} from clipboard"
                ).format(item.text(0))
            )
        # http://stackoverflow.com/a/24338247/1457481
        except (ValueError, KeyError):
            self.statusBar().showMessage(
                _translate(
                    "main",
                    "Failed paste, clipboard contains incompatible properties for {} ",
                ).format(item.text(0))
            )
            return
        try:
            populate_properties_dialog(
                item.dialog_ui, item, update_data_only=True
            )
        except AttributeError:
            return

    def import_props_dataitem(self):
        item = self.get_selected()
        fname, extension = QtWidgets.QFileDialog.getOpenFileName(
            self,
            _translate("main", "Import properties for {}").format(
                item.text(0)
            ),
            filter="Openstereo Layer Files (*.os_lyr);;All Files (*.*)",
        )
        if not fname:
            return
        try:
            with open(fname, "rb") as f:
                item.item_settings = json.load(utf8_reader(f))
                self.statusBar().showMessage(
                    _translate(
                        "main", "Imported properties to {} from {}"
                    ).format(item.text(0), fname)
                )
        # http://stackoverflow.com/a/24338247/1457481
        except (ValueError, KeyError):
            # maybe show a incompatible data popup
            return
        try:
            populate_properties_dialog(
                item.dialog_ui, item, update_data_only=True
            )
        except AttributeError:
            return

    def set_source_dataitem(self):
        item = self.get_selected()
        fname, extension = QtWidgets.QFileDialog.getOpenFileName(
            self,
            _translate("main", "Set data source for {}").format(item.text(0)),
        )
        if not fname:
            return
        item.data_path = fname
        item.reload_data()
        self.statusBar().showMessage(
            _translate("main", "Changed data source for {}").format(
                item.text(0)
            )
        )

    def reload_data(self):
        item = self.get_selected()
        item.reload_data()
        self.statusBar().showMessage(
            _translate("main", "Reloaded data for {}").format(item.text(0))
        )

    def extractor_factory(self, item_name, source_dataset, item_method):
        def extractor():
            return self.add_extracted_data(
                item_name, source_dataset, *item_method()
            )

        return extractor

    def tree_context_menu(self, position):
        items = self.get_selected(multiple_selection=True)
        if items is None:
            return
        menu = QtWidgets.QMenu()

        rename_action = menu.addAction(_translate("main", "Rename..."))
        if len(items) == 1:
            item = items[0]
            if isinstance(item, DataItem):
                properties_action = menu.addAction(
                    _translate("main", "Properties")
                )
                item_table_action = menu.addAction(
                    _translate("main", "View item table")
                )
                menu.addSeparator()
                copy_props_action = menu.addAction(
                    _translate("main", "Copy layer properties")
                )
                paste_props_action = menu.addAction(
                    _translate("main", "Paste layer properties")
                )
                export_props_action = menu.addAction(
                    _translate("main", "Export layer properties")
                )  # Maybe save and load instead?
                import_props_action = menu.addAction(
                    _translate("main", "Import layer properties")
                )
                menu.addSeparator()
                extract_menu = menu.addMenu(_translate("main", "Extract..."))
                extractable_items = item.extractable_items
                for item_name, item_method in extractable_items:
                    item_action = extract_menu.addAction(item_name)
                    item_action.triggered.connect(
                        self.extractor_factory(
                            item_name, item.text(0), item_method
                        )
                    )
                menu.addSeparator()
                # merge_with_action = menu.addAction("Merge with...")
                # rotate_action = menu.addAction("Rotate...")
                # menu.addSeparator()
                datasource_action = menu.addAction(
                    _translate("main", "Set data source")
                )  # should this trigger reimport? They aren't really safe...
                reload_action = menu.addAction(
                    _translate("main", "Reload data")
                )
                # menu.addAction("Export data")
            menu.addSeparator()
            up_action = menu.addAction(_translate("main", "Move item up"))
            down_action = menu.addAction(_translate("main", "Move item down"))
            top_action = menu.addAction(_translate("main", "Move item to top"))
            bottom_action = menu.addAction(
                _translate("main", "Move item to botton")
            )
        menu.addSeparator()
        group_action = menu.addAction(_translate("main", "Group selected"))
        menu.addSeparator()
        expand_action = menu.addAction(_translate("main", "Expand all"))
        collapse_action = menu.addAction(_translate("main", "Collapse all"))
        menu.addSeparator()
        delete_action = menu.addAction(_translate("main", "Delete item"))

        rename_action.triggered.connect(self.rename_dataitem)
        if len(items) == 1:
            item = items[0]
            if isinstance(item, DataItem):
                properties_action.triggered.connect(self.properties_dataitem)
                item_table_action.triggered.connect(self.item_table)

                copy_props_action.triggered.connect(self.copy_props_dataitem)
                paste_props_action.triggered.connect(self.paste_props_dataitem)
                export_props_action.triggered.connect(
                    self.export_props_dataitem
                )
                import_props_action.triggered.connect(
                    self.import_props_dataitem
                )

                datasource_action.triggered.connect(self.set_source_dataitem)
                reload_action.triggered.connect(self.reload_data)

            up_action.triggered.connect(self.up_dataitem)
            down_action.triggered.connect(self.down_dataitem)
            top_action.triggered.connect(self.top_dataitem)
            bottom_action.triggered.connect(self.bottom_dataitem)

        group_action.triggered.connect(lambda: self.group_selected())

        expand_action.triggered.connect(lambda: self.expand_data(True))
        collapse_action.triggered.connect(lambda: self.expand_data(False))

        delete_action.triggered.connect(self.remove_dataitem)

        menu.exec_(self.treeWidget.viewport().mapToGlobal(position))

    def get_selected(self, multiple_selection=False):
        selected_items = self.treeWidget.selectedItems()
        if not selected_items:
            return
        # item = item[0]
        items = []
        for item in selected_items:
            while not (
                isinstance(item, DataItem) or isinstance(item, GroupItem)
            ):
                item = item.parent()
            if item not in items:
                items.append(item)
        if multiple_selection:
            return items
        else:
            return items[0]

    def get_nearest_commmon_parent(self, items):  # could be a function
        remaining_parents = []
        parent = items[0].parent()
        while parent is not None:
            remaining_parents.append(parent)
            parent = parent.parent()
        for item in items[1:]:
            if not remaining_parents:
                return None
            candidate_parents = []
            parent = item.parent()
            while parent is not None:
                if parent in remaining_parents:
                    candidate_parents.append(parent)
                parent = parent.parent()
            remaining_parents = candidate_parents
        if not remaining_parents:
            return None
        else:
            return remaining_parents[0]

    # def check_save_guard(self):
    #     save_guard_file = path.join(data_dir, "save_guard.txt")
    #     if not path.exists(save_guard_file):
    #         with open(save_guard_file, "w") as f:
    #             f.write(str(datetime.now()))

    # def clear_save_guard(self):
    #     save_guard_file = path.join(data_dir, "save_guard.txt")
    #     if path.exists(save_guard_file):
    #         os.remove(save_guard_file)

    def closeEvent(self, event):
        quit_msg = _translate(
            "main", "Are you sure you want to exit OpenStereo?"
        )
        reply = QtWidgets.QMessageBox.question(
            self,
            _translate("main", "Message"),
            quit_msg,
            QtWidgets.QMessageBox.Yes,
            QtWidgets.QMessageBox.No,
        )

        if reply == QtWidgets.QMessageBox.Yes:
            # self.clear_save_guard()
            event.accept()
        else:
            event.ignore()


def os_main():
    def my_excepthook(type, value, tback):
        # log the exception here
        error_dialog = QtWidgets.QErrorMessage()
        error_dialog.showMessage(
            "".join(traceback.format_exception(type, value, tback))
        )
        error_dialog.exec_()
        # then call the default handler
        sys.__excepthook__(type, value, tback)

    # from https://stackoverflow.com/a/38020962/1457481
    sys.excepthook = my_excepthook

    app = QtWidgets.QApplication(sys.argv)
    # locale = os_qsettings.value("locale", QtCore.QLocale.system().name())
    # qtTranslator = QtCore.QTranslator()
    # if qtTranslator.load("openstereo_" + locale, ":/i18n"):
    #     app.installTranslator(qtTranslator)
    main = Main()
    icon = QtGui.QIcon()
    icon.addPixmap(
        QtGui.QPixmap(":/icons/openstereo.ico"),
        QtGui.QIcon.Normal,
        QtGui.QIcon.Off,
    )
    main.setWindowIcon(icon)
    main.add_plots()
    # argv = ["", "fault.openstereo"]
    if len(argv) > 1:  # make this smarter, allow opening other than projs
        main.open_project(argv[1])
        main.current_project = path.abspath(argv[1])
        main.set_title()

    main.show()
    sys.exit(app.exec_())
