#!/usr/bin/python
# -*- coding: utf-8 -*-
import csv
import json
import shutil
import sys
import zipfile
from datetime import datetime
from itertools import tee
from os import path
from tempfile import mkdtemp

import matplotlib
matplotlib.use('Qt5Agg')  # noqa: E402
import numpy as np
import shapefile
from PyQt5 import QtCore, QtWidgets

import openstereo.auttitude as autti
from openstereo.data_import import get_data, ImportDialog
from openstereo.data_models import (AttitudeData, CircularData, LineData,
                                    PlaneData, SmallCircleData)
from openstereo.os_math import net_grid, bearing, haversine, dcos_lines
from openstereo.os_plot import ClassificationPlot, RosePlot, StereoPlot
from openstereo.plot_data import (CirclePlotData, ClassificationPlotData,
                                  ProjectionPlotData, RosePlotData)
from openstereo.projection_models import EqualAngleProj, EqualAreaProj
from openstereo.tools.mesh_process import MeshDialog
from openstereo.ui.merge_data_ui import Ui_Dialog as merge_data_Ui_Dialog
from openstereo.ui.openstereo_ui import Ui_MainWindow
from openstereo.ui.os_settings_ui import Ui_Dialog as os_settings_Ui_Dialog
from openstereo.ui.rotate_data_ui import Ui_Dialog as rotate_data_Ui_Dialog
from openstereo.ui.ui_interface import (parse_properties_dialog,
                                        populate_properties_dialog)
from openstereo.ui import waiting_effects
from openstereo.tools.ply2atti import extract_colored_faces

extract_colored_faces = waiting_effects(extract_colored_faces)

print(sys.version)

__version__ = "0.9q"


def memory_usage_psutil():
    # return the memory usage in MB
    import psutil
    import os
    process = psutil.Process(os.getpid())
    mem = process.memory_info()[0] / float(2**20)
    return mem


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return list(zip(a, b))


