#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from os import path
import math
from math import pi, sin, cos, acos, atan2, degrees, radians, sqrt
from itertools import chain, tee
import re
import json
import zipfile
import shutil
from tempfile import mkdtemp
from datetime import datetime
import csv

print(sys.version)

try:
    from io import StringIO
except ImportError:
    from io import StringIO

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.pyplot import colorbar
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT)

from matplotlib.patches import Polygon, Wedge, Circle, Arc, FancyArrowPatch
from matplotlib.collections import PatchCollection, PolyCollection, LineCollection
from matplotlib.mlab import griddata
import matplotlib.patheffects as PathEffects
from matplotlib.font_manager import FontProperties
from mpl_toolkits.axes_grid.axislines import Subplot

from matplotlib.lines import Line2D

import numpy as np

import shapefile

import xlrd

from openstereo.ply2atti import extract_colored_faces

from openstereo.auttitude import load, DirectionalData
import openstereo.auttitude as autti

from openstereo.ui.openstereo_ui import Ui_MainWindow

from openstereo.ui.os_settings_ui import Ui_Dialog as os_settings_Ui_Dialog
from openstereo.ui.import_dialog_ui import Ui_Dialog as import_dialog_Ui_Dialog

from openstereo.ui.plane_properties_ui import Ui_Dialog as plane_Ui_Dialog
from openstereo.ui.line_properties_ui import Ui_Dialog as line_Ui_Dialog
from openstereo.ui.smallcircle_properties_ui import Ui_Dialog as smallcircle_Ui_Dialog
from openstereo.ui.circular_properties_ui import Ui_Dialog as circular_Ui_Dialog

from openstereo.ui.merge_data_ui import Ui_Dialog as merge_data_Ui_Dialog
from openstereo.ui.rotate_data_ui import Ui_Dialog as rotate_data_Ui_Dialog
from openstereo.ui.import_ply_ui import Ui_Dialog as import_ply_Ui_Dialog

__version__ = "0.9q"

sqrt2 = sqrt(2.0)
sqrt3_2 = sqrt(3.0) / 2.
sqrt3 = sqrt(3.0)
earth_radius = 6371000


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


#http://stackoverflow.com/a/20295812/1457481
def waiting_effects(function):
    def new_function(*args, **kwargs):
        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.WaitCursor))
        try:
            return function(*args, **kwargs)
        except Exception as e:
            raise e
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    return new_function


extract_colored_faces = waiting_effects(extract_colored_faces)


#http://www.movable-type.co.uk/scripts/latlong.html
def haversine(long1, long2, lat1, lat2, R=earth_radius):
    phi1, phi2 = radians(lat1), radians(lat2)
    lambda1, lambda2 = radians(long1), radians(long2)
    delta_phi = phi1 - phi2
    delta_lambda = lambda1 - lambda2
    a = sin(
        delta_phi / 2.)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2.)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


#http://www.movable-type.co.uk/scripts/latlong.html
def bearing(long1, long2, lat1, lat2):
    phi1, phi2 = radians(lat1), radians(lat2)
    lambda1, lambda2 = radians(long1), radians(long2)
    y = sin(lambda2 - lambda1) * cos(phi2)
    x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(lambda2 - lambda1)
    return degrees(atan2(y, x)) % 360.


#http://stackoverflow.com/a/22659261/1457481
def in_interval(from_, to_, theta):
    from_, to_ = from_ % 360., to_ % 360.
    return (from_ > to_ and (theta > from_ or theta < to_)) or\
       (from_ < to_ and (theta <= to_ and theta >= from_))


def dcos(atti):
    dd, d = np.transpose(atti)
    return np.array((sin(d) * sin(dd), sin(d) * cos(dd), cos(d)))


def dcos_lines(atti):
    tr, pl = np.transpose(atti)
    return np.array((cos(pl) * sin(tr), cos(pl) * cos(tr), -sin(pl)))


def sphere(x, y, z):
    """Calculates the attitude of poles direction cossines."""
    sign_z = np.copysign(1, z)
    return np.array((np.degrees(np.arctan2(sign_z * x, sign_z * y)) % 360,
                     np.degrees(np.arccos(np.abs(z))))).T


def normal_versor(a, b):
    c = np.cross(a, b)
    return c / np.linalg.norm(c)


def direction_versor(a):
    if a[2] == 1.0:
        return np.array((0.0, 1.0, 0.0, ))
    else:
        d = np.cross((0.0, 0.0, 1.0), a)
        return d / np.linalg.norm(d)


def angle(A, B):
    a, b = A / np.linalg.norm(A), B / np.linalg.norm(B)
    return math.atan2(np.linalg.norm(np.cross(a, b)), np.inner(a, b))


def normalized_cross(a, b):
    c = np.cross(a, b)
    return c / np.linalg.norm(c)[:, None]


def dip_versor(a):
    d = np.cross(direction_versor(a), a)
    return d / np.linalg.norm(d)


def great_circle_arc(a, b, r=radians(1.)):
    dot = np.dot(a, b)
    theta = acos(dot)
    b_ = b - dot * a
    b_ = b_ / np.linalg.norm(b_)
    c = np.cross(a, b_)
    theta_range = np.arange(0, theta, radians(r))
    sin_range = np.sin(theta_range)
    cos_range = np.cos(theta_range)
    return (a * cos_range[:, None] + b_ * sin_range[:, None]).T


def great_circle_simple(dcos, range=2 * pi, r=radians(1.)):
    theta_range = np.arange(0, range, r)
    sin_range = np.sin(theta_range)
    cos_range = np.cos(theta_range)
    dir_v = direction_versor(dcos)
    dip_v = dip_versor(dcos)
    return (np.outer(dir_v, cos_range) + np.outer(dip_v, sin_range)).T


def great_circle(dcos, n=360):
    theta_range = np.linspace(0, 2 * pi, n)
    sin_range = np.sin(theta_range)
    cos_range = np.cos(theta_range)
    dir_v = direction_versor(dcos)
    dip_v = dip_versor(dcos)
    return (np.outer(dir_v, cos_range) + np.outer(dip_v, sin_range)).T


def small_circle(axis, alpha, n=360):
    k = np.linspace(0., 2 * pi, n)
    dir = direction_versor(axis)
    dip = dip_versor(axis)
    gc = dip[:, None] * np.sin(k) + dir[:, None] * np.cos(k)
    sc = gc * sin(alpha) + axis[:, None] * cos(alpha)
    return sc.T, -sc.T


def net_grid(gcspacing=10., scspacing=10., n=360, clean_caps=True):
    theta = np.linspace(0., 2 * pi, n)
    gcspacing, scspacing = radians(gcspacing), radians(scspacing)
    theta_gc = np.linspace(0. + scspacing, pi - scspacing, n)\
                    if clean_caps else np.linspace(0., pi, n)
    gc_range = np.arange(0., pi + gcspacing, gcspacing)
    sc_range = np.arange(0., pi + scspacing, scspacing)
    i, j, k = np.eye(3)
    ik_circle = i[:, None] * np.sin(theta) + k[:, None] * np.cos(theta)
    great_circles = [(np.array((cos(alpha),.0,-sin(alpha)))[:,None]*np.sin(theta_gc)\
                     + j[:,None]*np.cos(theta_gc)).T for alpha in gc_range] +\
                    [(np.array((cos(alpha),.0,-sin(alpha)))[:,None]*np.sin(theta_gc)\
                     + j[:,None]*np.cos(theta_gc)).T for alpha in -gc_range]
    small_circles = [(ik_circle*sin(alpha) + j[:,None]*cos(alpha)).T\
                                        for alpha in sc_range]
    if clean_caps:
        theta_gc = np.linspace(-scspacing, scspacing, n)
        great_circles += [(np.array((cos(alpha),.0,-sin(alpha)))[:,None]*np.sin(theta_gc)\
                     + j[:,None]*np.cos(theta_gc)).T for alpha in (0, pi/2.)]
        theta_gc = np.linspace(pi - scspacing, pi + scspacing, n)
        great_circles += [(np.array((cos(alpha),.0,-sin(alpha)))[:,None]*np.sin(theta_gc)\
                     + j[:,None]*np.cos(theta_gc)).T for alpha in (0, pi/2.)]
    return great_circles, small_circles


#probably not needed
def clip_lines(data, clip_radius=1.1):
    radii = np.linalg.norm(data, axis=1)
    radii[np.isinf(radii)] = 100.
    radii[np.isnan(radii)] = 100.
    inside = radii < clip_radius
    results = []
    current = []
    for i, is_inside in enumerate(inside):
        if is_inside:
            current.append(data[i])
        elif current:
            results.append(current)
            current = []
    if current:
        results.append(current)
    return results


class Projection(object):
    def __init__(self, settings):
        self.settings = settings
        self.build_rotation_matrix()

    def build_rotation_matrix(self):
        azim = radians(self.settings.rotation_settings['azim'])
        plng = radians(self.settings.rotation_settings['plng'])
        rake = radians(self.settings.rotation_settings['rake'])

        R1 = np.array(((cos(rake), 0., sin(rake)), (0., 1., 0.),
                       (-sin(rake), 0., cos(rake))))

        R2 = np.array(((1., 0., 0.), (0., cos(plng), sin(plng)),
                       (0., -sin(plng), cos(plng))))

        R3 = np.array(((cos(azim), sin(azim), 0.), (-sin(azim), cos(azim), 0.),
                       (0., 0., 1.)))

        self.R = R3.dot(R2).dot(R1)
        self.Ri = np.linalg.inv(self.R)

    def rotate(self, x, y, z):
        self.build_rotation_matrix()
        return self.R.dot((x, y, z))

    def project_data(self, x, y, z, invert_positive=True, ztol=0.,
                     rotate=None):
        if self.settings.check_settings["rotate"] and rotate is None\
                or rotate is True:
            x, y, z = self.rotate(x, y, z)
        if invert_positive:
            c = np.where(z > ztol, -1, 1)
            x, y, z = c * x, c * y, c * z
        if self.settings.general_settings["hemisphere"] == "Upper"\
                and rotate is None:
            c = np.where(z != 0., -1, 1)
            x, y = c * x, c * y
        return self.project(x, y, z)

    def read_plot(self, X, Y):
        if X * X + Y * Y > 1.:
            return ""
        x, y, z = self.inverse(X, Y)
        if self.settings.check_settings["rotate"]:
            x, y, z = self.Ri.dot((x, y, z))
        theta, phi = sphere(x, y, z)
        if phi >= 0.:
            return "Pole: %05.1f/%04.1f\nLine: %05.1f/%04.1f" %\
                (theta, phi, (theta - 180) % 360., 90. - phi)
        else:
            return ""


class EqualAreaProj(Projection):
    name = 'Equal-area'

    def project(self, x, y, z, radius=1.0):
        return x * np.sqrt(1 / (1 - z)), y * np.sqrt(1 / (1 - z))

    def inverse(self, X, Y, radius=1.0):
        X, Y = X * sqrt2, Y * sqrt2
        x = np.sqrt(1 - (X * X + Y * Y) / 4.) * X
        y = np.sqrt(1 - (X * X + Y * Y) / 4.) * Y
        z = -1. + (X * X + Y * Y) / 2
        return x, y, z


class EqualAngleProj(Projection):
    name = 'Equal-angle'

    def project(self, x, y, z, radius=1.0):
        return x / (1 - z), y / (1 - z)

    def inverse(self, X, Y, radius=1.0):
        x = 2. * X / (1. + X * X + Y * Y)
        y = 2. * Y / (1. + X * X + Y * Y)
        z = (-1. + X * X + Y * Y) / (1. + X * X + Y * Y)
        return x, y, z


