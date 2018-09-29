from math import pi, radians, degrees, acos

# http://treyhunner.com/2016/02/how-to-merge-dictionaries-in-python/
try:
    from collections import ChainMap
except ImportError:
    from itertools import chain

    def ChainMap(*args):
        return dict(chain(*map(lambda d: d.items(), reversed(args))))


import numpy as np
from PyQt5 import QtWidgets, QtCore

from openstereo.ui.plane_properties_ui import Ui_Dialog as plane_Ui_Dialog
from openstereo.ui.line_properties_ui import Ui_Dialog as line_Ui_Dialog
from openstereo.ui.smallcircle_properties_ui import (
    Ui_Dialog as smallcircle_Ui_Dialog,
)
from openstereo.ui.circular_properties_ui import (
    Ui_Dialog as circular_Ui_Dialog,
)

from openstereo.os_math import small_circle, great_circle
from openstereo.os_auttitude import load, DirectionalData
from openstereo import os_auttitude as autti
from openstereo.data_import import get_data, split_attitude
from openstereo.plot_data import (
    PointPlotData,
    CirclePlotData,
    ContourPlotData,
    PetalsPlotData,
    KitePlotData,
    LinesPlotData,
    RoseMeanPlotData,
    ClassificationPlotData,
)

import auttitude as au
from auttitude.applications import stress


class DataItem(QtWidgets.QTreeWidgetItem):
    plot_item_name = {}
    default_checked = []
    item_order = {}

    def __init__(self, name, parent, item_id=None):
        super(DataItem, self).__init__(parent)
        self.id = item_id
        self.check_items = {}
        self.plot_item_name.update(
            dict((v, k) for k, v in self.plot_item_name.items())
        )
        self.build_items()
        self.build_configuration()
        self.set_checked(self.default_checked)
        self.setText(0, name)
        self.setCheckState(0, QtCore.Qt.Checked)
        self.setFlags(
            QtCore.Qt.ItemIsUserCheckable
            | QtCore.Qt.ItemIsEnabled
            | QtCore.Qt.ItemIsSelectable
            | QtCore.Qt.ItemIsDragEnabled
        )
        self.setExpanded(True)

    def build_configuration(self):
        pass

    @property
    def items(self):
        items = [
            item_name[5:]
            for item_name in dir(self)
            if item_name.startswith("plot_")
            and callable(getattr(self, item_name))
        ]
        items.sort(key=lambda x: self.item_order.get(x, 999))
        return items

    @property
    def hidden_items(self):
        for item_name in dir(self):
            if item_name.startswith("_plot_") and callable(
                getattr(self, item_name)
            ):
                yield item_name

    def get_item(self, item_name):
        return getattr(self, "plot_" + item_name.replace(" ", "_"))

    def get_item_props(self, item_name):
        return getattr(self, item_name.replace(" ", "_") + "_settings")

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
            if isinstance(settings, dict) and hasattr(self, name):
                settings = ChainMap({}, settings, getattr(self, name))
            setattr(self, name, settings)

    # @property
    # def checked_plots(self):
    #     return chain.from_iterable(
    #         (self.get_item(item_name)() for item_name in self.items
    #          if self.check_items[
    #               self.plot_item_name.get(item_name, item_name)]
    #          .checkState(0)))

    @property
    def checked_plots(self):
        for item_name in self.items:
            if self.check_items[
                self.plot_item_name.get(item_name, item_name)
            ].checkState(0):
                for plot_item in self.get_item(item_name)():
                    yield plot_item
        for item_name in self.hidden_items:
            for plot_item in getattr(self, item_name)():
                yield plot_item

    def get_checked_status(self):
        return {
            self.plot_item_name.get(item_name, item_name): bool(
                self.check_items[
                    self.plot_item_name.get(item_name, item_name)
                ].checkState(0)
            )
            for item_name in self.items
        }

    def build_items(self):
        for item_name in self.items:
            self.add_item(
                self.plot_item_name.get(item_name, item_name).replace("_", " ")
            )

    def add_item(self, item_name):
        item_widget = QtWidgets.QTreeWidgetItem(self)
        item_widget.setText(0, item_name)
        item_widget.setCheckState(0, QtCore.Qt.Unchecked)
        item_widget.setFlags(
            QtCore.Qt.ItemIsUserCheckable
            | QtCore.Qt.ItemIsEnabled
            | QtCore.Qt.ItemIsSelectable
        )
        self.check_items[item_name] = item_widget

    def set_checked(self, item_list):
        if type(item_list) == list:
            for item_name in item_list:
                self.check_items[item_name].setCheckState(0, QtCore.Qt.Checked)
        else:
            for item_name in item_list:
                self.check_items[item_name].setCheckState(
                    0,
                    QtCore.Qt.Checked
                    if item_list[item_name]
                    else QtCore.Qt.Unchecked,
                )

    def set_root(self, root):
        pass