class OSSettings(object):
    def __init__(self):
        self.rotation_settings = {'azim': 0., 'plng': 0., 'rake': 0.}
        self.projection_settings = {
            "gcspacing": 10.0,
            "scspacing": 10.0,
            "cardinalborder": 2.0
        }
        self.GC_settings = {
            "linewidths": 0.25,
            "colors": "#808080",
            "linestyles": "-"
        }
        self.SC_settings = {
            "linewidths": 0.25,
            "colors": "#808080",
            "linestyles": "-"
        }
        self.mLine_settings = {
            "linewidth": 1.00,
            "color": "#00CCCC",
            "linestyle": "-"
        }
        self.mGC_settings = {
            "linewidth": 1.00,
            "color": "#555555",
            "linestyle": ":"
        }
        self.check_settings = {
            "grid": False,
            "rotate": False,
            "cardinal": True,
            "cardinalborder": True,
            "colorbar": True,
            "colorbarpercentage": True,
            "measurelinegc": True
        }
        self.rose_check_settings = {
            "outer": True,
            "autoscale": False,
            "scaletxt": True,
            "rings": True,
            "diagonals": True,
            "360d": True,
            "180d": False,
            "interval": False
        }
        self.rose_settings = {
            "outerperc": 10.,
            "ringsperc": 2.5,
            "diagonalsang": 22.5,
            "diagonalsoff": 0.0,
            "outerwidth": 1.,
            "ringswidth": .5,
            "diagonalswidth": .5,
            "from": 0.,
            "to": 180.,
            "scaleaz": 90.,
            "outerc": "#000000",
            "ringsc": "#555555",
            "diagonalsc": "#555555"
        }
        self.general_settings = {
            'fontsize': 'x-small',
            'projection': 'Equal-Area',
            'hemisphere': 'Lower',
            'colorbar': '',
            'title': '',
            'description': '',
            'author': '',
            'lastsave': '',
            'packeddata': "no"
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
    # data_items = {}
    data_types = {
        data_type.data_type: data_type
        for data_type in (AttitudeData, PlaneData, LineData, SmallCircleData,
                          CircularData)
    }

    def __init__(self):
        super(Main, self).__init__()
        self.setupUi(self)

        self.OS_settings = OSSettings()
        self.settings = {
            'fontsize': 'x-small',
            'title': '',
            'summary': '',
            'description': '',
            'author': '',
            'credits': '',
            'last_saved': ''
        }

        self.projections = {
            'Equal-Area': EqualAreaProj(self.OS_settings),
            'Equal-Angle': EqualAngleProj(self.OS_settings)
        }

        # self.projection_option = QtWidgets.QActionGroup(self, exclusive=True)
        # self.projection_option.addAction(self.actionEqual_Area)
        # self.projection_option.addAction(self.actionEqual_Angle)

        self.actionImport_Plane_Data_DD.triggered.connect(
            lambda: self.import_files(
                        data_type="plane_data", direction=False,
                        dialog_title='Import plane data'))
        self.actionImport_Plane_Data_Dir.triggered.connect(
            lambda: self.import_files(
                        data_type="plane_data", direction=True,
                        dialog_title='Import plane data'))
        self.actionImport_Line_Data_Trend.triggered.connect(
            lambda: self.import_files(
                        data_type="line_data", direction=False,
                        dialog_title='Import line data'))
        self.actionImport_Small_Circle_Data.triggered.connect(
            lambda: self.import_files(
                        data_type="smallcircle_data", direction=False,
                        dialog_title='Import Small Circle data'))
        self.actionImport_Circular_Data_Trend.triggered.connect(
            lambda: self.import_files(
                        data_type="circular_data", direction=False,
                        dialog_title='Import Azimuth data'))

        self.actionNew.triggered.connect(self.new_project)
        self.actionSave.triggered.connect(self.save_project_dialog)
        self.actionSave_as.triggered.connect(self.save_project_as_dialog)
        self.actionOpen.triggered.connect(self.open_project_dialog)
        self.actionSave_as_Packed_Project.triggered.connect(
            lambda: self.save_project_as_dialog(pack=True))
        self.actionImport.triggered.connect(self.import_dialog)

        self.actionSettings.triggered.connect(self.show_settings_dialog)
        self.actionPreferences.triggered.connect(self.show_preferences_dialog)

        self.actionUnpack_Project_to.triggered.connect(self.unpack_data_dialog)

        self.actionMerge_Data.triggered.connect(self.merge_data_dialog)
        self.actionRotate_Data.triggered.connect(self.rotate_data_dialog)

        self.actionConvert_Shapefile_to_Azimuth_data.triggered.connect(
            self.import_shapefile)
        self.actionConvert_Mesh_to_Plane_Data.triggered.connect(
            self.import_mesh)

        self.plotButton.clicked.connect(self.plot_data)
        self.settingsButton.clicked.connect(self.show_settings_dialog)
        self.clearButton.clicked.connect(self.clear_plot)

        self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(
            self.tree_context_menu)
        # http://stackoverflow.com/a/4170541/1457481
        self.treeWidget.setDragDropMode(
            QtWidgets.QAbstractItemView.InternalMove)

        self.save_shortcut = QtWidgets.QShortcut("Ctrl+S", self,
                                                 self.save_project_dialog)
        self.save_as_shortcut = QtWidgets.QShortcut(
            "Ctrl+Shift+S", self, self.save_project_as_dialog)
        self.open_shortcut = QtWidgets.QShortcut("Ctrl+O", self,
                                                 self.open_project_dialog)

        self.rename_shortcut = QtWidgets.QShortcut("F2", self,
                                                   self.rename_dataitem)

        self.copy_shortcut = QtWidgets.QShortcut("Ctrl+C", self,
                                                 self.copy_props_dataitem)
        self.paste_shortcut = QtWidgets.QShortcut("Ctrl+V", self,
                                                  self.paste_props_dataitem)

        self.plot_shortcut = QtWidgets.QShortcut("Ctrl+P", self,
                                                 self.plot_data)
        self.clear_shortcut = QtWidgets.QShortcut("Ctrl+L", self,
                                                  self.clear_plot)
        self.settings_shortcut = QtWidgets.QShortcut("Ctrl+,", self,
                                                     self.show_settings_dialog)

        self.cb = QtWidgets.QApplication.clipboard()

        self.current_project = None
        self.packed_project = False
        self.temp_dir = None
        self.statusBar().showMessage('Ready')
        self.set_title()

    def projection(self):
        return self.projections[self.OS_settings.general_settings[
            'projection']]

    def clear_plot(self):
        self.projection_plot.plot_projection_net()
        self.projection_plot.draw_plot()
        self.rose_plot.draw_plot()
        self.classification_plot.draw_plot()
        self.statusBar().showMessage('Ready')

    def add_plots(self):
        self.projection_plot = StereoPlot(self.OS_settings, self.projection,
                                          self.projectionTab)
        self.rose_plot = RosePlot(self.OS_settings, self.roseTab)
        self.classification_plot = ClassificationPlot(self.OS_settings,
                                                      self.classificationTab)
        self.clear_plot()

    def set_title(self):
        title = "OpenStereo - "
        if self.OS_settings.general_settings['title']:
            title += self.OS_settings.general_settings['title']
        elif self.current_project is not None:
            title += self.current_project
        else:
            title += "Open-source, Multiplatform Stereonet Analysis"
        self.setWindowTitle(title)

    def import_data(self, data_type, name, **kwargs):
        return self.data_types[data_type](
            name=name, parent=self.treeWidget, **kwargs)

    def import_files(self, data_type, direction, dialog_title):
        fnames, extension =\
            QtWidgets.QFileDialog.getOpenFileNames(self, dialog_title)
        if not fnames:
            return
        for fname in fnames:
            dialog = ImportDialog(
                self, fname=fname, data_type=data_type, direction=direction)
            fname = dialog.fname.text()
            data_type, letter = dialog.data_type
            data_name = "({}){}".format(letter, path.basename(fname))
            reader = dialog.get_data()
            self.import_data(
                data_type,
                data_name,
                data_path=fname,
                data=reader,
                **dialog.import_kwargs)

    def import_dialog(self,
                      item=None,
                      try_default=False,
                      data_type=None,
                      direction=False,
                      fname=None,
                      dialog_title='Import data'):
        if fname is None:
            fname, extension =\
                QtWidgets.QFileDialog.getOpenFileName(self, dialog_title)
        if try_default and not fname:
            return
        dialog = ImportDialog(
            self, fname=fname, data_type=data_type, direction=direction)
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
                **dialog.import_kwargs)

    def import_shapefile(self):
        fname, extension =\
            QtWidgets.QFileDialog.getOpenFileName(
                self, 'Select Shapefile to convert',
                filter="ESRI Shapefile (*.shp);;All Files (*.*)")
        if not fname:
            return
        name, ext = path.splitext(fname)

        fname_out, extension =\
            QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save azimuth data as',
                name + ".txt",
                filter="Text Files (*.txt);;All Files (*.*)")
        if not fname_out:
            return
        with open(fname_out, "w") as f:
            sf = shapefile.Reader(fname)
            f.write("azimuth;length\n")
            for shape in sf.shapes():
                for A, B in pairwise(shape.points):
                    f.write("{};{}\n".format(
                        bearing(A[0], B[0], A[1], B[1]),
                        haversine(A[0], B[0], A[1], B[1])))
        self.import_dialog(
            try_default=True,
            fname=fname_out,
            data_type="circular_data",
            direction=False,
            dialog_title='Import Azimuth data')

    def import_mesh(self):
        fname, extension =\
            QtWidgets.QFileDialog.getOpenFileName(
                self, 'Select Mesh to convert',
                filter="Stanford Polygon (*.ply);;All Files (*.*)")
        if not fname:
            return
        name, ext = path.splitext(fname)
        dialog = MeshDialog(self)
        if dialog.exec_():
            self.statusBar().showMessage('Processing Mesh %s...' % fname)
            colors = dialog.colors
            if not colors:
                return
            with open(fname, "rb") as f:
                output = extract_colored_faces(f, colors)
            self.statusBar().showMessage('Ready')
            if dialog.check_separate.isChecked():
                dirname =\
                    QtWidgets.QFileDialog.getExistingDirectory(
                        self, 'Save data files to')
                if not dirname:
                    return
                color_filenames = []
                for color in list(output.keys()):
                    color_filename = "{0}_{1}.txt".format(name, color[:-1])
                    color_filenames.append((color, color_filename))
                    with open(color_filename, "wb") as f:
                        writer = csv.writer(f)
                        writer.writerow(
                            ["dip_direction", "dip", "X", "Y", "Z", "trace"])
                        for line in output[color]:
                            writer.writerow(line)
                for color, color_filename in color_filenames:
                    item = self.import_dialog(
                        try_default=True,
                        fname=color_filename,
                        data_type="plane_data",
                        direction=False,
                        dialog_title='Import plane data')
                    item.point_settings["c"] = '#%02x%02x%02x' % color[:-1]
                return
            else:
                fname_out, extension =\
                    QtWidgets.QFileDialog.getSaveFileName(
                        self, 'Save plane data as',
                        name + ".txt",
                        filter="Text Files (*.txt);;All Files (*.*)")
                if not fname_out:
                    return
                with open(fname_out, "wb") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "dip_direction", "dip", "X", "Y", "Z", "trace", "R",
                        "G", "B"
                    ])
                    for color in list(output.keys()):
                        for line in output[color]:
                            writer.writerow(line + color[:-1])
                item = self.import_dialog(
                    try_default=True,
                    fname=fname_out,
                    data_type="plane_data",
                    direction=False,
                    dialog_title='Import plane data')

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
            self.statusBar().showMessage('No items to merge')
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
            merge_dialog_ui.savename.setText(A_name + "+" + path.splitext(
                path.basename(B.data_path))[0] + ".txt")

        # http://stackoverflow.com/a/22798753/1457481
        if current_item is not None:
            index = merge_dialog_ui.A.findText(current_item)
            if index >= 0:
                merge_dialog_ui.A.setCurrentIndex(index)
        A_changed()

        def on_browse():
            fname, extension =\
                QtWidgets.QFileDialog.getSaveFileName(self, 'Save merged data')
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
                    **A.kwargs)
                merged_item.item_settings = A.item_settings
            self.statusBar().showMessage('Merged items %s and %s as %s' %
                                         (A.text(0), B.text(0), merged_name))

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
            self.statusBar().showMessage('No items to rotate')
            return
        for item_name in list(data_items.keys()):
            rotate_dialog_ui.A.addItem(item_name)

        def data_changed(event=None):
            A = data_items[rotate_dialog_ui.A.currentText()]
            A_name, A_ext = path.splitext(A.data_path)
            rotate_dialog_ui.savename.setText(
                A_name + "-rot_{}_{}_{}.txt".format(
                    rotate_dialog_ui.trend.value(),
                    rotate_dialog_ui.plunge.value(),
                    rotate_dialog_ui.angle.value(), ))

        # http://stackoverflow.com/a/22798753/1457481
        def on_browse():
            fname, extension =\
                QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save rotated data')
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
                np.radians((rotate_dialog_ui.trend.value(),
                            rotate_dialog_ui.plunge.value())))
            rotated_data = autti.rotate(A.auttitude_data, u,
                                        rotate_dialog_ui.angle.value())
            rotated_name = A.text(0) +\
                "-rot_{}_{}_{}".format(rotate_dialog_ui.trend.value(),
                                       rotate_dialog_ui.plunge.value(),
                                       rotate_dialog_ui.angle.value(),)
            rotated_fname = rotate_dialog_ui.savename.text()
            np.savetxt(rotated_fname, rotated_data.data_sphere)
            if rotate_dialog_ui.keep.isChecked():
                rotated_item = self.data_types[A.data_type](
                    name=rotated_name,
                    data_path=rotated_fname,
                    data=rotated_data,
                    parent=self.treeWidget,
                    **A.kwargs)
                rotated_item.item_settings = A.item_settings
            self.statusBar().showMessage('Rotated item %s to %s' %
                                         (A.text(0), rotated_name))

    # @waiting_effects
    def plot_data(self):
        self.statusBar().showMessage('Plotting data...')
        for index in range(self.treeWidget.topLevelItemCount() - 1, -1, -1):
            item = self.treeWidget.topLevelItem(index)
            if item.checkState(0):
                for plot_item in item.checked_plots:
                    if isinstance(plot_item, ProjectionPlotData) and\
                            self.tabWidget.currentIndex() == 0:
                        self.projection_plot.plot_data(plot_item)
                    if isinstance(plot_item, RosePlotData) and\
                            self.tabWidget.currentIndex() == 1:
                        self.rose_plot.plot_data(plot_item)
                    if isinstance(plot_item, ClassificationPlotData) and\
                            self.tabWidget.currentIndex() == 2:
                        self.classification_plot.plot_data(plot_item)
        if self.OS_settings.check_settings['grid'] and\
                self.tabWidget.currentIndex() == 0:
            gc, sc = self.plot_grid()
            self.projection_plot.plot_data(gc)
            self.projection_plot.plot_data(sc)
        if self.tabWidget.currentIndex() == 0:
            self.projection_plot.draw_plot()
        elif self.tabWidget.currentIndex() == 1:
            self.rose_plot.draw_plot()
        elif self.tabWidget.currentIndex() == 2:
            self.classification_plot.draw_plot()
        self.statusBar().showMessage('Ready')

    def plot_grid(self):
        gc, sc = net_grid(
            gcspacing=self.OS_settings.projection_settings['gcspacing'],
            scspacing=self.OS_settings.projection_settings['scspacing'])
        return (CirclePlotData(gc, self.OS_settings.GC_settings),
                CirclePlotData(sc, self.OS_settings.SC_settings))

    def new_project(self):
        self.remove_all()
        self.clear_plot()
        self.current_project = None
        self.packed_project = False

    def open_project_dialog(self):
        fname, extension =\
            QtWidgets.QFileDialog.getOpenFileName(
                self, 'Open project',
                filter="Openstereo Project Files (*.openstereo);;All Files (*.*)")  # noqa: E501
        if not fname:
            return
        self.new_project()
        self.open_project(fname)
        self.current_project = fname
        self.statusBar().showMessage('Loaded project from %s' % fname)
        self.set_title()

    def save_project_dialog(self):
        if self.current_project is None:
            fname, extension =\
                QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save project',
                    filter="Openstereo Project Files (*.openstereo);;All Files (*.*)")  # noqa: E501
            if not fname:
                return
            self.current_project = fname
        self.save_project(self.current_project)
        self.statusBar().showMessage(
            'Saved project to %s' % self.current_project)
        self.set_title()

    def save_project_as_dialog(self, pack=False):
        fname, extension =\
            QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save project',
                filter="Openstereo Project Files (*.openstereo);;All Files (*.*)")  # noqa: E501
        if not fname:
            return
        self.current_project = fname
        if pack:
            self.OS_settings.general_settings['packeddata'] = 'yes'
        self.save_project(fname)
        self.statusBar().showMessage('Saved project to %s' % fname)
        self.set_title()

    def save_project(self, fname):
        ozf = zipfile.ZipFile(fname, mode='w')
        self.OS_settings.general_settings["lastsave"] = str(datetime.now())
        project_data = {
            "global_settings": self.OS_settings.item_settings,
            "version": __version__,
            "items": []
        }
        project_dir = path.dirname(fname)
        pack = True if self.OS_settings.general_settings[
            'packeddata'] == 'yes' else False
        packed_paths = {}
        for index in range(self.treeWidget.topLevelItemCount() - 1, -1, -1):
            item = self.treeWidget.topLevelItem(index)
            item_path = getattr(item, 'data_path', None)
            if item_path is not None:
                item_fname = path.basename(item_path)
                name, ext = path.splitext(item_fname)
                if pack:
                    # as packed data are stored flat, this bellow is to avoid
                    # name colision.
                    i = 1
                    while item_fname in packed_paths and \
                            item_path != packed_paths[item_fname]:
                        item_fname = "{}({}){}".fomart(name, i, ext)
                        i += 1
                    packed_paths[item_fname] = item_path
                    item_path = item_fname
                    ozf.write(item_path, item_fname)
            item_settings_name = name + ".os_lyr" if item_path is not None \
                else item.text(0) + ".os_lyr"
            ozf.writestr(item_settings_name,
                         json.dumps(item.item_settings, indent=2))
            if item_path is not None:
                item_path = path.relpath(item_path, project_dir)
            project_data['items'].append({
                'name':
                item.text(0),
                'path':
                item_path,
                'checked':
                bool(item.checkState(0)),
                'checked_plots':
                item.get_checked_status(),
                'kwargs':
                item.auttitude_data.kwargs
            })
        ozf.writestr("project_data.json", json.dumps(project_data, indent=3))
        ozf.close()

    def open_project(self, fname, ask_for_missing=False):
        ozf = zipfile.ZipFile(fname, mode='r')
        project_data = json.load(ozf.open("project_data.json"))
        project_dir = path.dirname(fname)
        self.OS_settings.item_settings = project_data['global_settings']
        packed = True if self.OS_settings.general_settings[
            'packeddata'] == 'yes' else False
        self.temp_dir = mkdtemp() if packed else None
        found_dirs = {}

        for data in reversed(project_data['items']):
            item_path = data['path']
            if item_path is not None:
                item_basename = path.basename(item_path)
                item_fname, ext = path.splitext(item_basename)
                item_settings_name = item_fname + '.os_lyr'
                item_file = ozf.extract(item_path, self.temp_dir) \
                    if packed else \
                    path.normpath(path.join(project_dir, data['path']))
                if not path.exists(item_file):
                    for original_dir, current_dir in list(found_dirs.items()):
                        possible_path = path.normpath(
                            path.join(current_dir,
                                      path.relpath(item_file, original_dir)))
                        if path.exists(possible_path):
                            item_file = possible_path
                            break
                    else:
                        fname, extension = QtWidgets.QFileDialog.getOpenFileName(  # noqa: E501
                            self,
                            'Set data source for %s' % data['name'])
                        if not fname:
                            continue
                        found_dirs[path.dirname(item_file)] =\
                            path.dirname(fname)
                        item_file = fname

            else:
                item_settings_name = data['name'] + ".os_lyr"
                item_file = None
            item_settings = json.load(ozf.open(item_settings_name))
            data_type = list(item_settings.keys())[0]
            item_data = get_data(item_file, data['kwargs'])\
                if item_file is not None else None
            item = self.import_data(
                data_type,
                data['name'],
                data_path=item_path,
                data=item_data,
                **data['kwargs'])
            item.item_settings = item_settings
            item.setCheckState(0, QtCore.Qt.Checked
                               if data['checked'] else QtCore.Qt.Unchecked)
            item.set_checked(data['checked_plots'])
        ozf.close()

    def unpack_data_dialog(self):
        if self.OS_settings.general_settings['packeddata'] == 'no':
            self.statusBar().showMessage('Project is not packed')
            return
        # http://stackoverflow.com/a/22363617/1457481
        dirname =\
            QtWidgets.QFileDialog.getExistingDirectory(self, 'Unpack data to')
        if not dirname:
            return
        packed_paths = {}
        for index in range(self.treeWidget.topLevelItemCount() - 1, -1, -1):
            item = self.treeWidget.topLevelItem(index)
            # item_fname = path.basename(item.data_path)
            item_path = getattr(item, 'data_path', None)
            if item_path is None:
                continue
            item_fname = path.basename(item_path)
            name, ext = path.splitext(item_path)
            i = 1
            while item_fname in packed_paths and \
                    item_path != packed_paths[item_fname]:
                item_fname = "{}({}){}".fomart(name, i, ext)
                i += 1
            packed_paths[item_fname] = item_path
            target_path = path.join(dirname, item_fname)
            shutil.copy2(item_path, target_path)
            item.data_path = target_path
        self.OS_settings.general_settings['packeddata'] = 'no'
        target_project_path = path.join(dirname,
                                        path.basename(self.current_project))
        self.current_project = target_project_path
        self.save_project(target_project_path)
        self.statusBar().showMessage('Project unpacked to %s' % dirname)
        populate_properties_dialog(
            self.settings_dialog_ui,
            self.OS_settings,
            file={'name': self.current_project},
            update_data_only=True)

    def get_data_items(self):
        return [
            self.treeWidget.topLevelItem(index)
            for index in range(self.treeWidget.topLevelItemCount())
        ]

    def show_settings_dialog(self):
        if not hasattr(self, "settings_dialog"):
            self.settings_dialog = QtWidgets.QDialog(self)
            self.settings_dialog_ui = os_settings_Ui_Dialog()
            self.settings_dialog_ui.setupUi(self.settings_dialog)
            self.settings_dialog.accepted.connect(
                lambda: parse_properties_dialog(
                    self.settings_dialog_ui,
                    self.OS_settings, post_hook=(self.set_title,)))
            self.settings_dialog_ui.apply.clicked.connect(
                lambda: parse_properties_dialog(
                    self.settings_dialog_ui,
                    self.OS_settings, post_hook=(self.set_title,)))
            # http://stackoverflow.com/a/20021646/1457481
            self.settings_dialog_ui.apply.clicked.connect(
                    lambda: self.plot_data()
                    if self.actionPlot_on_Apply.isChecked()
                    else None)
            self.settings_dialog_ui.ok_button.clicked.connect(
                    lambda: self.plot_data()
                    if self.actionPlot_on_Accept.isChecked()
                    else None)
            populate_properties_dialog(
                self.settings_dialog_ui,
                self.OS_settings,
                file={'name': self.current_project},
                actions={'unpack': self.unpack_data_dialog})
        else:
            populate_properties_dialog(
                self.settings_dialog_ui,
                self.OS_settings,
                file={'name': self.current_project},
                update_data_only=True)
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
            item.setExpanded(expand)

    def remove_dataitem(self):
        item = self.get_selected()
        index = self.treeWidget.indexOfTopLevelItem(item)
        return self.treeWidget.takeTopLevelItem(
            index), index, item.isExpanded()
        self.statusBar().showMessage('Removed item %s' % item.text(0))

    def up_dataitem(self):
        item, index, expanded = self.remove_dataitem()
        self.treeWidget.insertTopLevelItem(max(0, index - 1), item)
        # item.setExpanded(expanded)

    def down_dataitem(self):
        n_items = self.treeWidget.topLevelItemCount()
        item, index, expanded = self.remove_dataitem()
        self.treeWidget.insertTopLevelItem(min(n_items - 1, index + 1), item)
        # item.setExpanded(expanded)

    def bottom_dataitem(self):
        n_items = self.treeWidget.topLevelItemCount()
        item, index, expanded = self.remove_dataitem()
        self.treeWidget.insertTopLevelItem(n_items - 1, item)

    def top_dataitem(self):
        item, index, expanded = self.remove_dataitem()
        self.treeWidget.insertTopLevelItem(0, item)

    def rename_dataitem(self):
        item = self.get_selected()
        name, ok = QtWidgets.QInputDialog.getText(self, "Rename Item", "Name:",
                                                  QtWidgets.QLineEdit.Normal,
                                                  item.text(0))
        if ok:
            self.statusBar().showMessage('Renamed item %s to %s' %
                                         (item.text(0), name))
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
                lambda: parse_properties_dialog(item.dialog_ui, item))
            item.dialog_ui.apply.clicked.connect(
                lambda: parse_properties_dialog(item.dialog_ui, item))
            # http://stackoverflow.com/a/20021646/1457481
            item.dialog_ui.apply.clicked.connect(
                lambda: self.plot_data()
                if self.actionPlot_on_Apply.isChecked() else None)
            item.dialog_ui.ok_button.clicked.connect(
                lambda: self.plot_data()
                if self.actionPlot_on_Accept.isChecked() else None)
            populate_properties_dialog(item.dialog_ui, item)
        else:
            item.dialog.setWindowTitle(item.text(0))
            populate_properties_dialog(
                item.dialog_ui, item, update_data_only=True)
        item.dialog.show()

    def copy_props_dataitem(self):
        item = self.get_selected()
        self.cb.setText(json.dumps(item.item_settings, indent=2))
        self.statusBar().showMessage(
            'Copied properties of %s to clipboard' % item.text(0))

    def export_props_dataitem(self):
        item = self.get_selected()
        fname, extension =\
            QtWidgets.QFileDialog.getSaveFileName(
                self,
                'Export properties of %s' % item.text(0),
                filter="Openstereo Layer Files (*.os_lyr);;All Files (*.*)")
        if not fname:
            return
        with open(fname, "wb") as f:
            json.dump(item.item_settings, f, indent=2)
        self.statusBar().showMessage('Exported properties of %s to %s' %
                                     (item.text(0), fname))

    def paste_props_dataitem(self):
        item = self.get_selected()
        try:
            item.item_settings = json.loads(self.cb.text())
            self.statusBar().showMessage(
                'Pasted properties to %s from clipboard' % item.text(0))
        # http://stackoverflow.com/a/24338247/1457481
        except (ValueError, KeyError):
            self.statusBar().showMessage(
                'Failed paste, clipboard contains incompatible properties for %s '  # noqa: E501
                % item.text(0))
            return
        try:
            populate_properties_dialog(
                item.dialog_ui, item, update_data_only=True)
        except AttributeError:
            return

    def import_props_dataitem(self):
        item = self.get_selected()
        fname, extension =\
            QtWidgets.QFileDialog.getOpenFileName(
                self,
                'Import properties for %s' % item.text(0),
                filter="Openstereo Layer Files (*.os_lyr);;All Files (*.*)")
        if not fname:
            return
        try:
            with open(fname, "rb") as f:
                item.item_settings = json.load(f)
                self.statusBar().showMessage(
                    'Imported properties to %s from %s' % (item.text(0),
                                                           fname))
        # http://stackoverflow.com/a/24338247/1457481
        except (ValueError, KeyError):
            # maybe show a incompatible data popup
            return
        try:
            populate_properties_dialog(
                item.dialog_ui, item, update_data_only=True)
        except AttributeError:
            return

    def set_source_dataitem(self):
        item = self.get_selected()
        fname, extension = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Set data source for %s' % item.text(0))
        if not fname:
            return
        item.data_path = fname
        item.reload_data()
        self.statusBar().showMessage(
            'Changed data source for %s' % item.text(0))

    def reload_data(self):
        item = self.get_selected()
        item.reload_data()
        self.statusBar().showMessage('Reloaded data for %s' % item.text(0))

    def tree_context_menu(self, position):
        item = self.get_selected()
        menu = QtWidgets.QMenu()

        rename_action = menu.addAction("Rename...")
        properties_action = menu.addAction("Properties")
        # menu.addAction("View item table")
        menu.addSeparator()
        copy_props_action = menu.addAction("Copy layer properties")
        paste_props_action = menu.addAction("Paste layer properties")
        export_props_action = menu.addAction(
            "Export layer properties")  # Maybe save and load instead?
        import_props_action = menu.addAction("Import layer properties")
        menu.addSeparator()
        # merge_with_action = menu.addAction("Merge with...")
        # rotate_action = menu.addAction("Rotate...")
        # menu.addSeparator()
        datasource_action = menu.addAction(
            "Set data source"
        )  # should this trigger reimport? They aren't really safe anymore...
        reload_action = menu.addAction("Reload data")
        # menu.addAction("Export data")
        menu.addSeparator()
        up_action = menu.addAction("Move item up")
        down_action = menu.addAction("Move item down")
        top_action = menu.addAction("Move item to top")
        bottom_action = menu.addAction("Move item to botton")
        menu.addSeparator()
        expand_action = menu.addAction("Expand all")
        collapse_action = menu.addAction("Collapse all")
        menu.addSeparator()
        delete_action = menu.addAction("Delete item")

        rename_action.triggered.connect(self.rename_dataitem)
        properties_action.triggered.connect(self.properties_dataitem)

        copy_props_action.triggered.connect(self.copy_props_dataitem)
        paste_props_action.triggered.connect(self.paste_props_dataitem)
        export_props_action.triggered.connect(self.export_props_dataitem)
        import_props_action.triggered.connect(self.import_props_dataitem)

        datasource_action.triggered.connect(self.set_source_dataitem)
        reload_action.triggered.connect(self.reload_data)

        up_action.triggered.connect(self.up_dataitem)
        down_action.triggered.connect(self.down_dataitem)
        top_action.triggered.connect(self.top_dataitem)
        bottom_action.triggered.connect(self.bottom_dataitem)

        expand_action.triggered.connect(lambda: self.expand_data(True))
        collapse_action.triggered.connect(lambda: self.expand_data(False))

        delete_action.triggered.connect(self.remove_dataitem)

        menu.exec_(self.treeWidget.viewport().mapToGlobal(position))

    def get_selected(self):
        item = self.treeWidget.selectedItems()
        if not item:
            return
        item = item[0]
        while item.parent():
            item = item.parent()
        return item