class DataItem(QtWidgets.QTreeWidgetItem):
    plot_item_name = {}
    default_checked = []
    item_order = {}

    def __init__(self, name, parent):
        super(DataItem, self).__init__(parent)
        self.check_items = {}
        self.plot_item_name.update(dict((v, k) for k, v in\
            self.plot_item_name.items()))
        self.build_items()
        self.build_configuration()
        self.set_checked(self.default_checked)
        self.setText(0, name)
        self.setCheckState(0, QtCore.Qt.Checked)
        self.setFlags(QtCore.Qt.ItemIsUserCheckable |\
            QtCore.Qt.ItemIsEnabled |\
            QtCore.Qt.ItemIsSelectable |\
            QtCore.Qt.ItemIsDragEnabled)
        self.setExpanded(True)

    def build_configuration(self):
        pass

    @property
    def items(self):
        items = [item_name[5:]  for item_name in dir(self)\
            if item_name.startswith('plot_')\
               and callable(getattr(self, item_name))]
        items.sort(key=lambda x: self.item_order.get(x, 999))
        return items

    @property
    def hidden_items(self):
        for item_name in dir(self):
            if item_name.startswith('_plot_')\
               and callable(getattr(self, item_name)):
                yield item_name

    def get_item(self, item_name):
        return getattr(self,\
            "plot_" + item_name.replace(" ", "_"))

    def get_item_props(self, item_name):
        return getattr(self,\
            item_name.replace(" ", "_") + "_settings")

    @property
    def item_settings(self):
        all_settings = {}
        for name, settings in list(vars(self).items()):
            if name.endswith("_settings"):
                all_settings[name] = settings.copy()
        return {self.data_type: all_settings}

    @item_settings.setter
    def item_settings(self, data):
        for name, settings in list(data[self.data_type].items()):
            setattr(self, name, settings)

    @property
    def checked_plots(self):
        return chain.from_iterable((self.get_item(item_name)()\
            for item_name in self.items\
            if self.check_items[self.plot_item_name.get(item_name,\
               item_name)].checkState(0)))

    @property
    def checked_plots(self):
        for item_name in self.items:
            if self.check_items[self.plot_item_name.get(item_name,\
                    item_name)].checkState(0):
                for plot_item in self.get_item(item_name)():
                    yield plot_item
        for item_name in self.hidden_items:
            for plot_item in getattr(self, item_name)():
                yield plot_item

    def get_checked_status(self):
        return {self.plot_item_name.get(item_name,\
                item_name): bool(self.check_items[\
                self.plot_item_name.get(item_name,item_name)].checkState(0))\
                for item_name in self.items}

    def build_items(self):
        for item_name in self.items:
            self.add_item(\
                self.plot_item_name.get(item_name,\
                                        item_name).replace("_", " "))

    def add_item(self, item_name):
        item_widget = QtWidgets.QTreeWidgetItem(self)
        item_widget.setText(0, item_name)
        item_widget.setCheckState(0, QtCore.Qt.Unchecked)
        item_widget.setFlags(QtCore.Qt.ItemIsUserCheckable |\
            QtCore.Qt.ItemIsEnabled |\
            QtCore.Qt.ItemIsSelectable)
        self.check_items[item_name] = item_widget

    def set_checked(self, item_list):
        if type(item_list) == list:
            for item_name in item_list:
                self.check_items[item_name].setCheckState(0, QtCore.Qt.Checked)
        else:
            for item_name in item_list:
                self.check_items[item_name].setCheckState(0,\
                    QtCore.Qt.Checked if item_list[item_name]\
                    else QtCore.Qt.Unchecked)


class CircularData(DataItem):
    data_type = "circular_data"
    default_checked = [
        "Rose",
    ]
    properties_ui = circular_Ui_Dialog

    def __init__(self, name, data_path, data, parent, **kwargs):
        self.data_path = data_path
        self.kwargs = kwargs
        self.auttitude_data = data if isinstance(data, DirectionalData)\
                                else load(data, **kwargs)
        super(CircularData, self).__init__(name, parent)

    def build_configuration(self):
        self.rose_check_settings = {\
            "standard":True,\
            "continuous":False,\
            "weightmunro":True,\
            "dd":True,\
            "dir":False,\
            "diraxial":False,\
            "weightcolumn":False,\
            "mean":True,\
            "confidence":True,\
            "petals":True,\
            "petalsfill":True,\
            "petalsoutline":True,\
            "kite":False,
            "kitefill":True,\
            "kiteoutline":True,\
            "lines":False,\
            "meandeviation":True,\
            "360d":True,\
            "180d":False,\
            "interval":False}
        self.rose_settings = {\
            "binwidth":10.,\
            "offset":5.,\
            "aperture":11.,\
            "weightmunro":.9,\
            "spacing":2.0,\
            "offsetcont":0.,\
            "weightcolumn":1,\
            "confidence":95.0,\
            "intervalfrom":0.,\
            "intervalto":180.,}
        self.rose_mean_settings = {
            "linestyle":"-",\
            "color":"#000000",\
            "linewidth":1}
        self.petals_settings = {
            "facecolor":"#4D4D4D",\
            "edgecolor":"#000000",\
            "linewidth":1}
        self.kite_settings = {
            "facecolor":"#4D4D4D",\
            "edgecolor":"#000000",\
            "linewidth":1}
        self.lines_settings = {
            "linestyle":":",\
            "color":"#000000",\
            "linewidth":1}

    def plot_Rose(self):
        plot_data = []
        grid = self.auttitude_data.cgrid
        full_circle = False
        if self.rose_check_settings["360d"]:
            from_, to_ = 0., 2 * pi
            full_circle = True
        elif self.rose_check_settings["180d"]:
            from_, to_ = 0., pi
        else:
            from_ = radians(self.rose_settings["intervalfrom"])
            to_ = radians(self.rose_settings["intervalto"])
        if self.rose_check_settings["weightcolumn"]:
            data_weight = np.array([float(line[self.rose_settings["weightcolumn"]])\
                for line in self.auttitude_data.input_data])
        else:
            data_weight = None
        if self.rose_check_settings["standard"]:
            nodes = grid.build_grid(\
                self.rose_settings["binwidth"],\
                self.rose_settings["offset"],\
                from_, to_)
            radii = self.auttitude_data.grid_rose(\
                aperture=self.rose_settings["binwidth"],\
                axial=self.rose_check_settings["diraxial"],\
                direction=self.rose_check_settings["dir"],\
                nodes=nodes, data_weight=data_weight)
        else:
            nodes = grid.build_grid(self.rose_settings["spacing"],\
                self.rose_settings["offsetcont"], from_, to_)
            if self.rose_check_settings["weightmunro"]:
                radii = self.auttitude_data.grid_munro(\
                    weight=self.rose_settings["weightmunro"],\
                    aperture=self.rose_settings["aperture"],\
                    axial=self.rose_check_settings["diraxial"],\
                    spacing=self.rose_settings["spacing"],\
                    offset=self.rose_settings["offsetcont"],\
                    direction=self.rose_check_settings["dir"],\
                    nodes=nodes, data_weight=data_weight)
            else:
                radii = self.auttitude_data.grid_rose(\
                    aperture=self.rose_settings["aperture"],\
                    axial=self.rose_check_settings["diraxial"],\
                    spacing=self.rose_settings["spacing"],\
                    offset=self.rose_settings["offsetcont"],\
                    direction=self.rose_check_settings["dir"],\
                    nodes=nodes, data_weight=data_weight)
        if self.rose_check_settings["petals"]:
            petal_settings = {
                "facecolor":self.petals_settings["facecolor"]\
                    if self.rose_check_settings["petalsfill"] else "none",\
                "edgecolor":self.petals_settings["edgecolor"]\
                    if self.rose_check_settings["petalsoutline"] else "none",\
                "linewidth":self.petals_settings["linewidth"]}
            plot_data.append(PetalsPlotData(nodes, radii, petal_settings))
        elif self.rose_check_settings["kite"]:
            kite_settings = {
                "facecolor":self.kite_settings["facecolor"]\
                    if self.rose_check_settings["kitefill"] else "none",\
                "edgecolor":self.kite_settings["edgecolor"]\
                    if self.rose_check_settings["kiteoutline"] else "none",\
                "linewidth":self.kite_settings["linewidth"]}
            plot_data.append(
                KitePlotData(nodes, radii, full_circle, kite_settings))
        elif self.rose_check_settings["lines"]:
            plot_data.append(LinesPlotData(nodes, radii,\
                self.rose_check_settings["meandeviation"],\
                self.lines_settings))
        if self.rose_check_settings["mean"]:
            theta = self.auttitude_data.circular_mean_direction_axial if\
                self.rose_check_settings["diraxial"] else\
                self.auttitude_data.circular_mean_direction
            confidence = self.auttitude_data.estimate_circular_confidence(\
                self.rose_check_settings["diraxial"],\
                self.rose_settings["confidence"]/100.)[1]\
                if self.rose_check_settings["confidence"] else None
            if self.rose_check_settings["dir"]:
                theta -= 90.
            plot_data.append(RoseMeanPlotData(theta, confidence,\
                                        self.rose_check_settings["diraxial"],
                                        self.rose_mean_settings))
        return plot_data