class CircularData(DataItem):
    data_type = "circular_data"
    default_checked = ["Rose"]
    properties_ui = circular_Ui_Dialog
    auttitude_class = np.array

    def __init__(self, name, data_path, data, parent, item_id, **kwargs):
        self.data_path = data_path
        self.kwargs = kwargs
        self.auttitude_data = (
            data if isinstance(data, DirectionalData) else load(data, **kwargs)
        )  # TODO: change this to new autti
        self.au_object = self.auttitude_class(self.auttitude_data.data)
        super(CircularData, self).__init__(name, parent, item_id)

    def build_configuration(self):
        self.rose_check_settings = {
            "standard": True,
            "continuous": False,
            "weightmunro": True,
            "dd": True,
            "dir": False,
            "diraxial": False,
            "weightcolumn": False,
            "mean": True,
            "confidence": True,
            "petals": True,
            "petalsfill": True,
            "petalsoutline": True,
            "kite": False,
            "kitefill": True,
            "kiteoutline": True,
            "lines": False,
            "meandeviation": True,
            "360d": True,
            "180d": False,
            "interval": False,
        }
        self.rose_settings = {
            "binwidth": 10.0,
            "offset": 5.0,
            "aperture": 11.0,
            "weightmunro": 0.9,
            "spacing": 2.0,
            "offsetcont": 0.0,
            "weightcolumn": 1,
            "confidence": 95.0,
            "intervalfrom": 0.0,
            "intervalto": 180.0,
            "180half": "N",
        }
        self.rose_mean_settings = {
            "linestyle": "-",
            "color": "#000000",
            "linewidth": 1,
        }
        self.petals_settings = {
            "facecolor": "#4D4D4D",
            "edgecolor": "#000000",
            "linewidth": 1,
        }
        self.kite_settings = {
            "facecolor": "#4D4D4D",
            "edgecolor": "#000000",
            "linewidth": 1,
        }
        self.lines_settings = {
            "linestyle": ":",
            "color": "#000000",
            "linewidth": 1,
        }

    def plot_Rose(self):
        plot_data = []
        grid = self.auttitude_data.cgrid
        full_circle = False
        if self.rose_check_settings["360d"]:
            from_, to_ = 0.0, 2 * pi
            full_circle = True
        elif self.rose_check_settings["180d"]:
            if self.rose_settings["180half"] == "N":
                from_, to_ = -pi / 2, pi / 2
            else:
                from_, to_ = pi / 2, -pi / 2
        else:
            from_ = radians(self.rose_settings["intervalfrom"])
            to_ = radians(self.rose_settings["intervalto"])
        if self.rose_check_settings["weightcolumn"]:
            data_weight = np.array(
                [
                    float(line[self.rose_settings["weightcolumn"]])
                    for line in self.auttitude_data.input_data
                ]
            )
        else:
            data_weight = None
        if self.rose_check_settings["standard"]:
            nodes = grid.build_grid(
                self.rose_settings["binwidth"],
                self.rose_settings["offset"],
                from_,
                to_,
            )
            radii = self.auttitude_data.grid_rose(
                aperture=self.rose_settings["binwidth"],
                axial=self.rose_check_settings["diraxial"],
                direction=self.rose_check_settings["dir"],
                nodes=nodes,
                data_weight=data_weight,
            )
        else:
            nodes = grid.build_grid(
                self.rose_settings["spacing"],
                self.rose_settings["offsetcont"],
                from_,
                to_,
            )
            if self.rose_check_settings["weightmunro"]:
                radii = self.auttitude_data.grid_munro(
                    weight=self.rose_settings["weightmunro"],
                    aperture=self.rose_settings["aperture"],
                    axial=self.rose_check_settings["diraxial"],
                    spacing=self.rose_settings["spacing"],
                    offset=self.rose_settings["offsetcont"],
                    direction=self.rose_check_settings["dir"],
                    nodes=nodes,
                    data_weight=data_weight,
                )
            else:
                radii = self.auttitude_data.grid_rose(
                    aperture=self.rose_settings["aperture"],
                    axial=self.rose_check_settings["diraxial"],
                    spacing=self.rose_settings["spacing"],
                    offset=self.rose_settings["offsetcont"],
                    direction=self.rose_check_settings["dir"],
                    nodes=nodes,
                    data_weight=data_weight,
                )
        if self.rose_check_settings["petals"]:
            petal_settings = {
                "facecolor": self.petals_settings["facecolor"]
                if self.rose_check_settings["petalsfill"]
                else "none",
                "edgecolor": self.petals_settings["edgecolor"]
                if self.rose_check_settings["petalsoutline"]
                else "none",
                "linewidth": self.petals_settings["linewidth"],
            }
            plot_data.append(PetalsPlotData(nodes, radii, petal_settings))
        elif self.rose_check_settings["kite"]:
            kite_settings = {
                "facecolor": self.kite_settings["facecolor"]
                if self.rose_check_settings["kitefill"]
                else "none",
                "edgecolor": self.kite_settings["edgecolor"]
                if self.rose_check_settings["kiteoutline"]
                else "none",
                "linewidth": self.kite_settings["linewidth"],
            }
            plot_data.append(
                KitePlotData(nodes, radii, full_circle, kite_settings)
            )
        elif self.rose_check_settings["lines"]:
            plot_data.append(
                LinesPlotData(
                    nodes,
                    radii,
                    self.rose_check_settings["meandeviation"],
                    self.lines_settings,
                )
            )
        if self.rose_check_settings["mean"]:
            theta = (
                self.auttitude_data.circular_mean_direction_axial
                if self.rose_check_settings["diraxial"]
                else self.auttitude_data.circular_mean_direction
            )
            confidence = (
                self.auttitude_data.estimate_circular_confidence(
                    self.rose_check_settings["diraxial"],
                    self.rose_settings["confidence"] / 100.0,
                )[1]
                if self.rose_check_settings["confidence"]
                else None
            )
            if self.rose_check_settings["dir"]:
                theta -= 90.0
            plot_data.append(
                RoseMeanPlotData(
                    theta,
                    confidence,
                    self.rose_check_settings["diraxial"],
                    self.rose_mean_settings,
                )
            )
        return plot_data