class AttitudeData(CircularData):
    data_type = "attitude_data"

    def build_configuration(self):
        super(AttitudeData, self).build_configuration()
        self.point_settings={'marker':'o',\
                             'c':'#000000',\
                             'ms':3.0,}
        self.meanpoint_settings={'marker':'*',\
                             'c':'#000000',\
                             'ms':12.0,}
        self.scaxis_settings={'marker':'o',\
                             'c':'#000000',\
                             'ms':3.0,}
        self.sccirc_settings={"linewidths":1.,\
                            "colors":"#000000",\
                            "linestyles":"-"}
        self.sccalc_settings = {
            "eiv": 0,
        }
        self.contour_settings = {"cmap":"Reds",\
                                 "linestyles":"-",\
                                 "antialiased":True,\
                                 "intervals":"",\
                                 "ncontours":10,\
                                 "cresolution":250}
        self.contour_line_settings={"cmap":"jet",\
                                    "colors":"#4D4D4D",\
                                    "linewidths":0.50}
        self.contour_calc_settings = {"spacing":2.5,\
                                      "K":100,\
                                     "scperc":1.0,\
                                     "scangle":10.0,}
        self.contour_check_settings = {"solidline":False,\
                                      "gradientline":True,\
                                      "fillcontours":True,\
                                      "drawover":True,\
                                      "minmax":True,\
                                      "zeromax":False,\
                                      "customintervals":False,\
                                      "fisher":True,\
                                      "scangle":False,\
                                      "scperc":False,\
                                      "autocount":False,\
                                      "robinjowett":True,\
                                      "digglefisher":False}
        self.check_settings = {"v1point": True,\
                               "v1GC": True,\
                               "v2point": True,\
                               "v2GC": True,\
                               "v3point": True,\
                               "v3GC": True,\
                               "meanpoint": False,\
                               "meanpointeiv": True,\
                               "scaxis":False,\
                               "sccirc":False,\
                               "concentratesc":False}
        self.v1point_settings={'marker':'*',\
                             'c':'#00FF00',\
                             'ms':12.0,}
        self.v2point_settings={'marker':'*',\
                             'c':'#FF0000',\
                             'ms':12.0,}
        self.v3point_settings={'marker':'*',\
                             'c':'#0000FF',\
                             'ms':12.0,}
        self.v1GC_settings= {"linewidths":1.0,\
                                "colors":"#00FF00",\
                                "linestyles":"-"}
        self.v2GC_settings= {"linewidths":1.0,\
                                "colors":"#FF0000",\
                                "linestyles":"-"}
        self.v3GC_settings= {"linewidths":1.0,\
                                "colors":"#0000FF",\
                                "linestyles":"-"}

        self.checklegend_settings= {"point":True,\
                                  "GC":True,\
                                  "meanpoint":True,\
                                  "scaxis":True,\
                                  "sccirc":True,\
                                  "v1point":True,\
                                  "v1GC":True,\
                                  "v2point":True,\
                                  "v2GC":True,\
                                  "v3point":True,\
                                  "v3GC":True}
        self.legend_settings= {"point":'',\
                               "GC":'',\
                               "meanpoint":'',\
                               "scaxis":'',\
                               "sccirc":'',\
                               "v1point":'',\
                               "v1GC":'',\
                               "v2point":'',\
                               "v2GC":'',\
                               "v3point":'',\
                               "v3GC":''}

    def reload_data(self):
        data = get_data(self.data_path, self.auttitude_data.kwargs)
        self.auttitude_data = load(data, **self.auttitude_data.kwargs)

    def plot_Points(self):
        if self.legend_settings['point']:
            try:
                legend_text = \
                self.legend_settings['point'].format(data=self.auttitude_data)
            except:
                legend_text = self.legend_settings['point']
        else:
            legend_text = "{} ({})".format(self.text(0),\
                self.plot_item_name.get('Points', 'Points'))
        return (PointPlotData(self.auttitude_data.data, self.point_settings,
                              self.checklegend_settings['point'],
                              legend_text), )

    def _plot_SC(self):
        plot_items = []
        if self.check_settings["scaxis"] or self.check_settings["sccirc"]:
            data = self.auttitude_data.data
            projection = self.treeWidget().window().projection()
            if self.check_settings["concentratesc"]:
                eiv = self.auttitude_data.eigenvectors[self.sccalc_settings[
                    "eiv"]]
                data = data * np.where(data.dot(eiv) > 0, 1, -1)[:, None]
            elif projection.settings.check_settings["rotate"]:
                data = projection.rotate(*data.T).T
                data = data * np.where(data[:, 2] > 0, -1, 1)[:, None]
            axis, alpha = autti.small_circle_axis(data)
            if self.check_settings["scaxis"]:
                if self.legend_settings['scaxis']:
                    try:
                        legend_text = \
                        self.legend_settings['scaxis'].format(data=self.auttitude_data)
                    except:
                        legend_text = self.legend_settings['scaxis']
                else:
                    legend_text = "{} ({} Axis)".format(self.text(0),\
                        self.plot_item_name.get('SC', 'Small Circle'))
                plot_items.append(PointPlotData(axis,\
                                               self.scaxis_settings,\
                                               self.checklegend_settings['scaxis'],\
                                               legend_text))
            if self.check_settings["sccirc"]:
                if self.legend_settings['sccirc']:
                    try:
                        legend_text = \
                        self.legend_settings['sccirc'].format(data=self.auttitude_data)
                    except:
                        legend_text = self.legend_settings['sccirc']
                else:
                    legend_text = "{} ({})".format(self.text(0),\
                        self.plot_item_name.get('SC', 'Small Circle'))
                plot_items.append(CirclePlotData(small_circle(axis, alpha),\
                                               self.sccirc_settings,\
                                               self.checklegend_settings['sccirc'],\
                                               legend_text))
        return plot_items

    def _plot_Mean(self):
        if self.check_settings['meanpoint']:
            if self.legend_settings['meanpoint']:
                try:
                    legend_text = \
                    self.legend_settings['meanpoint'].format(data=self.auttitude_data)
                except:
                    legend_text = self.legend_settings['meanpoint']
            else:
                legend_text = "{} ({})".format(self.text(0),\
                    self.plot_item_name.get('meanpoint', 'Mean'))
            return (PointPlotData(self.auttitude_data.mean_vector if not\
                                    self.check_settings['meanpointeiv'] else\
                                    self.auttitude_data.concentrated_mean_vector,
                                  self.meanpoint_settings,
                                  self.checklegend_settings['meanpoint'],
                                  legend_text),
                   )
        else:
            return []

    def plot_Eigenvectors(self):
        plot_data = []
        for i, eiv in enumerate(("v1point", "v2point", "v3point")):
            if self.check_settings[eiv]:
                if self.legend_settings[eiv]:
                    try:
                        legend_text = \
                        self.legend_settings[eiv].format(data=self.auttitude_data)
                    except:
                        legend_text = self.legend_settings[eiv]
                else:
                    legend_text = "{} (EV {})".format(self.text(0), i + 1)
                plot_data.append(PointPlotData(self.auttitude_data.eigenvectors[i],\
                                               self.get_item_props(eiv),\
                                               self.checklegend_settings[eiv],\
                                               legend_text))
        for i, eiv in enumerate(("v1GC", "v2GC", "v3GC")):
            if self.check_settings[eiv]:
                if self.legend_settings[eiv]:
                    try:
                        legend_text = \
                        self.legend_settings[eiv].format(data=self.auttitude_data)
                    except:
                        legend_text = self.legend_settings[eiv]
                else:
                    legend_text = "{} (EV {})".format(self.text(0), i + 1)
                plot_data.append(CirclePlotData((great_circle(self.auttitude_data.eigenvectors[i]),),\
                                                self.get_item_props(eiv),\
                                                self.checklegend_settings[eiv],\
                                                legend_text))
        return plot_data

    def plot_Contours(self):
        grid = self.auttitude_data.grid
        grid.change_spacing(self.contour_calc_settings['spacing'])
        nodes = self.auttitude_data.grid_nodes
        if self.contour_check_settings["fisher"]:
            if self.contour_check_settings["autocount"]:
                if self.contour_check_settings["robinjowett"]:
                    k = None
                else:
                    try:
                        k = grid.optimize_k(self.auttitude_data.data)
                    except ImportError:
                        QtWidgets.QMessageBox.warning(self.parent(), "Scipy not Found",\
                            "Scipy is needed for Diggle & Fisher method. Defaulting to Robin & Jowett.")
                        k = None
            else:
                k = self.contour_calc_settings['K']
            count = self.auttitude_data.grid_fisher(k)
        else:
            if self.contour_check_settings["autocount"]:
                if self.contour_check_settings["robinjowett"]:
                    theta = None
                else:
                    try:
                        theta = degrees(acos(\
                            1. - 1./grid.optimize_k(self.auttitude_data.data)))
                    except ImporError:
                        QtWidgets.QMessageBox.warning(self.parent(), "Scipy not Found",\
                            "Scipy is needed for Diggle & Fisher method. Defaulting to Robin & Jowett.")
                        theta = None
            else:
                theta = self.contour_calc_settings['scangle']\
                        if self.contour_check_settings["scangle"]\
                        else degrees(0.141536 * self.contour_calc_settings['scperc'])
            count = self.auttitude_data.grid_kamb(theta)
        return (ContourPlotData(nodes, count, self.contour_settings,\
                    self.contour_line_settings, self.contour_check_settings,\
                    n=self.auttitude_data.n),)

    def _plot_Classification(self):
        if self.legend_settings['point']:
            try:
                legend_text = \
                self.legend_settings['point'].format(data=self.auttitude_data)
            except:
                legend_text = self.legend_settings['point']
        else:
            legend_text = "{} ({})".format(self.text(0),\
                self.plot_item_name.get('Points', 'Points'))
        return (ClassificationPlotData(self.auttitude_data.vollmer_G,\
                                       self.auttitude_data.vollmer_R,\
                                       self.auttitude_data.woodcock_Kx,\
                                       self.auttitude_data.woodcock_Ky,\
                                       self.point_settings,\
                                       self.checklegend_settings['point'],\
                                       legend_text), )


class PlaneData(AttitudeData):
    data_type = "plane_data"
    plot_item_name = {"Points": "Poles", 'GC': 'Great Circles'}
    item_order = {"Points": 0, "GC": 1, "Eigenvectors": 2, "Contours": 3}
    default_checked = ["Poles", "Rose"]
    properties_ui = plane_Ui_Dialog

    def build_configuration(self):
        super(PlaneData, self).build_configuration()
        self.GC_settings = {"linewidths":0.8,\
                                "colors":"#4D4D4D",\
                                "linestyles":"-"}

    def plot_GC(self):
        circles = [great_circle(point) for point in self.auttitude_data.data]
        if self.legend_settings['GC']:
            try:
                legend_text = \
                self.legend_settings['GC'].format(data=self.auttitude_data)
            except:
                legend_text = self.legend_settings['GC']
        else:
            legend_text = "{} ({})".format(self.text(0),\
                self.plot_item_name.get('GC', 'Great Circles'))
        return (CirclePlotData(circles, self.GC_settings,
                               self.checklegend_settings['GC'], legend_text), )


class LineData(AttitudeData):
    data_type = "line_data"
    plot_item_name = {"Points": "Lines"}
    item_order = {"Points": 0, "Contours": 3}
    default_checked = ["Lines", "Rose"]
    properties_ui = line_Ui_Dialog


class SmallCircleData(DataItem):
    data_type = "smallcircle_data"
    plot_item_name = {"SC": "Small Circles"}
    default_checked = ["Axes", "Small Circles"]
    properties_ui = smallcircle_Ui_Dialog

    def __init__(self, name, data_path, data, parent, **kwargs):
        self.data_path = data_path
        self.auttitude_data = data if isinstance(data, DirectionalData)\
                                else load(data, **kwargs)
        self.alpha_column = kwargs["alpha_column"]
        self.alpha = [float(line[self.alpha_column]) for line in\
                                    self.auttitude_data.input_data]
        super(SmallCircleData, self).__init__(name, parent)

    def build_configuration(self):
        super(SmallCircleData, self).build_configuration()
        self.scaxis_settings={'marker':'o',\
                             'c':'#000000',\
                             'ms':3.0,}
        self.sccirc_settings={"linewidths":1.,\
                            "colors":"#000000",\
                            "linestyles":"-"}

        self.checklegend_settings= {"scaxis":True,\
                                  "sccirc":True,}
        self.legend_settings= {"scaxis":'',\
                               "sccirc":'',}

    def reload_data(self):
        data = get_data(self.data_path, self.auttitude_data.kwargs)
        self.auttitude_data = load(data, calculate_statistics=False,\
                                   **self.auttitude_data.kwargs)

    def plot_Axes(self):
        if self.legend_settings['scaxis']:
            try:
                legend_text = \
                self.legend_settings['scaxis'].format(data=self.auttitude_data)
            except:
                legend_text = self.legend_settings['scaxis']
        else:
            legend_text = "{} ({})".format(self.text(0),\
                self.plot_item_name.get('scaxis', 'scaxis'))
        return (PointPlotData(self.auttitude_data.data, self.scaxis_settings,
                              self.checklegend_settings['scaxis'],
                              legend_text), )

    def plot_SC(self):
        plot_items = []
        if self.legend_settings['sccirc']:
            try:
                legend_text = \
                self.legend_settings['sccirc'].format(data=self.auttitude_data)
            except:
                legend_text = self.legend_settings['sccirc']
        else:
            legend_text = "{} ({})".format(self.text(0),\
                self.plot_item_name.get('SC', 'Small Circle'))
        circles = chain.from_iterable(small_circle(axis, radians(alpha))\
                for axis, alpha in zip(self.auttitude_data.data, self.alpha))
        plot_items.append(CirclePlotData(circles,\
                                       self.sccirc_settings,\
                                       self.checklegend_settings['sccirc'],\
                                       legend_text))
        return plot_items