class AttitudeData(CircularData):  # TODO: change name to VectorData
    data_type = "attitude_data"
    auttitude_class = au.VectorSet

    def build_configuration(self):
        super(AttitudeData, self).build_configuration()
        self.point_settings = {"marker": "o", "c": "#000000", "ms": 3.0}
        self.meanpoint_settings = {"marker": "*", "c": "#000000", "ms": 12.0}
        self.scaxis_settings = {"marker": "o", "c": "#000000", "ms": 3.0}
        self.sccirc_settings = {
            "linewidths": 1.0,
            "colors": "#000000",
            "linestyles": "-",
        }
        self.sccalc_settings = {"eiv": 0}
        self.contour_settings = {
            "cmap": "Reds",
            "linestyles": "-",
            "antialiased": True,
            "intervals": "",
            "ncontours": 10,
            "cresolution": 250,
        }
        self.contour_line_settings = {
            "cmap": "jet",
            "colors": "#4D4D4D",
            "linewidths": 0.50,
        }
        self.contour_calc_settings = {
            "spacing": 2.5,
            "K": 100,
            "scperc": 1.0,
            "scangle": 10.0,
        }
        self.contour_check_settings = {
            "solidline": False,
            "gradientline": True,
            "fillcontours": True,
            "drawover": True,
            "minmax": True,
            "zeromax": False,
            "customintervals": False,
            "fisher": True,
            "scangle": False,
            "scperc": False,
            "autocount": False,
            "robinjowett": True,
            "digglefisher": False,
        }
        self.check_settings = {
            "v1point": True,
            "v1GC": True,
            "v2point": True,
            "v2GC": True,
            "v3point": True,
            "v3GC": True,
            "meanpoint": False,
            "meanpointeiv": True,
            "scaxis": False,
            "sccirc": False,
            "concentratesc": False,
        }
        self.v1point_settings = {"marker": "*", "c": "#00FF00", "ms": 12.0}
        self.v2point_settings = {"marker": "*", "c": "#FF0000", "ms": 12.0}
        self.v3point_settings = {"marker": "*", "c": "#0000FF", "ms": 12.0}
        self.v1GC_settings = {
            "linewidths": 1.0,
            "colors": "#00FF00",
            "linestyles": "-",
        }
        self.v2GC_settings = {
            "linewidths": 1.0,
            "colors": "#FF0000",
            "linestyles": "-",
        }
        self.v3GC_settings = {
            "linewidths": 1.0,
            "colors": "#0000FF",
            "linestyles": "-",
        }

        self.checklegend_settings = {
            "point": True,
            "GC": True,
            "meanpoint": True,
            "scaxis": True,
            "sccirc": True,
            "v1point": True,
            "v1GC": True,
            "v2point": True,
            "v2GC": True,
            "v3point": True,
            "v3GC": True,
        }
        self.legend_settings = {
            "point": "",
            "GC": "",
            "meanpoint": "",
            "scaxis": "",
            "sccirc": "",
            "v1point": "",
            "v1GC": "",
            "v2point": "",
            "v2GC": "",
            "v3point": "",
            "v3GC": "",
        }

    def reload_data(self):
        data = get_data(self.data_path, self.auttitude_data.kwargs)
        self.auttitude_data = load(data, **self.auttitude_data.kwargs)

    def reload_data_from_internal(self):
        # data = get_data(self.data_path, self.auttitude_data.kwargs)
        self.auttitude_data = load(
            self.auttitude_data.input_data, **self.auttitude_data.kwargs
        )

    def plot_Points(self):
        if self.legend_settings["point"]:
            try:  # TODO: add count to others?
                legend_text = self.legend_settings["point"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["point"]
        else:
            legend_text = "{} ({} {})".format(
                self.text(0),
                self.auttitude_data.n,
                self.plot_item_name.get("Points", "Points").lower(),
            )
        return (
            PointPlotData(
                self.auttitude_data.data,
                self.point_settings,
                self.checklegend_settings["point"],
                legend_text,
            ),
        )

    def _plot_SC(self):
        plot_items = []
        if self.check_settings["scaxis"] or self.check_settings["sccirc"]:
            data = self.auttitude_data.data
            projection = self.treeWidget().window().projection()
            if self.check_settings["concentratesc"]:
                eiv = self.auttitude_data.eigenvectors[
                    self.sccalc_settings["eiv"]
                ]
                data = data * np.where(data.dot(eiv) > 0, 1, -1)[:, None]
            elif projection.settings.check_settings["rotate"]:
                data = projection.rotate(*data.T).T
                data = data * np.where(data[:, 2] > 0, -1, 1)[:, None]
            axis, alpha = autti.small_circle_axis(data)
            if self.check_settings["scaxis"]:
                if self.legend_settings["scaxis"]:
                    try:
                        legend_text = self.legend_settings["scaxis"].format(
                            data=self.auttitude_data
                        )
                    except:
                        legend_text = self.legend_settings["scaxis"]
                else:
                    legend_text = "{} ({} Axis)".format(
                        self.text(0),
                        self.plot_item_name.get("SC", "Small Circle"),
                    )
                plot_items.append(
                    PointPlotData(
                        axis,
                        self.scaxis_settings,
                        self.checklegend_settings["scaxis"],
                        legend_text,
                    )
                )
            if self.check_settings["sccirc"]:
                if self.legend_settings["sccirc"]:
                    try:
                        legend_text = self.legend_settings["sccirc"].format(
                            data=self.auttitude_data
                        )
                    except:
                        legend_text = self.legend_settings["sccirc"]
                else:
                    legend_text = "{} ({})".format(
                        self.text(0),
                        self.plot_item_name.get("SC", "Small Circle"),
                    )
                plot_items.append(
                    CirclePlotData(
                        small_circle(axis, alpha),
                        self.sccirc_settings,
                        self.checklegend_settings["sccirc"],
                        legend_text,
                    )
                )
        return plot_items

    def _plot_Mean(self):
        if self.check_settings["meanpoint"]:
            if self.legend_settings["meanpoint"]:
                try:
                    legend_text = self.legend_settings["meanpoint"].format(
                        data=self.auttitude_data
                    )
                except:
                    legend_text = self.legend_settings["meanpoint"]
            else:
                legend_text = "{} ({})".format(
                    self.text(0), self.plot_item_name.get("meanpoint", "Mean")
                )
            return (
                PointPlotData(
                    self.auttitude_data.mean_vector
                    if not self.check_settings["meanpointeiv"]
                    else self.auttitude_data.concentrated_mean_vector,
                    self.meanpoint_settings,
                    self.checklegend_settings["meanpoint"],
                    legend_text,
                ),
            )
        else:
            return []

    def plot_Eigenvectors(self):
        plot_data = []
        for i, eiv in enumerate(("v1point", "v2point", "v3point")):
            if self.check_settings[eiv]:
                if self.legend_settings[eiv]:
                    try:
                        legend_text = self.legend_settings[eiv].format(
                            data=self.auttitude_data
                        )
                    except:
                        legend_text = self.legend_settings[eiv]
                else:
                    legend_text = "{} (EV {})".format(self.text(0), i + 1)
                plot_data.append(
                    PointPlotData(
                        self.auttitude_data.eigenvectors[i],
                        self.get_item_props(eiv),
                        self.checklegend_settings[eiv],
                        legend_text,
                    )
                )
        for i, eiv in enumerate(("v1GC", "v2GC", "v3GC")):
            if self.check_settings[eiv]:
                if self.legend_settings[eiv]:
                    try:
                        legend_text = self.legend_settings[eiv].format(
                            data=self.auttitude_data
                        )
                    except:
                        legend_text = self.legend_settings[eiv]
                else:
                    legend_text = "{} (EV {})".format(self.text(0), i + 1)
                plot_data.append(
                    CirclePlotData(
                        (great_circle(self.auttitude_data.eigenvectors[i]),),
                        self.get_item_props(eiv),
                        self.checklegend_settings[eiv],
                        legend_text,
                    )
                )
        return plot_data

    def plot_Contours(self):
        grid = self.auttitude_data.grid
        grid.change_spacing(self.contour_calc_settings["spacing"])
        nodes = self.auttitude_data.grid_nodes
        if self.contour_check_settings["fisher"]:
            if self.contour_check_settings["autocount"]:
                if self.contour_check_settings["robinjowett"]:
                    k = None
                else:
                    try:
                        k = grid.optimize_k(self.auttitude_data.data)
                    except ImportError:
                        QtWidgets.QMessageBox.warning(
                            self.parent(),
                            "Scipy not Found",
                            "Scipy is needed for Diggle & Fisher method. Defaulting to Robin & Jowett.",
                        )  # noqa: E501
                        k = None
            else:
                k = self.contour_calc_settings["K"]
            count = self.auttitude_data.grid_fisher(k)
        else:
            if self.contour_check_settings["autocount"]:
                if self.contour_check_settings["robinjowett"]:
                    theta = None
                else:
                    try:
                        theta = degrees(
                            acos(
                                1.0
                                - 1.0
                                / grid.optimize_k(self.auttitude_data.data)
                            )
                        )
                    except ImportError:
                        QtWidgets.QMessageBox.warning(
                            self.parent(),
                            "Scipy not Found",
                            "Scipy is needed for Diggle & Fisher method. Defaulting to Robin & Jowett.",
                        )  # noqa: E501
                        theta = None
            else:
                theta = (
                    self.contour_calc_settings["scangle"]
                    if self.contour_check_settings["scangle"]
                    else degrees(
                        0.141536 * self.contour_calc_settings["scperc"]
                    )
                )
            count = self.auttitude_data.grid_kamb(theta)
        return (
            ContourPlotData(
                nodes,
                count,
                self.contour_settings,
                self.contour_line_settings,
                self.contour_check_settings,
                n=self.auttitude_data.n,
            ),
        )

    def _plot_Classification(self):
        if self.legend_settings["point"]:
            try:
                legend_text = self.legend_settings["point"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["point"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("Points", "Points")
            )
        return (
            ClassificationPlotData(
                self.auttitude_data.vollmer_G,
                self.auttitude_data.vollmer_R,
                self.auttitude_data.woodcock_Kx,
                self.auttitude_data.woodcock_Ky,
                self.point_settings,
                self.checklegend_settings["point"],
                legend_text,
            ),
        )


class PlaneData(AttitudeData):
    data_type = "plane_data"
    plot_item_name = {"Points": "Poles", "GC": "Great Circles"}
    item_order = {"Points": 0, "GC": 1, "Eigenvectors": 2, "Contours": 3}
    default_checked = ["Poles", "Rose"]
    properties_ui = plane_Ui_Dialog
    auttitude_class = au.PlaneSet

    def build_configuration(self):
        super(PlaneData, self).build_configuration()
        self.GC_settings = {
            "linewidths": 0.8,
            "colors": "#4D4D4D",
            "linestyles": "-",
        }

    def plot_GC(self):
        circles = [great_circle(point) for point in self.auttitude_data.data]
        if self.legend_settings["GC"]:
            try:
                legend_text = self.legend_settings["GC"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["GC"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("GC", "Great Circles")
            )
        return (
            CirclePlotData(
                circles,
                self.GC_settings,
                self.checklegend_settings["GC"],
                legend_text,
            ),
        )


class LineData(AttitudeData):
    data_type = "line_data"
    plot_item_name = {"Points": "Lines"}
    item_order = {"Points": 0, "Contours": 3}
    default_checked = ["Lines", "Rose"]
    properties_ui = line_Ui_Dialog
    auttitude_class = au.LineSet


class SmallCircleData(DataItem):
    data_type = "smallcircle_data"
    plot_item_name = {"SC": "Small Circles"}
    default_checked = ["Axes", "Small Circles"]
    properties_ui = smallcircle_Ui_Dialog
    auttitude_class = au.VectorSet

    def __init__(self, name, data_path, data, parent, item_id, **kwargs):
        self.data_path = data_path
        self.kwargs = kwargs  # FIXME: get update statistics from kwargs
        self.auttitude_data = (
            data if isinstance(data, DirectionalData) else load(data, **kwargs)
        )
        self.au_object = self.auttitude_class(self.auttitude_data.data)
        self.alpha_column = kwargs["alpha_column"]
        self.alpha = [
            float(line[self.alpha_column])
            for line in self.auttitude_data.input_data
        ]
        super(SmallCircleData, self).__init__(name, parent, item_id)

    def build_configuration(self):
        super(SmallCircleData, self).build_configuration()
        self.scaxis_settings = {"marker": "o", "c": "#000000", "ms": 3.0}
        self.sccirc_settings = {
            "linewidths": 1.0,
            "colors": "#000000",
            "linestyles": "-",
        }

        self.checklegend_settings = {"scaxis": True, "sccirc": True}
        self.legend_settings = {"scaxis": "", "sccirc": ""}


# Kim Wilde
class FaultData(DataItem):
    data_type = "fault_data"
    plot_item_name = {"SC": "Small Circles"}
    default_checked = ["Dihedra", "Michael"]
    properties_ui = smallcircle_Ui_Dialog

    def __init__(self, name, data, parent, item_id, **kwargs):
        self.kwargs = kwargs
        if data is not None:
            self.plane_item, self.line_item = data
        else:
            self.plane_item, self.line_item = None, None
        super().__init__(name, parent, item_id)

    def build_configuration(self):
        super().build_configuration()
        self.scaxis_settings = {"marker": "o", "c": "#000000", "ms": 3.0}
        self.sccirc_settings = {
            "linewidths": 1.0,
            "colors": "#000000",
            "linestyles": "-",
        }

        self.contour_check_settings = {
            "solidline": False,
            "gradientline": True,
            "fillcontours": True,
            "drawover": True,
            "minmax": True,
            "zeromax": False,
            "customintervals": False,
            "fisher": True,
            "scangle": False,
            "scperc": False,
            "autocount": False,
            "robinjowett": True,
            "digglefisher": False,
        }

        self.contour_settings = {
            "cmap": "jet",
            "linestyles": "-",
            "antialiased": True,
            "intervals": "",
            "ncontours": 20,
            "cresolution": 250,
        }

        self.contour_line_settings = {
            "cmap": "jet",
            "colors": "#4D4D4D",
            "linewidths": 0.50,
        }
        self.contour_calc_settings = {
            "spacing": 2.5,
            "K": 100,
            "scperc": 1.0,
            "scangle": 10.0,
        }

        self.m1point_settings = {"marker": "*", "c": "#FF0000", "ms": 12.0}
        self.m2point_settings = {"marker": "*", "c": "#00FF00", "ms": 12.0}
        self.m3point_settings = {"marker": "*", "c": "#00FFFF", "ms": 12.0}

        self.checklegend_settings = {"scaxis": True, "sccirc": True}
        self.legend_settings = {"scaxis": "", "sccirc": ""}

        self.data_settings = {}

    def set_root(self, root):
        self.root = root

    def ensure_data(self):  # TODO: Should this be a mixin?
        if self.plane_item is None:
            self.plane_item = self.root.get_data_item_by_id(
                self.data_settings["plane_id"]
            )
        else:
            self.data_settings["plane_id"] = self.plane_item.id
        if self.line_item is None:
            self.line_item = self.root.get_data_item_by_id(
                self.data_settings["line_id"]
            )
        else:
            self.data_settings["line_id"] = self.line_item.id

    def plot_Dihedra(self):
        self.ensure_data()

        dihedra = stress.angelier_graphical(
            self.plane_item.au_object, self.line_item.au_object
        )

        return (
            ContourPlotData(
                au.DEFAULT_GRID.grid,
                dihedra,
                self.contour_settings,
                self.contour_line_settings,
                self.contour_check_settings,
                n=len(self.plane_item.au_object),
            ),
        )

    def plot_Michael(self):
        self.ensure_data()
        plot_data = []
        stress_matrix, residuals = stress.michael(
            self.plane_item.au_object, self.line_item.au_object
        )
        stress_directions, (s1, s2, s3) = stress.principal_stresses(
            stress_matrix
        )

        for i, miv in enumerate(("m1point", "m2point", "m3point")):
            legend_text = "{} ({})".format(
                self.text(0), ["compressive", "intermediate", "distensive"][i]
            )
            plot_data.append(
                PointPlotData(
                    stress_directions[i],
                    self.get_item_props(miv),
                    True,
                    legend_text,
                )
            )
        return plot_data


# Hairspray & Alexander Hamilton
class SinglePlane(DataItem):
    data_type = "singleplane_data"
    plot_item_name = {"GC": "Great Circle"}
    item_order = {"Pole": 0, "GC": 1}
    default_checked = ["Pole", "Great Circle"]
    properties_ui = smallcircle_Ui_Dialog

    def __init__(self, name, parent, item_id, data="", strike=False, **kwargs):
        super().__init__(name, parent, item_id)
        self.data_settings["attitude"] = data
        self.data_settings["strike"] = strike

    def build_configuration(self):
        super().build_configuration()
        self.scaxis_settings = {"marker": "o", "c": "#000000", "ms": 3.0}
        self.sccirc_settings = {
            "linewidths": 1.0,
            "colors": "#000000",
            "linestyles": "-",
        }

        self.checklegend_settings = {"scaxis": True, "sccirc": True}
        self.legend_settings = {"scaxis": "", "sccirc": ""}

        self.data_settings = {}

    def reload_data(self):
        pass

    def change_attitude(self, data, strike=False):
        self.data_settings["attitude"] = data
        self.data_settings["strike"] = strike

    def get_attitude_Plane(self):
        attitude = split_attitude(self.data_settings["attitude"])
        translated_attitude = au.translate_attitude(
            attitude[0], attitude[1], strike=self.data_settings["strike"]
        )
        return au.Plane.from_attitude(
            *translated_attitude, strike=self.data_settings["strike"]
        )

    def plot_Pole(self):
        if self.legend_settings["scaxis"]:
            try:
                legend_text = self.legend_settings["scaxis"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["scaxis"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("scaxis", "scaxis")
            )
        plane = self.get_attitude_Plane()
        return (
            PointPlotData(
                plane,
                self.scaxis_settings,
                self.checklegend_settings["scaxis"],
                legend_text,
            ),
        )

    def plot_GC(self):
        plot_items = []
        if self.legend_settings["sccirc"]:
            try:
                legend_text = self.legend_settings["sccirc"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["sccirc"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("SC", "Small Circle")
            )
        circle = self.get_attitude_Plane().get_great_circle()
        plot_items.append(
            CirclePlotData(
                circle,
                self.sccirc_settings,
                self.checklegend_settings["sccirc"],
                legend_text,
            )
        )
        return plot_items


class SingleLine(DataItem):
    data_type = "singleline_data"
    properties_ui = smallcircle_Ui_Dialog

    def __init__(self, name, parent, item_id, data="", strike=False, **kwargs):
        super().__init__(name, parent, item_id)
        self.data_settings["attitude"] = data
        self.data_settings["strike"] = strike

    def build_configuration(self):
        super().build_configuration()
        self.scaxis_settings = {"marker": "o", "c": "#000000", "ms": 3.0}
        self.sccirc_settings = {
            "linewidths": 1.0,
            "colors": "#000000",
            "linestyles": "-",
        }

        self.checklegend_settings = {"scaxis": True, "sccirc": True}
        self.legend_settings = {"scaxis": "", "sccirc": ""}

        self.data_settings = {}

    def reload_data(self):
        pass

    def change_attitude(self, data, strike=False):
        self.data_settings["attitude"] = data
        self.data_settings["strike"] = strike

    def get_attitude_Line(self):
        attitude = split_attitude(self.data_settings["attitude"])
        translated_attitude = au.translate_attitude(
            attitude[0], attitude[1], strike=self.data_settings["strike"]
        )
        return au.Line.from_attitude(
            *translated_attitude, strike=self.data_settings["strike"]
        )

    def _plot_Point(self):
        if self.legend_settings["scaxis"]:
            try:
                legend_text = self.legend_settings["scaxis"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["scaxis"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("scaxis", "scaxis")
            )
        line = self.get_attitude_Line()
        return (
            PointPlotData(
                line,
                self.scaxis_settings,
                self.checklegend_settings["scaxis"],
                legend_text,
            ),
        )


class SingleSmallCircle(DataItem):
    data_type = "singlesc_data"
    plot_item_name = {"SC": "Small Circles"}
    default_checked = ["Axis", "Small Circles"]
    properties_ui = smallcircle_Ui_Dialog

    def __init__(self, name, parent, item_id, data="", strike=False, **kwargs):
        super().__init__(name, parent, item_id)
        self.data_settings["attitude"] = data
        self.data_settings["strike"] = strike

    def build_configuration(self):
        super().build_configuration()
        self.scaxis_settings = {"marker": "o", "c": "#000000", "ms": 3.0}
        self.sccirc_settings = {
            "linewidths": 1.0,
            "colors": "#000000",
            "linestyles": "-",
        }

        self.checklegend_settings = {"scaxis": True, "sccirc": True}
        self.legend_settings = {"scaxis": "", "sccirc": ""}

        self.data_settings = {}

    def reload_data(self):
        pass

    def change_attitude(self, data, strike=False):
        self.data_settings["attitude"] = data
        self.data_settings["strike"] = strike

    def get_attitude_LineAlpha(self):
        attitude = split_attitude(self.data_settings["attitude"])
        alpha = radians(float(attitude[2]))
        translated_attitude = au.translate_attitude(
            attitude[0], attitude[1], strike=self.data_settings["strike"]
        )
        return (
            au.Line.from_attitude(
                *translated_attitude, strike=self.data_settings["strike"]
            ),
            alpha,
        )

    def plot_Axis(self):
        if self.legend_settings["scaxis"]:
            try:
                legend_text = self.legend_settings["scaxis"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["scaxis"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("scaxis", "scaxis")
            )
        axis, alpha = self.get_attitude_LineAlpha()
        return (
            PointPlotData(
                axis,
                self.scaxis_settings,
                self.checklegend_settings["scaxis"],
                legend_text,
            ),
        )

    def plot_SC(self):
        plot_items = []
        if self.legend_settings["sccirc"]:
            try:
                legend_text = self.legend_settings["sccirc"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["sccirc"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("SC", "Small Circle")
            )
        axis, alpha = self.get_attitude_LineAlpha()
        circles = axis.get_small_circle(alpha=alpha)
        plot_items.append(
            CirclePlotData(
                circles,
                self.sccirc_settings,
                self.checklegend_settings["sccirc"],
                legend_text,
            )
        )
        return plot_items


class Slope(DataItem):
    data_type = "slope_data"
    plot_item_name = {
        "GC": "Great Circle",
        "Daylight": "Daylight Envelope",
        "Lateral": "Lateral Limits",
        "PlaneFriction": "Plane Friction Cone",
        "PoleFriction": "Pole Friction Cone",
    }
    item_order = {"Pole": 0, "GC": 1}
    default_checked = ["Great Circle", "Daylight Envelope", "Lateral Limits"]
    properties_ui = smallcircle_Ui_Dialog

    def __init__(self, name, parent, item_id, data="", strike=False, **kwargs):
        super().__init__(name, parent, item_id)
        self.data_settings["attitude"] = data
        self.data_settings["strike"] = strike

    def build_configuration(self):
        super().build_configuration()
        self.scaxis_settings = {"marker": "o", "c": "#000000", "ms": 3.0}
        self.sccirc_settings = {
            "linewidths": 1.0,
            "colors": "#000000",
            "linestyles": "-",
        }

        self.checklegend_settings = {"scaxis": True, "sccirc": True}
        self.legend_settings = {"scaxis": "", "sccirc": ""}

        self.data_settings = {"friction_angle": 30.0}

    def reload_data(self):
        pass

    def change_attitude(self, data, strike=False):
        self.data_settings["attitude"] = data
        self.data_settings["strike"] = strike

    def get_attitude_Plane(self):
        attitude = split_attitude(self.data_settings["attitude"])
        translated_attitude = au.translate_attitude(
            attitude[0], attitude[1], strike=self.data_settings["strike"]
        )
        return au.Plane.from_attitude(
            *translated_attitude, strike=self.data_settings["strike"]
        )

    def plot_Pole(self):
        if self.legend_settings["scaxis"]:
            try:
                legend_text = self.legend_settings["scaxis"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["scaxis"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("scaxis", "scaxis")
            )
        plane = self.get_attitude_Plane()
        return (
            PointPlotData(
                plane,
                self.scaxis_settings,
                self.checklegend_settings["scaxis"],
                legend_text,
            ),
        )

    def plot_GC(self):
        plot_items = []
        if self.legend_settings["sccirc"]:
            try:
                legend_text = self.legend_settings["sccirc"].format(
                    data=self.auttitude_data
                )
            except:
                legend_text = self.legend_settings["sccirc"]
        else:
            legend_text = "{} ({})".format(
                self.text(0), self.plot_item_name.get("SC", "Small Circle")
            )
        circle = self.get_attitude_Plane().get_great_circle()
        plot_items.append(
            CirclePlotData(
                circle,
                self.sccirc_settings,
                self.checklegend_settings["sccirc"],
                legend_text,
            )
        )
        return plot_items

    def plot_Daylight(self):
        circle, = self.get_attitude_Plane().get_great_circle(step=radians(0.5))
        daylight_envelope = np.array([p.dip_vector for p in circle])
        # if self.legend_settings['GC']:
        #     try:
        #         legend_text = \
        #             self.legend_settings['GC'].format(
        #                 data=self.auttitude_data)
        #     except:
        #         legend_text = self.legend_settings['GC']
        # else:
        legend_text = "{} ({})".format(
            self.text(0),
            self.plot_item_name.get("Daylight", "Daylight Envelope"),
        )
        return (
            CirclePlotData(
                (daylight_envelope,),
                self.sccirc_settings,
                self.checklegend_settings["sccirc"],
                legend_text,
            ),
        )

    def plot_Lateral(self):
        direction = self.get_attitude_Plane().direction_vector
        lateral_limits = direction.get_small_circle(alpha=radians(70.0))
        legend_text = "{} ({})".format(
            self.text(0), self.plot_item_name.get("Lateral", "Lateral Limits")
        )
        return (
            CirclePlotData(
                lateral_limits,
                self.sccirc_settings,
                self.checklegend_settings["sccirc"],
                legend_text,
            ),
        )

    def plot_PoleFriction(self):
        vertical = au.Line([0.0, 0.0, 1.0])
        alpha = radians(self.data_settings["friction_angle"])
        sc = vertical.get_small_circle(alpha)
        legend_text = "{} ({})".format(
            self.text(0),
            self.plot_item_name.get("PoleFriction", "Pole Friction Cone"),
        )
        return (
            CirclePlotData(
                sc,
                self.sccirc_settings,
                self.checklegend_settings["sccirc"],
                legend_text,
            ),
        )

    def plot_PlaneFriction(self):
        vertical = au.Line([0.0, 0.0, 1.0])
        alpha = radians(90.0 - self.data_settings["friction_angle"])
        sc = vertical.get_small_circle(alpha)
        legend_text = "{} ({})".format(
            self.text(0),
            self.plot_item_name.get("PlaneFriction", "Plane Friction Cone"),
        )
        return (
            CirclePlotData(
                sc,
                self.sccirc_settings,
                self.checklegend_settings["sccirc"],
                legend_text,
            ),
        )