class OSSettings(object):
    def __init__(self):
        self.rotation_settings = {'azim': 0., 'plng': 0., 'rake': 0.}
        self.projection_settings = {"gcspacing":10.0,\
                                    "scspacing":10.0,\
                                    "cardinalborder":2.0}
        self.GC_settings = {"linewidths":0.25,\
                            "colors":"#808080",\
                            "linestyles":"-"}
        self.SC_settings = {"linewidths":0.25,\
                            "colors":"#808080",\
                            "linestyles":"-"}
        self.mLine_settings={"linewidth":1.00,\
                            "color":"#00CCCC",\
                            "linestyle":"-"}
        self.mGC_settings= {"linewidth":1.00,\
                            "color":"#555555",\
                            "linestyle":":"}
        self.check_settings={"grid":False,\
                             "rotate":False,\
                             "cardinal":True,\
                             "cardinalborder":True,\
                             "colorbar":True,\
                             "colorbarpercentage":True,\
                             "measurelinegc":True}
        self.rose_check_settings={\
                             "outer":True,\
                             "autoscale":False,\
                             "scaletxt":True,\
                             "rings":True,\
                             "diagonals":True,\
                             "360d":True,\
                             "180d":False,\
                             "interval":False}
        self.rose_settings= {\
                             "outerperc":10.,\
                             "ringsperc":2.5,\
                             "diagonalsang":22.5,\
                             "diagonalsoff":0.0,\
                             "outerwidth":1.,\
                             "ringswidth":.5,\
                             "diagonalswidth":.5,\
                             "from":0.,\
                             "to":180.,\
                             "scaleaz":90.,\
                             "outerc":"#000000",\
                             "ringsc":"#555555",\
                             "diagonalsc":"#555555"}
        self.general_settings = {
                            'fontsize':'x-small',
                            'projection':'Equal-Area',\
                            'hemisphere':'Lower',\
                            'colorbar':'',
                            'title':'',\
                            'description':'',\
                            'author':'',\
                            'lastsave':'',\
                            'packeddata':"no"}

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
        return getattr(self,\
            item_name.replace(" ", "_") + "_settings")


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
            if self.do_skip.isChecked(): header_row += self.skip_rows.value()
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

            #try:
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
        if not fname: return
        self.fname.setText(fname)
        self.on_file_changed()

    @property
    def import_kwargs(self):
        kwargs ={"worksheet":self.worksheet.currentIndex(),\
                "keep_input":True,\
                "line":self.lines.isChecked() or self.small_circle.isChecked(),\
                "dip_direction":self.planetype.currentIndex() == 0,\
                "dipdir_column":self.longitude.currentIndex(),\
                "dip_column":self.colatitude.currentIndex(),\
                "alpha_column":self.alpha.currentIndex(),\
                "circular":self.circular.isChecked(),\
                "data_headers":self.header if self.has_header.isChecked() else\
                               None,
                "has_header": self.has_header.isChecked(),
                "header_row":self.header_row.value() if\
                               self.has_header.isChecked() else None,
                "skip_rows":self.skip_rows.value() if\
                               self.do_skip.isChecked() else None,
                "is_geoeas":self.geoeas,
                "geoeas_offset":self.offset if self.geoeas else None
                }
        if self.dialect is not None:
            kwargs["dialect_data"] = {\
                    "delimiter":self.dialect.delimiter,\
                    "doublequote":self.dialect.doublequote,\
                    "escapechar":self.dialect.escapechar,\
                    "lineterminator":self.dialect.lineterminator,\
                    "quotechar":self.dialect.quotechar,\
                    "quoting":self.dialect.quoting,\
                    "skipinitialspace":self.dialect.skipinitialspace}
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
            if self.do_skip.isChecked(): header_row += self.skip_rows.value()
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
        header_row = 0 if kwargs['header_row'] is None else kwargs['header_row'] + 1
        header_row += 0 if kwargs['skip_rows'] is None else kwargs['skip_rows']
        return [sheet.row_values(i) for i in range(header_row, sheet.nrows)]
    else:
        f = open(fname, "r")
        if kwargs['is_geoeas']:
            f.seek(kwargs['geoeas_offset'])
        skip_rows = 0 if kwargs['header_row'] is None else kwargs['header_row'] + 1
        skip_rows += 0 if kwargs['skip_rows'] is None else kwargs['skip_rows']
        dialect_data = {}
        for key, item in list(kwargs["dialect_data"].items()):
            dialect_data[key] = str(item) if isinstance(item,
                                                        str) else item
        reader = csv.reader(f, **dialect_data)
        for i in range(skip_rows):
            next(reader)
        return reader


class MeshDialog(QtWidgets.QDialog, import_ply_Ui_Dialog):
    default_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

    def __init__(self, parent=None):
        super(MeshDialog, self).__init__(parent)
        self.setupUi(self)
        for color in self.default_colors:
            self.add_color_to_list(color)
        self.add_color_button.clicked.connect(self.add_color)
        self.remove_color_button.clicked.connect(self.remove_color)

    def add_color_to_list(self, color):
        item = QtWidgets.QListWidgetItem(",".join(str(c)
                                              for c in color), self.color_list)
        item.setForeground(QtGui.QColor(*color))

    def add_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.add_color_to_list((color.red(), color.green(), color.blue()))

    #http://stackoverflow.com/a/7486225/1457481
    def remove_color(self):
        current_item = self.color_list.currentItem()
        self.color_list.takeItem(self.color_list.row(current_item))

    @property
    def colors(self):
        return [tuple([int(c) for c in self.color_list.item(i).text().split(',')] + [255,])\
                        for i in range(self.color_list.count())]


class Main(QtWidgets.QMainWindow, Ui_MainWindow):
    #data_items = {}
    data_types = {data_type.data_type: data_type for data_type in \
                        (AttitudeData, PlaneData, LineData, SmallCircleData,\
                         CircularData)}

    def __init__(self):
        super(Main, self).__init__()
        self.setupUi(self)

        self.OS_settings = OSSettings()
        self.settings = {
            'fontsize':'x-small',
            'title':'',\
            'summary':'',\
            'description':'',\
            'author':'',\
            'credits':'',\
            'last_saved':''}

        self.projections = {'Equal-Area': EqualAreaProj(self.OS_settings),\
                            'Equal-Angle':EqualAngleProj(self.OS_settings)}

        #self.projection_option = QtWidgets.QActionGroup(self, exclusive=True)
        #self.projection_option.addAction(self.actionEqual_Area)
        #self.projection_option.addAction(self.actionEqual_Angle)

        self.actionImport_Plane_Data_DD.triggered.connect(\
            lambda: self.import_files(\
                        data_type="plane_data", direction=False,\
                        dialog_title='Import plane data'))
        self.actionImport_Plane_Data_Dir.triggered.connect(\
            lambda: self.import_files(\
                        data_type="plane_data", direction=True,\
                        dialog_title='Import plane data'))
        self.actionImport_Line_Data_Trend.triggered.connect(\
            lambda: self.import_files(\
                        data_type="line_data", direction=False,\
                        dialog_title='Import line data'))
        self.actionImport_Small_Circle_Data.triggered.connect(\
            lambda: self.import_files(\
                        data_type="smallcircle_data", direction=False,\
                        dialog_title='Import Small Circle data'))
        self.actionImport_Circular_Data_Trend.triggered.connect(\
            lambda: self.import_files(\
                        data_type="circular_data", direction=False,\
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

        self.actionConvert_Shapefile_to_Azimuth_data.triggered.connect(\
            self.import_shapefile)
        self.actionConvert_Mesh_to_Plane_Data.triggered.connect(
            self.import_mesh)

        self.plotButton.clicked.connect(self.plot_data)
        self.settingsButton.clicked.connect(self.show_settings_dialog)
        self.clearButton.clicked.connect(self.clear_plot)

        self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(
            self.tree_context_menu)
        #http://stackoverflow.com/a/4170541/1457481
        self.treeWidget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)

        self.save_shortcut = QtWidgets.QShortcut("Ctrl+S", self,
                                             self.save_project_dialog)
        self.save_as_shortcut = QtWidgets.QShortcut("Ctrl+Shift+S", self,
                                                self.save_project_as_dialog)
        self.open_shortcut = QtWidgets.QShortcut("Ctrl+O", self,
                                             self.open_project_dialog)

        self.rename_shortcut = QtWidgets.QShortcut("F2", self,
                                               self.rename_dataitem)

        self.copy_shortcut = QtWidgets.QShortcut("Ctrl+C", self,
                                             self.copy_props_dataitem)
        self.paste_shortcut = QtWidgets.QShortcut("Ctrl+V", self,
                                              self.paste_props_dataitem)

        self.plot_shortcut = QtWidgets.QShortcut("Ctrl+P", self, self.plot_data)
        self.clear_shortcut = QtWidgets.QShortcut("Ctrl+L", self, self.clear_plot)
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
        if not fnames: return
        for fname in fnames:
            dialog = ImportDialog(self, fname=fname, data_type=data_type,\
                                        direction=direction)
            fname = dialog.fname.text()
            data_type, letter = dialog.data_type
            data_name = "({}){}".format(letter, path.basename(fname))
            reader = dialog.get_data()
            self.import_data(data_type,
                             data_name,\
                             data_path = fname,\
                             data = reader,\
                             **dialog.import_kwargs)

    def import_dialog(self, item=None, try_default=False, data_type=None,\
                                 direction=False, fname=None,\
                                 dialog_title='Import data'):
        if fname is None:
            fname, extension =\
                QtWidgets.QFileDialog.getOpenFileName(self, dialog_title)
        if try_default and not fname: return
        dialog = ImportDialog(self, fname=fname, data_type=data_type,\
                                    direction=direction)
        if try_default or dialog.exec_():
            fname = dialog.fname.text()
            data_type, letter = dialog.data_type
            data_name = "({}){}".format(letter, path.basename(fname))
            reader = dialog.get_data()
            return self.import_data(data_type,
                                    data_name,\
                                    data_path = fname,\
                                    data = reader,\
                                    **dialog.import_kwargs)

    def import_shapefile(self):
        fname, extension =\
            QtWidgets.QFileDialog.getOpenFileName(self, 'Select Shapefile to convert',\
                filter="ESRI Shapefile (*.shp);;All Files (*.*)")
        if not fname: return
        name, ext = path.splitext(fname)

        fname_out, extension =\
            QtWidgets.QFileDialog.getSaveFileName(self, 'Save azimuth data as',\
                name + ".txt",\
                filter="Text Files (*.txt);;All Files (*.*)")
        if not fname_out: return
        with open(fname_out, "wb") as f:
            sf = shapefile.Reader(fname)
            f.write("azimuth;length\n")
            for shape in sf.shapes():
                for A, B in pairwise(shape.points):
                    f.write("{};{}\n".format(\
                        bearing(A[0], B[0], A[1], B[1]),\
                        haversine(A[0], B[0], A[1], B[1])))
        self.import_dialog(try_default=True, fname=fname_out,\
                                data_type="circular_data", direction=False,\
                                dialog_title='Import Azimuth data')

    def import_mesh(self):
        fname, extension =\
            QtWidgets.QFileDialog.getOpenFileName(self, 'Select Mesh to convert',\
                filter="Stanford Polygon (*.ply);;All Files (*.*)")
        if not fname: return
        name, ext = path.splitext(fname)
        dialog = MeshDialog(self)
        if dialog.exec_():
            self.statusBar().showMessage('Processing Mesh %s...' % fname)
            colors = dialog.colors
            if not colors: return
            with open(fname, "rb") as f:
                output = extract_colored_faces(f, colors)
            self.statusBar().showMessage('Ready')
            if dialog.check_separate.isChecked():
                dirname =\
                    QtWidgets.QFileDialog.getExistingDirectory(self, 'Save data files to')
                if not dirname: return
                color_filenames = []
                for color in list(output.keys()):
                    color_filename = "{0}_{1}.txt".format(name, color[:-1])
                    color_filenames.append((color, color_filename))
                    with open(color_filename, "wb") as f:
                        writer = csv.writer(f)
                        writer.writerow(\
                            ["dip_direction","dip","X","Y","Z","trace"])
                        for line in output[color]:
                            writer.writerow(line)
                for color, color_filename in color_filenames:
                    item = self.import_dialog(try_default=True,\
                                fname=color_filename,\
                                data_type="plane_data", direction=False,\
                                dialog_title='Import plane data')
                    item.point_settings["c"] = '#%02x%02x%02x' % color[:-1]
                return
            else:
                fname_out, extension =\
                    QtWidgets.QFileDialog.getSaveFileName(self, 'Save plane data as',\
                        name + ".txt",\
                        filter="Text Files (*.txt);;All Files (*.*)")
                if not fname_out: return
                with open(fname_out, "wb") as f:
                    writer = csv.writer(f)
                    writer.writerow(\
                        ["dip_direction","dip","X","Y","Z","trace","R","G","B"])
                    for color in list(output.keys()):
                        for line in output[color]:
                            writer.writerow(line + color[:-1])
                item = self.import_dialog(try_default=True, fname=fname_out,\
                            data_type="plane_data", direction=False,\
                            dialog_title='Import plane data')

    def merge_data_dialog(self, current_item=None):
        merge_dialog = QtWidgets.QDialog(self)
        merge_dialog_ui = merge_data_Ui_Dialog()
        merge_dialog_ui.setupUi(merge_dialog)
        data_items = {item.text(0): item for item in self.get_data_items() if\
                        isinstance(item, CircularData)}
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

        #http://stackoverflow.com/a/22798753/1457481
        if current_item is not None:
            index = merge_dialog_ui.A.findText(current_item)
            if index >= 0:
                merge_dialog_ui.A.setCurrentIndex(index)
        A_changed()

        def on_browse():
            fname, extension =\
                QtWidgets.QFileDialog.getSaveFileName(self, 'Save merged data')
            if not fname: return
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
                merged_item = self.data_types[A.data_type](name=merged_name,\
                    data_path=merged_fname,\
                    data = merged_data,\
                    parent=self.treeWidget, **A.kwargs)
                merged_item.item_settings = A.item_settings
            self.statusBar().showMessage('Merged items %s and %s as %s' %\
                (A.text(0), B.text(0), merged_name))

    def rotate_data_dialog(self, current_item=None):
        rotate_dialog = QtWidgets.QDialog(self)
        rotate_dialog_ui = rotate_data_Ui_Dialog()
        rotate_dialog_ui.setupUi(rotate_dialog)
        data_items = {item.text(0): item for item in self.get_data_items() if\
                        isinstance(item, AttitudeData)}
        if not data_items:
            self.statusBar().showMessage('No items to rotate')
            return
        for item_name in list(data_items.keys()):
            rotate_dialog_ui.A.addItem(item_name)

        def data_changed(event=None):
            A = data_items[rotate_dialog_ui.A.currentText()]
            A_name, A_ext = path.splitext(A.data_path)
            rotate_dialog_ui.savename.setText(A_name +\
                 "-rot_{}_{}_{}.txt".format(rotate_dialog_ui.trend.value(),\
                                            rotate_dialog_ui.plunge.value(),\
                                            rotate_dialog_ui.angle.value(),))

        #http://stackoverflow.com/a/22798753/1457481
        def on_browse():
            fname, extension =\
                QtWidgets.QFileDialog.getSaveFileName(self, 'Save rotated data')
            if not fname: return
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
            u = dcos_lines(np.radians((rotate_dialog_ui.trend.value(),\
                                       rotate_dialog_ui.plunge.value())))
            rotated_data = autti.rotate(A.auttitude_data, u,\
                                       rotate_dialog_ui.angle.value())
            rotated_name = A.text(0) +\
                "-rot_{}_{}_{}".format(rotate_dialog_ui.trend.value(),\
                                       rotate_dialog_ui.plunge.value(),\
                                       rotate_dialog_ui.angle.value(),)
            rotated_fname = rotate_dialog_ui.savename.text()
            np.savetxt(rotated_fname, rotated_data.data_sphere)
            if rotate_dialog_ui.keep.isChecked():
                rotated_item = self.data_types[A.data_type](name=rotated_name,\
                    data_path=rotated_fname,\
                    data = rotated_data,\
                    parent=self.treeWidget, **A.kwargs)
                rotated_item.item_settings = A.item_settings
            self.statusBar().showMessage('Rotated item %s to %s' %\
                (A.text(0), rotated_name))

    #@waiting_effects
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
            QtWidgets.QFileDialog.getOpenFileName(self, 'Open project',\
                filter="Openstereo Project Files (*.openstereo);;All Files (*.*)")
        if not fname: return
        self.new_project()
        self.open_project(fname)
        self.current_project = fname
        self.statusBar().showMessage('Loaded project from %s' % fname)
        self.set_title()

    def save_project_dialog(self):
        if self.current_project is None:
            fname, extension =\
                QtWidgets.QFileDialog.getSaveFileName(self, 'Save project',\
                    filter="Openstereo Project Files (*.openstereo);;All Files (*.*)")
            if not fname: return
            self.current_project = fname
        self.save_project(self.current_project)
        self.statusBar().showMessage(
            'Saved project to %s' % self.current_project)
        self.set_title()

    def save_project_as_dialog(self, pack=False):
        fname, extension =\
            QtWidgets.QFileDialog.getSaveFileName(self, 'Save project',\
                filter="Openstereo Project Files (*.openstereo);;All Files (*.*)")
        if not fname: return
        self.current_project = fname
        if pack:
            self.OS_settings.general_settings['packeddata'] = 'yes'
        self.save_project(fname)
        self.statusBar().showMessage('Saved project to %s' % fname)
        self.set_title()

    def save_project(self, fname):
        ozf = zipfile.ZipFile(fname, mode='w')
        self.OS_settings.general_settings["lastsave"] = str(datetime.now())
        project_data = {"global_settings": self.OS_settings.item_settings,\
                        "version": __version__,\
                        "items": []}
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
                    #as packed data are stored flat, this bellow is to avoid
                    #name colision.
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
            ozf.writestr(item_settings_name,\
                        json.dumps(item.item_settings, indent=2))
            if item_path is not None:
                item_path = path.relpath(item_path, project_dir)
            project_data['items'].append(\
                    {'name':item.text(0),
                     'path': item_path,
                     'checked':bool(item.checkState(0)),
                     'checked_plots':item.get_checked_status(),
                     'kwargs':item.auttitude_data.kwargs})
        ozf.writestr("project_data.json",\
                     json.dumps(project_data, indent=3))
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
                        possible_path = path.normpath(\
                            path.join(current_dir,\
                                path.relpath(item_file, original_dir)))
                        if path.exists(possible_path):
                            item_file = possible_path
                            break
                    else:
                        fname, extension = QtWidgets.QFileDialog.getOpenFileName(self,\
                            'Set data source for %s' % data['name'])
                        if not fname: continue
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
            item = self.import_data(data_type,
                            data['name'],\
                            data_path = item_path,\
                            data = item_data,\
                            **data['kwargs'])
            item.item_settings = item_settings
            item.setCheckState(0, QtCore.Qt.Checked if data['checked']\
                else QtCore.Qt.Unchecked)
            item.set_checked(data['checked_plots'])
        ozf.close()

    def unpack_data_dialog(self):
        if self.OS_settings.general_settings['packeddata'] == 'no':
            self.statusBar().showMessage('Project is not packed')
            return
        #http://stackoverflow.com/a/22363617/1457481
        dirname =\
            QtWidgets.QFileDialog.getExistingDirectory(self, 'Unpack data to')
        if not dirname: return
        packed_paths = {}
        for index in range(self.treeWidget.topLevelItemCount() - 1, -1, -1):
            item = self.treeWidget.topLevelItem(index)
            #item_fname = path.basename(item.data_path)
            item_path = getattr(item, 'data_path', None)
            if item_path is None: continue
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
        populate_properties_dialog(self.settings_dialog_ui, self.OS_settings,\
                    file={'name': self.current_project},\
                    update_data_only=True)

    def get_data_items(self):
        return [self.treeWidget.topLevelItem(index)\
            for index in range(self.treeWidget.topLevelItemCount())]

    def show_settings_dialog(self):
        if not hasattr(self, "settings_dialog"):
            self.settings_dialog = QtWidgets.QDialog(self)
            self.settings_dialog_ui = os_settings_Ui_Dialog()
            self.settings_dialog_ui.setupUi(self.settings_dialog)
            self.settings_dialog.accepted.connect(\
                lambda: parse_properties_dialog(self.settings_dialog_ui,\
                            self.OS_settings, post_hook=(self.set_title,)))
            self.settings_dialog_ui.apply.clicked.connect(\
                lambda: parse_properties_dialog(self.settings_dialog_ui,\
                    self.OS_settings, post_hook=(self.set_title,)))
            #http://stackoverflow.com/a/20021646/1457481
            self.settings_dialog_ui.apply.clicked.connect(\
                    lambda: self.plot_data() if self.actionPlot_on_Apply.isChecked() else None)
            self.settings_dialog_ui.ok_button.clicked.connect(\
                    lambda: self.plot_data() if self.actionPlot_on_Accept.isChecked() else None)
            populate_properties_dialog(self.settings_dialog_ui, self.OS_settings,\
                        file={'name': self.current_project},
                        actions={'unpack':self.unpack_data_dialog})
        else:
            populate_properties_dialog(self.settings_dialog_ui, self.OS_settings,\
                        file={'name': self.current_project},\
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
        #item.setExpanded(expanded)

    def down_dataitem(self):
        n_items = self.treeWidget.topLevelItemCount()
        item, index, expanded = self.remove_dataitem()
        self.treeWidget.insertTopLevelItem(min(n_items - 1, index + 1), item)
        #item.setExpanded(expanded)

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
        #http://www.qtcentre.org/threads/16310-Closing-all-of-the-mainWindow-s-child-dialogs
        if not hasattr(item, "dialog"):
            item.dialog = QtWidgets.QDialog(self)
            item.dialog_ui = item.properties_ui()
            item.dialog_ui.setupUi(item.dialog)
            item.dialog.setWindowTitle(item.text(0))
            item.dialog.accepted.connect(
                lambda: parse_properties_dialog(item.dialog_ui, item))
            item.dialog_ui.apply.clicked.connect(
                lambda: parse_properties_dialog(item.dialog_ui, item))
            #http://stackoverflow.com/a/20021646/1457481
            item.dialog_ui.apply.clicked.connect(\
                    lambda: self.plot_data() if self.actionPlot_on_Apply.isChecked() else None)
            item.dialog_ui.ok_button.clicked.connect(\
                    lambda: self.plot_data() if self.actionPlot_on_Accept.isChecked() else None)
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
            QtWidgets.QFileDialog.getSaveFileName(self,\
                'Export properties of %s' % item.text(0),\
                filter="Openstereo Layer Files (*.os_lyr);;All Files (*.*)")
        if not fname: return
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
        #http://stackoverflow.com/a/24338247/1457481
        except (ValueError, KeyError):
            self.statusBar().showMessage(
                'Failed paste, clipboard contains incompatible properties for %s '
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
            QtWidgets.QFileDialog.getOpenFileName(self,\
                'Import properties for %s' % item.text(0),\
                filter="Openstereo Layer Files (*.os_lyr);;All Files (*.*)")
        if not fname: return
        try:
            with open(fname, "rb") as f:
                item.item_settings = json.load(f)
                self.statusBar().showMessage(
                    'Imported properties to %s from %s' % (item.text(0),
                                                           fname))
        #http://stackoverflow.com/a/24338247/1457481
        except (ValueError, KeyError):
            #maybe show a incompatible data popup
            return
        try:
            populate_properties_dialog(
                item.dialog_ui, item, update_data_only=True)
        except AttributeError:
            return

    def set_source_dataitem(self):
        item = self.get_selected()
        fname, extension = QtWidgets.QFileDialog.getOpenFileName(self,\
            'Set data source for %s' % item.text(0))
        if not fname: return
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
        #menu.addAction("View item table")
        menu.addSeparator()
        copy_props_action = menu.addAction("Copy layer properties")
        paste_props_action = menu.addAction("Paste layer properties")
        export_props_action = menu.addAction(
            "Export layer properties")  #Maybe save and load instead?
        import_props_action = menu.addAction("Import layer properties")
        menu.addSeparator()
        #merge_with_action = menu.addAction("Merge with...")
        #rotate_action = menu.addAction("Rotate...")
        #menu.addSeparator()
        datasource_action = menu.addAction(
            "Set data source"
        )  #should this trigger reimport? They aren't really safe anymore...
        reload_action = menu.addAction("Reload data")
        #menu.addAction("Export data")
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
        if not item: return
        item = item[0]
        while item.parent():
            item = item.parent()
        return item


class ProjectionPlotData(object):
    pass


class RosePlotData(object):
    pass


class PointPlotData(ProjectionPlotData):
    def __init__(self, data, point_settings, legend=False, legend_text=''):
        self.data = data
        self.point_settings = point_settings
        self.legend = legend
        self.legend_text = legend_text


class CirclePlotData(ProjectionPlotData):
    def __init__(self, data, circle_settings, legend=False, legend_text=''):
        self.data = data
        self.circle_settings = circle_settings
        self.legend = legend
        self.legend_text = legend_text


class ContourPlotData(ProjectionPlotData):
    def __init__(self, nodes, count, contour_settings, contour_line_settings,\
                    contour_check_settings, legend=False, n=None):
        self.nodes = nodes
        self.count = count
        self.contour_settings = contour_settings
        self.contour_line_settings = contour_line_settings
        self.contour_check_settings = contour_check_settings
        self.legend = legend
        self.n = n


class PetalsPlotData(RosePlotData):
    def __init__(self, nodes, radii, rose_settings):
        self.nodes = nodes
        self.radii = radii
        self.rose_settings = rose_settings


class KitePlotData(RosePlotData):
    def __init__(self, nodes, radii, full_circle, kite_settings):
        self.nodes = nodes
        self.radii = radii
        self.full_circle = full_circle
        self.kite_settings = kite_settings


class LinesPlotData(RosePlotData):
    def __init__(self, nodes, radii, mean_deviation, lines_settings):
        self.nodes = nodes
        self.radii = radii
        self.mean_deviation = mean_deviation
        self.lines_settings = lines_settings


class RoseMeanPlotData(RosePlotData):
    def __init__(self, theta, confidence, axial, mean_settings):
        self.theta = theta
        self.confidence = confidence
        self.axial = axial
        self.mean_settings = mean_settings


class ClassificationPlotData(object):
    def __init__(self, G, R, kx, ky, point_settings, legend, legend_text):
        self.G, self.R = G, R
        self.kx, self.ky = kx, ky
        self.point_settings = point_settings
        self.legend, self.legend_text = legend, legend_text


class NavigationToolbar(NavigationToolbar2QT):
    # only display the buttons we need
    toolitems = (('Home', 'Reset original view', 'home', 'home'),
                 ('Pan', 'Pan axes with left mouse, zoom with right', 'move',
                  'pan'), ('Zoom', 'Zoom to rectangle', 'zoom_to_rect',
                           'zoom'), ('Save', 'Save the figure', 'filesave',
                                     'save_figure'), (None, None, None, None),
                 (None, None, None, None), )


class PlotPanel(QtWidgets.QVBoxLayout):
    def __init__(self, parent=None):
        super(PlotPanel, self).__init__(parent)

        self.plotFigure = Figure(figsize=(4, 4), facecolor='white')

        self.plot_canvas_frame = QtWidgets.QWidget()
        self.plot_canvas = FigureCanvas(self.plotFigure)
        self.plot_canvas.setParent(self.plot_canvas_frame)
        self.addWidget(self.plot_canvas)
        self.build_toolbar()

    def build_toolbar(self):
        self.plot_toolbar = NavigationToolbar(self.plot_canvas,\
            self.plot_canvas_frame)
        #thanks http://stackoverflow.com/a/33148049/1457481
        for a in self.plot_toolbar.findChildren(QtWidgets.QAction):
            if a.text() == 'Customize':
                self.plot_toolbar.removeAction(a)
                break

        self.addWidget(self.plot_toolbar)

    def plot_data(self, plot_item):
        pass

    def draw_plot(self):
        pass


class StereoPlot(PlotPanel):
    def __init__(self, settings, projection, parent=None):
        super(StereoPlot, self).__init__(parent)

        self.settings = settings
        self._projection = projection

        self.plotaxes = self.plotFigure.add_axes([0.01, 0.01, 0.6, 0.98], \
            clip_on='True',xlim=(-1.1,1.2), ylim=(-1.15,1.15), \
        adjustable='box',autoscale_on='False',label='stereo')
        self.plotaxes.set_aspect(aspect='equal', adjustable=None, anchor='W')
        self.caxes = self.plotFigure.add_axes([0.603, 0.09, 0.025, 0.38], \
            anchor='SW')
        self.caxes.set_axis_off()

        self.plotaxes.format_coord = self.read_plot
        self.caxes.format_coord = lambda x, y: ''

        self.plot_canvas.draw()
        self.legend_items = []
        self.drawn = True

        self.measure_from = None
        self.measure_line = None
        self.measure_gc = None
        self.from_line = None
        self.to_line = None
        self.connect_measure()

    def connect_measure(self):
        'connect to all the events we need'
        self.cidpress = self.plotFigure.canvas.mpl_connect(
            'button_press_event', self.measure_press)
        self.cidrelease = self.plotFigure.canvas.mpl_connect(
            'button_release_event', self.measure_release)
        self.cidmotion = self.plotFigure.canvas.mpl_connect(
            'motion_notify_event', self.measure_motion)
        #http://stackoverflow.com/a/18145817/1457481

    def measure_press(self, event):
        if self.plot_toolbar._active is not None:
            return
        if event.inaxes != self.plotaxes:
            return
        x, y = event.xdata, event.ydata
        if x * x + y * y > 1.:
            return
        self.background = self.plot_canvas.copy_from_bbox(self.plotaxes.bbox)
        self.measure_from = x, y

    def measure_release(self, event):
        self.measure_from = None
        if self.measure_line is not None:
            self.measure_line.remove()
            if self.settings.check_settings['measurelinegc']:
                self.measure_gc.remove()
                self.from_line.remove()
                self.to_line.remove()
            self.measure_line = None
            self.plot_canvas.draw()

    #thanks forever to http://stackoverflow.com/a/8956211/1457481 for basics on blit
    def measure_motion(self, event):
        if self.measure_from is None: return
        if event.inaxes != self.plotaxes: return
        a = np.array(self.projection.inverse(*self.measure_from))
        x, y = event.xdata, event.ydata
        if x * x + y * y > 1: return
        b = np.array(self.projection.inverse(event.xdata, event.ydata))
        theta = acos(np.dot(a, b))
        theta_range = np.arange(0, theta, radians(1))
        sin_range = np.sin(theta_range)
        cos_range = np.cos(theta_range)
        x, y = self.projection.project_data(*great_circle_arc(a, b),\
                                            rotate=False)
        c = np.cross(a, b)
        c /= np.linalg.norm(c)
        c = c if c[2] < 0. else -c
        full_gc = self.projection.project_data(*great_circle_simple(c, pi).T,\
                                            rotate=False)
        c_ = self.projection.project_data(*c, rotate=False)

        from_ = self.projection.project_data(*great_circle_arc(a, c),\
                                            rotate=False)
        to_   = self.projection.project_data(*great_circle_arc(b, c),\
                                            rotate=False)

        if self.projection.settings.check_settings["rotate"]:
            c = self.projection.Ri.dot(c)
        c_sphere = sphere(*c)

        if self.measure_line is None:  #make configurable
            self.measure_line, = self.plotaxes.plot(x, y,\
                **self.settings.mLine_settings)
            self.measure_line.set_clip_path(self.circle)
            if self.settings.check_settings['measurelinegc']:
                self.measure_gc,   = self.plotaxes.plot(*full_gc,\
                    **self.settings.mGC_settings)
                self.from_line,   = self.plotaxes.plot(\
                    *from_, **self.settings.mGC_settings)
                self.to_line,   = self.plotaxes.plot(\
                    *to_, **self.settings.mGC_settings)
                self.measure_gc.set_clip_path(self.circle)
                self.from_line.set_clip_path(self.circle)
                self.to_line.set_clip_path(self.circle)
        else:
            self.measure_line.set_data(x, y)
            if self.settings.check_settings['measurelinegc']:
                self.measure_gc.set_data(*full_gc)
                self.from_line.set_data(*from_)
                self.to_line.set_data(*to_)

        self.plot_toolbar.set_message("Angle: %3.2f\nPlane: %05.1f/%04.1f"\
            % (degrees(theta), c_sphere[0], c_sphere[1]))
        self.plot_canvas.restore_region(self.background)
        if self.settings.check_settings['measurelinegc']:
            self.plotaxes.draw_artist(self.measure_gc)
            self.plotaxes.draw_artist(self.from_line)
            self.plotaxes.draw_artist(self.to_line)
        self.plotaxes.draw_artist(self.measure_line)
        self.plot_canvas.blit(self.plotaxes.bbox)

    def read_plot(self, X, Y):
        return self.projection.read_plot(X, Y)

    @property
    def projection(self):
        return self._projection()

    def project(self, x, y, z, invert_positive=True, ztol=0.):
        return self.projection.project_data(x, y, z,\
            invert_positive=invert_positive, ztol=ztol)

    def plot_data(self, plot_item):
        if self.drawn:
            self.plot_projection_net()
            self.drawn = False
        if isinstance(plot_item, PointPlotData):
            element = self.plot_points(\
                plot_item.data,\
                plot_item.point_settings)
        elif isinstance(plot_item, CirclePlotData):
            element = self.plot_circles(\
                plot_item.data,\
                plot_item.circle_settings)
        elif isinstance(plot_item, ContourPlotData):
            element = self.plot_contours(\
                plot_item.nodes,\
                plot_item.count,\
                plot_item.contour_settings,\
                plot_item.contour_line_settings,\
                plot_item.contour_check_settings,\
                plot_item.n)
        else:
            element = plot_item.plot_data(self)
        if plot_item.legend:
            self.legend_items.append((element, plot_item.legend_text))
        #old = self.plotFigure.get_size_inches()
        #self.plotFigure.set_size_inches((4,4))
        #self.plotFigure.savefig("test.png")
        #self.plotFigure.set_size_inches(old)
        #print self.plotFigure.get_size_inches()

    def draw_plot(self):
        if self.legend_items:
            self.plotaxes.legend(*list(zip(*self.legend_items)), \
                bbox_to_anchor=(0.95, 0.95), loc=2, \
                fontsize=self.settings.general_settings['fontsize'],\
                numpoints=1, fancybox=True).draw_frame(False)
        self.legend_items = []
        if self.drawn:
            self.plot_projection_net()
        self.plot_canvas.draw()
        self.drawn = True

    def plot_projection_net(self):
        ''' create the Stereonet '''
        axes = self.plotaxes
        caxes = self.caxes
        self.circle = PlotStereoNetCircle(axes, caxes,\
                       self.settings.general_settings['fontsize'],\
                       self.settings.check_settings['rotate'])
        self.drawn = False

        axes.text(-0.95,-1.08,\
            "{}\n{} hemisphere".format(self.projection.name,\
                self.settings.general_settings['hemisphere']),
            family='sans-serif',size=self.settings.general_settings['fontsize'], \
            horizontalalignment='left')

        if self.settings.check_settings['rotate'] and\
           self.settings.check_settings['cardinal']:
            self.plot_cardinal()

        axes.set_xlim(-1.1, 1.2)
        axes.set_ylim(-1.15, 1.15)

        self.measure_line = None

    def plot_points(self, points, point_settings):
        X, Y = self.project(*points.T)
        #http://stackoverflow.com/a/11983074/1457481
        element, = self.plotaxes.plot(X, Y, linestyle='', **point_settings)
        return element

    def plot_circles(self, circles, circle_settings):
        projected_circles = \
        [segment for circle in circles for segment in
        clip_lines(np.transpose(self.project(*circle.T, invert_positive=False)))]
        circle_segments = LineCollection(projected_circles, **circle_settings)
        circle_segments.set_clip_path(self.circle)
        self.plotaxes.add_collection(circle_segments, autolim=True)
        return circle_segments

    def plot_cardinal(self):
        cpoints = np.array(((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, -1., 0.0),
                            (-1., 0.0, 0.0)))
        c_projected = np.transpose(
            self.project(*cpoints.T, invert_positive=False))
        c_rotated = self.projection.rotate(*cpoints.T).T
        for i, (point, name) in enumerate(zip(c_rotated, "NESW")):
            if self.settings.general_settings['hemisphere'] == 'Lower' and point[2] > 0\
                or self.settings.general_settings['hemisphere'] == 'Upper' and point[2] < 0:
                continue
            point = self.project(*cpoints[i])
            txt = self.plotaxes.text(point[0],point[1],name, family='sans-serif',\
                      size=self.settings.general_settings['fontsize'],\
                      horizontalalignment='center', verticalalignment='center' )
            txt.set_path_effects([PathEffects.withStroke(\
                linewidth=self.settings.projection_settings['cardinalborder'], foreground='w')])

    def plot_contours(self, nodes, count, contour_settings,
                      contour_line_settings, contour_check_settings, n):
        axes = self.plotaxes
        caxes = self.caxes
        colorbar_ploted = False
        n_contours = contour_settings['ncontours']
        if n is not None:
            count = 100.*count/n\
                if self.settings.check_settings['colorbarpercentage']\
                else count
        if contour_check_settings["minmax"]:
            intervals = np.linspace(count.min(), count.max(), n_contours)
        elif contour_check_settings["zeromax"]:
            intervals = np.linspace(0, count.max(), n_contours)
        else:
            intervals = [float(i) for i in re.split(b"[^-\\d\\.]+",\
                        contour_settings['intervals'])]
        xi = yi = np.linspace(-1.1, 1.1, contour_settings['cresolution'])
        X, Y = self.project(*nodes.T, ztol=.1)

        zi = griddata(X, Y, count, xi, yi, interp='linear')
        if contour_check_settings["fillcontours"]:
            contour_plot = axes.contourf(xi, yi, zi, intervals,\
                        cmap=contour_settings['cmap'],\
                        linestyles=contour_settings['linestyles'],\
                        antialiased=contour_settings['antialiased'])
            #http://matplotlib.1069221.n5.nabble.com/Clipping-a-plot-inside-a-polygon-td41950.html
            for collection in contour_plot.collections:
                collection.set_clip_path(self.circle)
            if self.settings.check_settings['colorbar']:
                cb = colorbar(contour_plot, cax=caxes, format='%3.2f',\
                    spacing='proportional')
                colorbar_ploted = True
        if contour_check_settings["drawover"] or\
                not contour_check_settings["fillcontours"]:
            if contour_check_settings["solidline"]:
                contour_lines_plot = axes.contour(xi, yi, zi, intervals,\
                        colors=contour_line_settings['colors'],\
                        linestyles=contour_settings['linestyles'],\
                        linewidths=contour_line_settings['linewidths'])
            else:
                contour_lines_plot = axes.contour(xi, yi, zi, intervals,\
                        cmap=contour_line_settings['cmap'],\
                        linestyles=contour_settings['linestyles'],\
                        linewidths=contour_line_settings['linewidths'])
                if self.settings.check_settings['colorbar']:
                    colorbar_ploted = True
                    cb = colorbar(contour_lines_plot, cax=caxes,\
                        format='%3.2f', spacing='proportional')
            for collection in contour_lines_plot.collections:
                collection.set_clip_path(self.circle)
        if colorbar_ploted:
            caxes.set_axis_on()
            for t in cb.ax.get_yticklabels():
                t.set_fontsize(9)
            if self.settings.general_settings['colorbar']:
                colorbar_label = self.settings.general_settings['colorbar']
            else:
                colorbar_label = 'Density (%)'\
                    if self.settings.check_settings['colorbarpercentage']\
                    else 'Count'
            caxes.text(0.1,1.07,\
                colorbar_label, family='sans-serif',\
                size=self.settings.general_settings['fontsize'],\
                horizontalalignment='left')


class RosePlot(PlotPanel):
    def __init__(self, settings, parent=None):
        super(RosePlot, self).__init__(parent)

        self.settings = settings

        self.plotaxes = self.plotFigure.add_axes([0.01, 0.01, 0.98, 0.98], \
                        clip_on='True',xlim=(-1.2,1.2), ylim=(-1.15,1.15), \
                        adjustable='box',autoscale_on='False',label='rose')
        self.plotaxes.set_axis_off()
        self.plotaxes.set_aspect(aspect='equal', adjustable=None, anchor='W')

        self.plotaxes.format_coord = self.read_plot

        self.plot_canvas.draw()
        self.plot_list = []
        self.max_frequency = 0.
        self.scale = .1

    def read_plot(self, X, Y):
        return "Az %3.2f (%3.2f%%)" % (degrees(atan2(X, Y)) % 360.,\
                                        100*math.hypot(X, Y)/self.scale)

    def plot_data(self, plot_item):
        if isinstance(plot_item, RosePlotData):
            if hasattr(plot_item, "radii"):
                self.max_frequency = max(self.max_frequency,\
                                    plot_item.radii.max())
            self.plot_list.append(plot_item)
        else:
            plot_item.plot_data(self)

    def draw_plot(self):
        try:
            if self.settings.rose_check_settings["autoscale"] and self.max_frequency > 0.:
                rings_interval = self.settings.rose_settings["ringsperc"]
                self.scale = 100./(rings_interval*\
                                math.ceil(100*self.max_frequency/rings_interval))
            else:
                self.scale = 100. / self.settings.rose_settings["outerperc"]
            self.plot_scale()
            for plot_item in self.plot_list:
                if hasattr(plot_item, "radii"):
                    radii = plot_item.radii * self.scale
                if isinstance(plot_item, PetalsPlotData):
                    self.plot_rose(\
                        plot_item.nodes,\
                        radii,\
                        plot_item.rose_settings)
                elif isinstance(plot_item, KitePlotData):
                    self.plot_kite(\
                        plot_item.nodes,\
                        radii,\
                        plot_item.full_circle,\
                        plot_item.kite_settings)
                elif isinstance(plot_item, LinesPlotData):
                    self.plot_lines(\
                        plot_item.nodes,\
                        radii,\
                        plot_item.mean_deviation,\
                        plot_item.lines_settings)
                elif isinstance(plot_item, RoseMeanPlotData):
                    self.plot_mean(\
                        plot_item.theta,\
                        plot_item.confidence,\
                        plot_item.axial,\
                        plot_item.mean_settings)
        finally:
            self.plot_canvas.draw()
            self.plot_list = []
            self.max_frequency = 0.

    def from_to(self):
        if self.settings.rose_check_settings["360d"]:
            from_, to_ = 0., 360.
        elif self.settings.rose_check_settings["180d"]:
            from_, to_ = -90., 90.
        else:
            from_ = self.settings.rose_settings["from"]
            to_ = self.settings.rose_settings["to"]
        interval = not self.settings.rose_check_settings["360d"]
        return from_, to_, interval

    def plot_scale(self):
        axes = self.plotaxes
        axes.cla()
        axes.set_axis_off()
        from_, to_, interval = self.from_to()

        if self.settings.rose_check_settings["outer"]:
            if interval:
                circ = Wedge((0,0), 1.,\
                    theta2=90-from_, theta1=90-to_,\
                    ec=self.settings.rose_settings["outerc"],\
                    lw=self.settings.rose_settings["outerwidth"],
                    fill=False,\
                    zorder=0)
            else:
                circ = Arc((0,0), 2., 2.,\
                    theta2=90-from_, theta1=90-to_,\
                    ec=self.settings.rose_settings["outerc"],\
                    lw=self.settings.rose_settings["outerwidth"],
                    zorder=0)
            axes.add_patch(circ)
        if self.settings.rose_check_settings["scaletxt"]:
            scaleaz = radians(self.settings.rose_settings["scaleaz"] % 360.)
            axes.text(1.05*sin(scaleaz), 1.05*cos(scaleaz),\
                "{}%".format(100./self.scale),\
                family='sans-serif',\
                size=self.settings.general_settings['fontsize'],\
                verticalalignment='center',\
                horizontalalignment='left' if scaleaz <= pi else 'right')
        if self.settings.rose_check_settings["rings"]:
            rings_interval = self.scale * self.settings.rose_settings[
                "ringsperc"] / 100.
            for i in np.arange(0.0, 1.0, rings_interval):
                ring = Arc((0,0), 2*i, 2*i, theta2=90-from_, theta1=90-to_,\
                    ec=self.settings.rose_settings["ringsc"],\
                    lw=self.settings.rose_settings["ringswidth"],\
                    zorder=0)
                axes.add_patch(ring)

        #http://stackoverflow.com/a/22659261/1457481
        if self.settings.rose_check_settings["diagonals"]:
            offset = self.settings.rose_settings["diagonalsoff"]
            for i in np.arange(0 + offset, 360 + offset,\
                    self.settings.rose_settings["diagonalsang"]):
                if not interval or in_interval(from_, to_, i):
                    diag = Line2D((0, sin(radians(i))), \
                        (0,cos(radians(i))),\
                        c=self.settings.rose_settings["diagonalsc"],\
                        lw=self.settings.rose_settings["diagonalswidth"],\
                        zorder=0)
                    axes.add_line(diag)
        self.plotaxes.set_xlim(-1.3, 1.3)
        self.plotaxes.set_ylim(-1.15, 1.15)

    def plot_mean(self, theta, confidence, axial, mean_settings):
        theta = 90 - theta
        from_, to_, interval = self.from_to()
        if interval and axial:
            from_, to_ = radians(from_), radians(to_)
            f = np.mean(
                ((cos(from_), sin(from_)), (cos(to_), sin(to_))), axis=0)
            p = (cos(radians(theta)), sin(radians(theta)))
            if np.dot(f, p) < 0:
                theta += 180.
        if confidence is not None:
            confcirc = Arc((0,0), width=2.08, height=2.08, \
                angle=0.0, theta1=theta - confidence, theta2=theta + confidence, \
                ec=mean_settings["color"],\
                lw=mean_settings["linewidth"],\
                linestyle=mean_settings["linestyle"],\
                fill=None, zorder=0)
            self.plotaxes.add_patch(confcirc)

        rtheta = radians(theta)
        lin = Line2D((cos(rtheta) + cos(rtheta)*0.11, cos(rtheta) + cos(rtheta)*0.065),\
                     (sin(rtheta) + sin(rtheta)*0.11, sin(rtheta) + sin(rtheta)*0.065),\
                     c=mean_settings["color"],\
                     lw=mean_settings["linewidth"],\
                     linestyle=mean_settings["linestyle"])
        self.plotaxes.add_line(lin)

    def plot_rose(self, nodes, radii, rose_settings):
        patches = []
        n = nodes.shape[0]
        #self.plotaxes.scatter(*nodes.T, c=np.arange(n))

        mid_cn = (nodes[0] + nodes[1]) / 2.
        theta1 = degrees(atan2(mid_cn[1], mid_cn[0]))
        m = degrees(atan2(nodes[0, 1], nodes[0, 0]))
        self.plotaxes.add_patch(Wedge((0, 0),\
            radii[0],
            theta1,
            2*m - theta1,
            **rose_settings))

        for i in range(1, n - 1):
            pn, cn, nn = nodes[i - 1], nodes[i], nodes[(
                i + 1)]  #this is wrong...
            mid_pc = (pn + cn) / 2.
            mid_cn = (cn + nn) / 2.
            theta1 = degrees(atan2(mid_pc[1], mid_pc[0]))
            theta2 = degrees(atan2(mid_cn[1], mid_cn[0]))
            radius = radii[i]
            self.plotaxes.add_patch(Wedge((0, 0),\
                radius, theta2, theta1, **rose_settings))
        mid_pc = (nodes[-2] + nodes[-1]) / 2.
        theta1 = degrees(atan2(mid_pc[1], mid_pc[0]))
        m = degrees(atan2(nodes[-1, 1], nodes[-1, 0]))
        self.plotaxes.add_patch(Wedge((0, 0),\
            radii[-1],
            2*m - theta1,
            theta1,
            **rose_settings))

    def plot_kite(self, nodes, radii, full_circle, kite_settings):
        xy = nodes*radii if full_circle else\
            np.concatenate((nodes*radii, ((0, 0),)), axis=0)
        polygon = Polygon(xy, **kite_settings)
        self.plotaxes.add_patch(polygon)

    def plot_lines(self, nodes, radii, mean_deviation, line_settings):
        patches = []
        mean = radii.mean()
        for node, radius in zip(nodes, radii):
            patches.append((mean*node, radius*node) if mean_deviation else\
                           ((0., 0.), radius*node))
        self.plotaxes.add_collection(LineCollection(patches, **line_settings))


class ClassificationPlot(PlotPanel):
    def __init__(self, settings, parent=None):
        super(ClassificationPlot, self).__init__(parent)
        self.settings = settings

        self.plot_canvas.draw()
        self.plot_list = []
        self.legend_items = []

        self.vollmer = QtWidgets.QRadioButton("Vollmer")
        self.flinn = QtWidgets.QRadioButton("Flinn")
        self.vollmer.setChecked(True)

        separators = [a for a in self.plot_toolbar.findChildren(QtWidgets.QAction)\
                        if a.isSeparator()]
        self.plot_toolbar.insertWidget(separators[-1], self.vollmer)
        self.plot_toolbar.insertWidget(separators[-1], self.flinn)

    def read_vollmer(self, X, Y):
        if X > 0 and X > Y / sqrt3 and X < 1 - Y / sqrt3:
            R = Y / sqrt3_2
            G = X - R / 2.
            P = 1 - R - G
            return "P %.2f, R %.2f, G %.2f" % (P, R, G)
        else:
            return ''

    def read_flinn(self, X, Y):
        if X > 0 and Y > 0:
            return "ln(S2/S3) %.2f, ln(S1/S2) %.2f\nK %.2f, C %.2f" % (X, Y,
                                                                       Y / X,
                                                                       X + Y)
        else:
            return ''

    def plot_data(self, plot_item):
        self.plot_list.append(plot_item)

    def draw_plot(self):
        if self.flinn.isChecked():
            self.draw_Flinn()
        elif self.vollmer.isChecked():
            self.draw_Vollmer()
        if self.legend_items:
            self.plotaxes.legend(*list(zip(*self.legend_items)), \
                bbox_to_anchor=(1.1, 1), loc=2, \
                fontsize=self.settings.general_settings['fontsize'],\
                numpoints=1, fancybox=True)
        self.legend_items = []
        self.plot_list = []
        self.plot_canvas.draw()
        self.drawn = True

    def draw_Vollmer(self):
        self.plotFigure.clf()
        fontsize = self.settings.general_settings['fontsize']
        self.plotaxes = axes = Subplot(self.plotFigure, 111, clip_on='True',\
                xlim=(-0.1,1.05), ylim=(-0.1,1.05), autoscale_on='True',\
                label='vollmer', aspect='equal', adjustable='box', anchor='SW')
        self.plotFigure.add_subplot(axes)
        self.plotaxes.format_coord = self.read_vollmer
        axes.axis['right'].set_visible(False)
        axes.axis['top'].set_visible(False)
        axes.axis['bottom'].set_visible(False)
        axes.axis['left'].set_visible(False)

        tr1 = Line2D((0, 1), (0, 0), c='black')
        axes.add_line(tr1)
        tr2 = Line2D((0, 0.5), (0, sqrt3_2), c='black')
        axes.add_line(tr2)
        tr3 = Line2D((1, 0.5), (0, sqrt3_2), c='black')
        axes.add_line(tr3)

        for i in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            diag = Line2D(
                (i / 2, 1.0 - i / 2), (sqrt3_2 * i, sqrt3_2 * i),
                c='grey',
                lw=0.5)
            axes.add_line(diag)
            diag2 = Line2D((i / 2, i), (sqrt3_2 * i, 0), c='grey', lw=0.5)
            axes.add_line(diag2)
            diag3 = Line2D(
                (i, i + (1 - i) / 2), (0, sqrt3_2 - sqrt3_2 * i),
                c='grey',
                lw=0.5)
            axes.add_line(diag3)

        axes.text(-0.08,-0.05,'Point',family='sans-serif',\
                  size=fontsize,horizontalalignment='left' )
        axes.text(0.97,-0.05,'Girdle',family='sans-serif',\
                  size=fontsize,horizontalalignment='left' )
        axes.text(0.5,0.88,'Random',family='sans-serif',\
                  size=fontsize,horizontalalignment='center' )

        for i in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            axes.text((1-i)/2, sqrt3_2*(1-i)-0.01, '%d' % (i*100), \
                family='sans-serif', size=fontsize, \
                horizontalalignment='right', color='grey', rotation='60')
            axes.text(i, -0.02,'%d' % (i*100), family='sans-serif', \
                size=fontsize, horizontalalignment='center', \
                verticalalignment='top', color='grey')
            axes.text(1.0-i/2, sqrt3_2*i-0.01,'%d' % (i*100) , \
                family='sans-serif', size=fontsize, \
                horizontalalignment='left', color='grey', rotation='-60')

        for plot_item in self.plot_list:
            x = plot_item.G + (plot_item.R / 2.)
            y = plot_item.R * sqrt3_2
            element, = axes.plot(x, y, linestyle='',\
                **plot_item.point_settings)
            if plot_item.legend:
                self.legend_items.append((element, plot_item.legend_text))

        axes.set_xlim(-0.1, 1.05)
        axes.set_ylim(-0.1, 1.05)

    def draw_Flinn(self):
        self.plotFigure.clf()
        fontsize = self.settings.general_settings['fontsize']
        self.plotaxes = axes = Subplot(self.plotFigure, 111, clip_on='True',\
            xlim=(-0.2,7.2), ylim=(-0.2,7.2), autoscale_on='True',\
            xlabel='ln(S2/S3)', ylabel='ln(S1/S2)', label='flinn',\
            aspect='equal', adjustable='box',anchor='W')
        self.plotFigure.add_subplot(axes)
        self.plotaxes.format_coord = self.read_flinn
        axes.axis['right'].set_visible(False)
        axes.axis['top'].set_visible(False)

        for i in [0.2, 0.5, 1.0, 2.0, 5.0]:
            if i <= 1.0:
                diag = Line2D((0, 7.0), (0, (i * 7.0)), c='grey', lw=0.5)
                axes.add_line(diag)
            else:
                diag = Line2D((0, (7.0 / i)), (0, 7.0), c='grey', lw=0.5)
                axes.add_line(diag)

        for j in [2, 4, 6]:
            diag2 = Line2D((0, j), (j, 0), c='grey', lw=0.5)
            axes.add_line(diag2)

        axes.text(6.25,0.05,'K = 0',family='sans-serif',size=fontsize, \
                  horizontalalignment='left',color='grey')
        axes.text(0.15,6.1,'K = inf.',family='sans-serif',size=fontsize, \
                  horizontalalignment='left',color='grey',rotation='vertical')
        axes.text(6.45,6.4,'K = 1',family='sans-serif',size=fontsize, \
                  horizontalalignment='center',color='grey',rotation='45')
        axes.text(3.2,6.4,'K = 2',family='sans-serif',size=fontsize, \
                  horizontalalignment='center',color='grey',rotation='63.5')
        axes.text(1.2,6.4,'K = 5',family='sans-serif',size=fontsize, \
                  horizontalalignment='center',color='grey',rotation='78.7')
        axes.text(6.4,3.1,'K = 0.5',family='sans-serif',size=fontsize, \
                  horizontalalignment='center',color='grey',rotation='26.6')
        axes.text(6.5,1.3,'K = 0.2',family='sans-serif',size=fontsize, \
                  horizontalalignment='center',color='grey',rotation='11.3')
        axes.text(2.6,3.35,'C = 6',family='sans-serif',size=fontsize, \
                  horizontalalignment='center',color='grey',rotation='-45')
        axes.text(1.75,2.2,'C = 4',family='sans-serif',size=fontsize, \
                  horizontalalignment='center',color='grey',rotation='-45')

        axes.text(3.5,3.75,'Girdle/Cluster Transition',family='sans-serif',\
                  size=fontsize, horizontalalignment='left',\
                  verticalalignment='bottom',\
                  color='grey',rotation='45')
        axes.text(6.5,7.2,'CLUSTERS',family='sans-serif',size=fontsize, \
                  horizontalalignment='right',verticalalignment='bottom',\
                  color='grey')
        axes.text(7.2,6.5,'GIRDLES',family='sans-serif',size=fontsize, \
                  horizontalalignment='left',verticalalignment='top',\
                  color='grey',rotation='-90')

        for plot_item in self.plot_list:
            element, = axes.plot(plot_item.kx, plot_item.ky, linestyle='',\
                **plot_item.point_settings)
            if plot_item.legend:
                self.legend_items.append((element, plot_item.legend_text))

        axes.set_xlim(0.0, 7.2)
        axes.set_ylim(0.0, 7.2)


def color_button_factory(button, button_name):
    def color_button_dialog():
        col = QtWidgets.QColorDialog.getColor()
        if col.isValid():
            button.setStyleSheet("QWidget#%s { background-color: %s }" %
                                 (button_name, col.name()))
            #button.palette().color(QtWidgets.QPalette.Background).name()

    return color_button_dialog


props_re = re.compile("([^_]+)_(color_)?(.+)_([^_]+)")


def populate_properties_dialog(properties_ui,
                               item,
                               update_data_only=False,
                               **kwargs):
    dialog_widgets = vars(properties_ui)
    for widget_name in dialog_widgets:
        parsed_widget = props_re.match(widget_name)
        if parsed_widget is None: continue
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
            #http://stackoverflow.com/a/22798753/1457481
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
        if parsed_widget is None: continue
        widget = dialog_widgets[widget_name]
        category, is_color, widget_item, prop_name = parsed_widget.groups()
        if category == "prop":
            item_props = item.get_item_props(widget_item)
            if is_color:
                item_props[prop_name] = widget.palette().color(
                    QtGui.QPalette.Background).name()
            #http://stackoverflow.com/a/6062987/1457481
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
            f()  #could pass self to post_hook?


#Really need to remake this
def PlotStereoNetCircle(axes, caxes, fontsize, rotate):
    '''Function to create the stereonet circle'''
    caxes.cla()
    caxes.set_axis_off()
    axes.cla()
    axes.set_axis_off()
    if not rotate:
        axes.text(0.01,1.025,'N', family='sans-serif', size=fontsize, \
                  horizontalalignment='center' )
        x_cross = [0, 1, 0, -1, 0]
        y_cross = [0, 0, 1, 0, -1]
        axes.plot(x_cross, y_cross, 'k+', markersize=8, label='_nolegend_')
    circ = Circle( (0,0), radius=1, edgecolor='black', facecolor='none', \
        clip_box='None',label='_nolegend_')
    axes.add_patch(circ)
    return circ
