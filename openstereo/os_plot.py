import math
from math import pi, sin, cos, acos, atan2, degrees, radians, sqrt
import re

from PyQt5 import QtWidgets
from matplotlib.pyplot import colorbar, imread, get_cmap
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT,
)

from matplotlib.patches import Polygon, Wedge, Circle, Arc, FancyArrowPatch
from matplotlib.collections import (
    PatchCollection,
    PolyCollection,
    LineCollection,
)
from matplotlib.mlab import griddata
import matplotlib.patheffects as PathEffects
from matplotlib.font_manager import FontProperties
from mpl_toolkits.axes_grid.axislines import Subplot

from matplotlib.lines import Line2D

import numpy as np

from openstereo.plot_data import (
    ProjectionPlotData,
    RosePlotData,
    PointPlotData,
    CirclePlotData,
    PolygonPlotData,
    ArrowPlotData,
    ContourPlotData,
    PetalsPlotData,
    KitePlotData,
    LinesPlotData,
    RoseMeanPlotData,
    ClassificationPlotData,
)

from openstereo.os_math import (
    great_circle_arc,
    great_circle_simple,
    sphere,
    clip_lines,
    in_interval,
    au_clip_lines,
    au_join_segments,
    au_close_polygon,
    extents_from_center,
)

import auttitude as au

sqrt3_2 = sqrt(3.0) / 2.0
sqrt3 = sqrt(3.0)


class NavigationToolbar(NavigationToolbar2QT):
    # only display the buttons we need
    toolitems = (
        ("Home", "Reset original view", "home", "home"),
        ("Pan", "Pan axes with left mouse, zoom with right", "move", "pan"),
        ("Zoom", "Zoom to rectangle", "zoom_to_rect", "zoom"),
        ("Save", "Save the figure", "filesave", "save_figure"),
        (None, None, None, None),
        (None, None, None, None),
    )


class PlotPanel(QtWidgets.QVBoxLayout):
    def __init__(self, parent=None):
        super(PlotPanel, self).__init__(parent)

        self.plotFigure = Figure(figsize=(4, 4), facecolor="white")

        self.plot_canvas_frame = QtWidgets.QWidget()
        self.plot_canvas = FigureCanvas(self.plotFigure)
        self.plot_canvas.setParent(self.plot_canvas_frame)
        self.addWidget(self.plot_canvas)
        self.build_toolbar()

    def build_toolbar(self):
        self.plot_toolbar = NavigationToolbar(
            self.plot_canvas, self.plot_canvas_frame
        )
        # thanks http://stackoverflow.com/a/33148049/1457481
        for a in self.plot_toolbar.findChildren(QtWidgets.QAction):
            if a.text() == "Customize":
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

        self.plotaxes = self.plotFigure.add_axes(
            [0.01, 0.01, 0.6, 0.98],
            clip_on="True",
            xlim=(-1.1, 1.2),
            ylim=(-1.15, 1.15),
            adjustable="box",
            autoscale_on="False",
            label="stereo",
        )
        self.plotaxes.set_aspect(aspect="equal", adjustable=None, anchor="W")
        self.caxes = self.plotFigure.add_axes(
            [0.603, 0.09, 0.025, 0.38], anchor="SW"
        )
        self.caxes.set_axis_off()

        self.plotaxes.format_coord = self.read_plot
        self.caxes.format_coord = lambda x, y: ""

        self.plot_canvas.draw()
        self.legend_items = []
        self.drawn = True

        self.measure_from = None
        self.measure_line = None
        self.measure_gc = None
        self.measure_sc = None
        self.button_pressed = None
        self.from_line = None
        self.to_line = None
        self.last_center = None
        self.last_theta = None
        self.last_from_measure = None
        self.last_to_measure = None
        self.connect_measure()

        # experimental
        self.point_elements = []
        self.circle_elements = []
        self.drag_rotate_mode = False
        self.current_rotation = np.eye(3)
        self.last_rotation = np.eye(3)
        self.last_rotation_I = np.eye(3)

    def connect_measure(self):
        "connect to all the events we need"
        self.cidpress = self.plotFigure.canvas.mpl_connect(
            "button_press_event", self.measure_press
        )
        self.cidrelease = self.plotFigure.canvas.mpl_connect(
            "button_release_event", self.measure_release
        )
        self.cidmotion = self.plotFigure.canvas.mpl_connect(
            "motion_notify_event", self.measure_motion
        )
        # http://stackoverflow.com/a/18145817/1457481

    def measure_press(self, event):
        if self.plot_toolbar._active is not None:
            return
        if event.inaxes != self.plotaxes:
            return
        x, y = event.xdata, event.ydata
        if x * x + y * y > 1.0:
            return
        self.background = self.plot_canvas.copy_from_bbox(self.plotaxes.bbox)
        self.button_pressed = event.button
        # print(self.button_pressed)
        self.measure_from = x, y
        a = au.Vector(self.projection.inverse(*self.measure_from))
        self.last_from_measure = a
        self.last_to_measure = None
        self.last_center = None
        self.last_theta = None

    def measure_release(self, event):
        self.measure_from = None
        try:
            if self.measure_sc is not None:
                self.measure_sc.remove()
        except ValueError:
            pass
        try:
            if self.measure_line is not None:
                self.measure_line.remove()
        except ValueError:
            pass
        try:
            if self.settings.check_settings["measurelinegc"]:
                for line in [self.measure_gc, self.from_line, self.to_line]:
                    if line is not None:
                        line.remove()
                # self.measure_gc.remove()
                # self.from_line.remove()
                # self.to_line.remove()
        except ValueError:
            pass
        self.measure_line = None
        self.last_rotation = self.current_rotation
        self.last_rotation_I = np.linalg.inv(self.current_rotation)
        self.current_rotation = np.eye(3)
        self.plot_canvas.draw()

    # thanks forever to http://stackoverflow.com/a/8956211/1457481 for basics on blit
    def measure_motion(self, event):
        if self.measure_from is None:
            return
        if event.inaxes != self.plotaxes:
            return
        a = self.last_from_measure
        x, y = event.xdata, event.ydata
        if x * x + y * y > 1:
            return
        b = au.Vector(self.projection.inverse(event.xdata, event.ydata))
        self.last_to_measure = b
        theta = acos(np.dot(a, b))
        theta_range = np.arange(0, theta, radians(1))
        sin_range = np.sin(theta_range)
        cos_range = np.cos(theta_range)
        x, y = self.projection.project_data(
            *great_circle_arc(a, b), rotate=False
        )
        c = np.cross(a, b)
        c /= np.linalg.norm(c)

        au_c = au.Vector(c)

        c = c if c[2] < 0.0 else -c
        full_gc = self.projection.project_data(
            *great_circle_simple(c, pi).T, rotate=False
        )
        if self.button_pressed == 3:
            self.last_center = a
            self.last_theta = theta
            full_sc = self.projection.project_data(
                *a.get_small_circle(theta)[0].T,
                rotate=False,
                invert_positive=False
            )
        else:
            ab = (a + b) / 2
            ab /= ab.length
            self.last_center = ab
            self.last_theta = theta / 2
            full_sc = self.projection.project_data(
                *ab.get_small_circle(theta / 2)[0].T,
                rotate=False,
                invert_positive=False
            )

        c_ = self.projection.project_data(*c, rotate=False)

        from_ = self.projection.project_data(
            *great_circle_arc(a, c), rotate=False
        )
        to_ = self.projection.project_data(
            *great_circle_arc(b, c), rotate=False
        )

        if self.projection.settings.check_settings["rotate"]:
            c = self.projection.Ri.dot(c)
            au_c = au_c.dot(self.last_rotation.T).dot(self.projection.Ri.T)
        c_sphere = sphere(*c)

        if self.drag_rotate_mode:
            rotation_matrix = self.last_rotation.dot(
                au_c.get_rotation_matrix(-theta)
            )
            self.current_rotation = rotation_matrix
            for point, element in self.point_elements:
                Xp, Yp = self.project(*(point.dot(rotation_matrix)).T)
                element.set_data(Xp, Yp)

            for circles, element in self.circle_elements:
                projected_circles = [
                    np.transpose(
                        self.project(
                            *(circle.dot(rotation_matrix)).T,
                            invert_positive=False
                        )
                    )
                    for circle in circles
                ]
                element.set_segments(projected_circles)

        if self.measure_line is None:  # make configurable
            self.measure_line, = self.plotaxes.plot(
                x, y, **self.settings.mLine_settings
            )
            self.measure_line.set_clip_path(self.circle)
            if self.button_pressed in (2, 3):
                self.measure_sc, = self.plotaxes.plot(
                    *full_sc, **self.settings.mLine_settings
                )
                self.measure_sc.set_clip_path(self.circle)
            if self.settings.check_settings["measurelinegc"]:
                self.measure_gc, = self.plotaxes.plot(
                    *full_gc, **self.settings.mGC_settings
                )
                self.from_line, = self.plotaxes.plot(
                    *from_, **self.settings.mGC_settings
                )
                self.to_line, = self.plotaxes.plot(
                    *to_, **self.settings.mGC_settings
                )
                self.measure_gc.set_clip_path(self.circle)
                self.from_line.set_clip_path(self.circle)
                self.to_line.set_clip_path(self.circle)
        else:
            self.measure_line.set_data(x, y)
            if self.button_pressed in (2, 3):
                self.measure_sc.set_data(*full_sc)
            if self.settings.check_settings["measurelinegc"]:
                self.measure_gc.set_data(*full_gc)
                self.from_line.set_data(*from_)
                self.to_line.set_data(*to_)

        if self.button_pressed in (2, 3):
            self.plot_toolbar.set_message(
                "Angle: {:3.2f}\nAxis: {:05.1f}/{:04.1f}".format(
                    degrees(self.last_theta), *self.last_center.attitude
                )
            )
        else:
            self.plot_toolbar.set_message(
                "Angle: {:3.2f}\nLine: {:05.1f}/{:04.1f} Plane: {:05.1f}/{:04.1f}".format(
                    degrees(theta),
                    (c_sphere[0] - 180) % 360,
                    90 - c_sphere[1],
                    c_sphere[0],
                    c_sphere[1],
                )
            )
        self.plot_canvas.restore_region(self.background)
        if self.settings.check_settings["measurelinegc"]:
            self.plotaxes.draw_artist(self.measure_gc)
            if self.button_pressed in (2, 3):
                self.plotaxes.draw_artist(self.measure_sc)
            else:
                self.plotaxes.draw_artist(self.from_line)
                self.plotaxes.draw_artist(self.to_line)
        self.plotaxes.draw_artist(self.measure_line)
        # experimental
        if self.drag_rotate_mode:
            for point, element in self.point_elements:
                self.plotaxes.draw_artist(element)
            for circles, element in self.circle_elements:
                self.plotaxes.draw_artist(element)
        self.plot_canvas.blit(self.plotaxes.bbox)

    def read_plot(self, X, Y):
        return self.projection.read_plot(X, Y)

    @property
    def projection(self):
        return self._projection()

    def project(self, x, y, z, invert_positive=True, ztol=0.0):
        return self.projection.project_data(
            x, y, z, invert_positive=invert_positive, ztol=ztol
        )

    def plot_data(self, plot_item):
        if self.drawn:
            self.plot_projection_net()
            self.drawn = False
        if isinstance(plot_item, PointPlotData):
            element = self.plot_points(
                plot_item.data, plot_item.point_settings
            )
            self.point_elements.append((plot_item.data, element))
        elif isinstance(plot_item, CirclePlotData):
            element = self.plot_circles(
                plot_item.data, plot_item.circle_settings
            )
            self.circle_elements.append((plot_item.data, element))
        elif isinstance(plot_item, ContourPlotData):
            element = self.plot_contours(
                plot_item.nodes,
                plot_item.count,
                plot_item.contour_settings,
                plot_item.contour_line_settings,
                plot_item.contour_check_settings,
                plot_item.n,
            )
        elif isinstance(plot_item, ArrowPlotData):
            element = self.plot_arrow(
                plot_item.data[0],
                plot_item.data[1],
                plot_item.arrow_settings,
                has_sense=plot_item.sense,
            )
        elif isinstance(plot_item, PolygonPlotData):
            element = self.plot_polygons(
                plot_item.data, plot_item.polygon_settings
            )
        else:
            element = plot_item.plot_data(self)  # somewhat visitor pattern
        if plot_item.legend:
            self.legend_items.append((element, plot_item.legend_text))
        # old = self.plotFigure.get_size_inches()
        # self.plotFigure.set_size_inches((4,4))
        # self.plotFigure.savefig("test.png")
        # self.plotFigure.set_size_inches(old)
        # print self.plotFigure.get_size_inches()

    def clear_plot_element_data(self):
        self.point_elements = []
        self.circle_elements = []
        self.last_rotation = np.eye(3)
        self.last_rotation_I = self.last_rotation

    def draw_plot(self):
        if self.legend_items:
            L = self.plotaxes.legend(
                *list(zip(*self.legend_items)),
                bbox_to_anchor=(0.95, 0.95),
                loc=2,
                fontsize=self.settings.general_settings["fontsize"],
                numpoints=1,
                fancybox=True
            )  # .draw_frame(False)
            L.draw_frame(False)
            # L.set_draggable(True)
        self.legend_items = []
        if self.drawn:
            self.plot_projection_net()
        # self.plot_image()
        self.plot_canvas.draw()
        self.drawn = True

    def plot_projection_net(self):
        """ create the Stereonet """
        axes = self.plotaxes
        caxes = self.caxes
        self.circle = PlotStereoNetCircle(
            axes,
            caxes,
            self.settings.general_settings["fontsize"],
            self.settings.check_settings["rotate"],
        )
        self.drawn = False

        axes.text(
            -0.95,
            -1.08,
            "{}\n{} hemisphere".format(
                self.projection.name,
                self.settings.general_settings["hemisphere"],
            ),
            family="sans-serif",
            size=self.settings.general_settings["fontsize"],
            horizontalalignment="left",
        )

        if (
            self.settings.check_settings["rotate"]
            and self.settings.check_settings["cardinal"]
        ):
            self.plot_cardinal()

        axes.set_xlim(-1.1, 1.2)
        axes.set_ylim(-1.15, 1.15)

        self.measure_line = None

    def plot_points(self, points, point_settings):
        X, Y = self.project(*points.T)
        # http://stackoverflow.com/a/11983074/1457481
        element, = self.plotaxes.plot(X, Y, linestyle="", **point_settings)
        return element

    def plot_circles(self, circles, circle_settings):
        projected_circles = [
            segment
            for circle in circles
            for segment in clip_lines(
                np.transpose(self.project(*circle.T, invert_positive=False))
            )
        ]
        circle_segments = LineCollection(projected_circles, **circle_settings)
        circle_segments.set_clip_path(self.circle)
        self.plotaxes.add_collection(circle_segments, autolim=True)
        return circle_segments

    def plot_polygons(self, polygons, polygon_settings):
        projected_polygons = [
            au_close_polygon(
                np.transpose(
                    self.project(
                        *np.transpose(segment),
                        invert_positive=False  # , rotate=False
                    )
                )
            )
            for circle in polygons
            for segment in au_join_segments(
                au_clip_lines(np.dot(circle, self.projection.R.T))
            )
        ]
        polygon_segments = PolyCollection(
            projected_polygons, **polygon_settings
        )
        polygon_segments.set_clip_path(self.circle)
        self.plotaxes.add_collection(polygon_segments, autolim=True)
        return polygon_segments

    def plot_arrow(self, planes, lines, arrow_settings, has_sense):
        for plane, line, sense in zip(planes, lines, has_sense):
            if plane[-1] > 0:
                plane = -plane
            arrow_to = (
                cos(arrow_settings["arrowsize"] / 2.0) * plane
                + sin(arrow_settings["arrowsize"] / 2.0) * line
            )
            arrow_from = (
                cos(-arrow_settings["arrowsize"] / 2.0) * plane
                + sin(-arrow_settings["arrowsize"] / 2.0) * line
            )
            if arrow_settings.get("footwall", False):
                arrow_from, arrow_to = arrow_to, arrow_from
            X, Y = self.project(
                *np.transpose((arrow_from, arrow_to)), invert_positive=False
            )
            if not sense:
                self.plotaxes.add_line(
                    Line2D(
                        X,
                        Y,
                        c=arrow_settings["arrowcolor"],
                        label="_nolegend_",
                        lw=arrow_settings["lw"],
                        ls=arrow_settings["ls"],
                    )
                )
            else:
                a, b = (X[0], Y[0]), (X[1], Y[1])
                self.plotaxes.add_patch(
                    FancyArrowPatch(
                        a,
                        b,
                        shrinkA=0.0,
                        shrinkB=0.0,
                        arrowstyle="->,head_length=2.5,head_width=1",
                        connectionstyle="arc3,rad=0.0",
                        mutation_scale=2.0,
                        ec=arrow_settings["arrowcolor"],
                        lw=arrow_settings["lw"],
                        ls=arrow_settings["ls"],
                    )
                )
        return Line2D(
            X,
            Y,
            c=arrow_settings["arrowcolor"],
            label="_nolegend_",
            lw=arrow_settings["lw"],
            ls=arrow_settings["ls"],
        )

    # def plot_image(self):
    #     imfile = imread("C:/Users/arthur.endlein/Documents/projects/repos/os/A9 manual.JPG")
    #     extent = extents_from_center(453, 451, 160, 0, 0, 159, 824, 780)
    #     im = self.plotaxes.imshow(imfile, cmap=get_cmap('gray'), extent=extent)
    #     im.set_clip_path(self.circle)

    def plot_cardinal(self):
        cpoints = np.array(
            (
                (0.0, 1.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, -1.0, 0.0),
                (-1.0, 0.0, 0.0),
            )
        )
        c_projected = np.transpose(
            self.project(*cpoints.T, invert_positive=False)
        )
        c_rotated = self.projection.rotate(*cpoints.T).T
        for i, (point, name) in enumerate(zip(c_rotated, "NESW")):
            if (
                self.settings.general_settings["hemisphere"] == "Lower"
                and point[2] > 0
                or self.settings.general_settings["hemisphere"] == "Upper"
                and point[2] < 0
            ):
                continue
            point = self.project(*cpoints[i])
            txt = self.plotaxes.text(
                point[0],
                point[1],
                name,
                family="sans-serif",
                size=self.settings.general_settings["fontsize"],
                horizontalalignment="center",
                verticalalignment="center",
            )
            txt.set_path_effects(
                [
                    PathEffects.withStroke(
                        linewidth=self.settings.projection_settings[
                            "cardinalborder"
                        ],
                        foreground="w",
                    )
                ]
            )

    def plot_contours(
        self,
        nodes,
        count,
        contour_settings,
        contour_line_settings,
        contour_check_settings,
        n,
    ):
        axes = self.plotaxes
        caxes = self.caxes
        colorbar_ploted = False
        n_contours = contour_settings["ncontours"]
        if n is not None:
            count = (
                100.0 * count / n
                if self.settings.check_settings["colorbarpercentage"]
                else count
            )
        if contour_check_settings["minmax"]:
            intervals = np.linspace(count.min(), count.max(), n_contours)
        elif contour_check_settings["zeromax"]:
            intervals = np.linspace(0, count.max(), n_contours)
        else:
            intervals = [
                float(i)
                for i in re.split(
                    b"[^-\\d\\.]+", contour_settings["intervals"]
                )
            ]
        xi = yi = np.linspace(-1.1, 1.1, contour_settings["cresolution"])
        X, Y = self.project(*nodes.T, ztol=0.1)

        zi = griddata(X, Y, count, xi, yi, interp="linear")
        if contour_check_settings["fillcontours"]:
            contour_plot = axes.contourf(
                xi,
                yi,
                zi,
                intervals,
                cmap=contour_settings["cmap"],
                linestyles=contour_settings["linestyles"],
                antialiased=contour_settings["antialiased"],
            )
            # http://matplotlib.1069221.n5.nabble.com/Clipping-a-plot-inside-a-polygon-td41950.html
            for collection in contour_plot.collections:
                collection.set_clip_path(self.circle)
            if self.settings.check_settings["colorbar"]:
                cb = colorbar(
                    contour_plot,
                    cax=caxes,
                    format="%3.2f",
                    spacing="proportional",
                )
                colorbar_ploted = True
        if (
            contour_check_settings["drawover"]
            or not contour_check_settings["fillcontours"]
        ):
            if contour_check_settings["solidline"]:
                contour_lines_plot = axes.contour(
                    xi,
                    yi,
                    zi,
                    intervals,
                    colors=contour_line_settings["colors"],
                    linestyles=contour_settings["linestyles"],
                    linewidths=contour_line_settings["linewidths"],
                )
            else:
                contour_lines_plot = axes.contour(
                    xi,
                    yi,
                    zi,
                    intervals,
                    cmap=contour_line_settings["cmap"],
                    linestyles=contour_settings["linestyles"],
                    linewidths=contour_line_settings["linewidths"],
                )
                if self.settings.check_settings["colorbar"]:
                    colorbar_ploted = True
                    cb = colorbar(
                        contour_lines_plot,
                        cax=caxes,
                        format="%3.2f",
                        spacing="proportional",
                    )
            for collection in contour_lines_plot.collections:
                collection.set_clip_path(self.circle)
        if colorbar_ploted:
            caxes.set_axis_on()
            for t in cb.ax.get_yticklabels():
                t.set_fontsize(9)
            if self.settings.general_settings["colorbar"]:
                colorbar_label = self.settings.general_settings["colorbar"]
            else:
                colorbar_label = (
                    "Density (%)"
                    if self.settings.check_settings["colorbarpercentage"]
                    else "Count"
                )
            caxes.text(
                0.1,
                1.07,
                colorbar_label,
                family="sans-serif",
                size=self.settings.general_settings["fontsize"],
                horizontalalignment="left",
            )


class RosePlot(PlotPanel):
    def __init__(self, settings, parent=None):
        super(RosePlot, self).__init__(parent)

        self.settings = settings

        self.plotaxes = self.plotFigure.add_axes(
            [0.01, 0.01, 0.98, 0.98],
            clip_on="True",
            xlim=(-1.2, 1.2),
            ylim=(-1.15, 1.15),
            adjustable="box",
            autoscale_on="False",
            label="rose",
        )
        self.plotaxes.set_axis_off()
        self.plotaxes.set_aspect(aspect="equal", adjustable=None, anchor="W")

        self.plotaxes.format_coord = self.read_plot

        self.plot_canvas.draw()
        self.plot_list = []
        self.max_frequency = 0.0
        self.scale = 0.1

    def read_plot(self, X, Y):
        return "Az %3.2f (%3.2f%%)" % (
            degrees(atan2(X, Y)) % 360.0,
            100 * math.hypot(X, Y) / self.scale,
        )

    def plot_data(self, plot_item):
        if isinstance(plot_item, RosePlotData):
            if hasattr(plot_item, "radii"):
                self.max_frequency = max(
                    self.max_frequency, plot_item.radii.max()
                )
            self.plot_list.append(plot_item)
        else:
            plot_item.plot_data(self)

    def draw_plot(self):
        try:
            if (
                self.settings.rose_check_settings["autoscale"]
                and self.max_frequency > 0.0
            ):
                rings_interval = self.settings.rose_settings["ringsperc"]
                self.scale = 100.0 / (
                    rings_interval
                    * math.ceil(100 * self.max_frequency / rings_interval)
                )
            else:
                self.scale = 100.0 / self.settings.rose_settings["outerperc"]
            self.plot_scale()
            for plot_item in self.plot_list:
                if hasattr(plot_item, "radii"):
                    radii = plot_item.radii * self.scale
                if isinstance(plot_item, PetalsPlotData):
                    self.plot_rose(
                        plot_item.nodes, radii, plot_item.rose_settings
                    )
                elif isinstance(plot_item, KitePlotData):
                    self.plot_kite(
                        plot_item.nodes,
                        radii,
                        plot_item.full_circle,
                        plot_item.kite_settings,
                    )
                elif isinstance(plot_item, LinesPlotData):
                    self.plot_lines(
                        plot_item.nodes,
                        radii,
                        plot_item.mean_deviation,
                        plot_item.lines_settings,
                    )
                elif isinstance(plot_item, RoseMeanPlotData):
                    self.plot_mean(
                        plot_item.theta,
                        plot_item.confidence,
                        plot_item.axial,
                        plot_item.mean_settings,
                    )
        finally:
            self.plot_canvas.draw()
            self.plot_list = []
            self.max_frequency = 0.0

    def from_to(self):
        if self.settings.rose_check_settings["360d"]:
            from_, to_ = 0.0, 360.0
        elif self.settings.rose_check_settings["180d"]:
            from_, to_ = -90.0, 90.0
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
                circ = Wedge(
                    (0, 0),
                    1.0,
                    theta2=90 - from_,
                    theta1=90 - to_,
                    ec=self.settings.rose_settings["outerc"],
                    lw=self.settings.rose_settings["outerwidth"],
                    fill=False,
                    zorder=0,
                )
            else:
                circ = Arc(
                    (0, 0),
                    2.0,
                    2.0,
                    theta2=360.0,
                    theta1=0.0,
                    ec=self.settings.rose_settings["outerc"],
                    lw=self.settings.rose_settings["outerwidth"],
                    zorder=0,
                )
            axes.add_patch(circ)
        if self.settings.rose_check_settings["scaletxt"]:
            scaleaz = radians(self.settings.rose_settings["scaleaz"] % 360.0)
            axes.text(
                1.05 * sin(scaleaz),
                1.05 * cos(scaleaz),
                "{}%".format(100.0 / self.scale),
                family="sans-serif",
                size=self.settings.general_settings["fontsize"],
                verticalalignment="center",
                horizontalalignment="left" if scaleaz <= pi else "right",
            )
        if self.settings.rose_check_settings["rings"]:
            rings_interval = (
                self.scale * self.settings.rose_settings["ringsperc"] / 100.0
            )
            for i in np.arange(rings_interval, 1.0, rings_interval):
                ring = Arc(
                    (0, 0),
                    2 * i,
                    2 * i,
                    theta2=90.0 - from_,
                    theta1=90.0 - to_,
                    ec=self.settings.rose_settings["ringsc"],
                    lw=self.settings.rose_settings["ringswidth"],
                    zorder=0,
                )
                axes.add_patch(ring)

        # http://stackoverflow.com/a/22659261/1457481
        if self.settings.rose_check_settings["diagonals"]:
            offset = self.settings.rose_settings["diagonalsoff"]
            for i in np.arange(
                0 + offset,
                360 + offset,
                self.settings.rose_settings["diagonalsang"],
            ):
                if not interval or in_interval(from_, to_, i):
                    diag = Line2D(
                        (0, sin(radians(i))),
                        (0, cos(radians(i))),
                        c=self.settings.rose_settings["diagonalsc"],
                        lw=self.settings.rose_settings["diagonalswidth"],
                        zorder=0,
                    )
                    axes.add_line(diag)
        self.plotaxes.set_xlim(-1.3, 1.3)
        self.plotaxes.set_ylim(-1.15, 1.15)

    def plot_mean(self, theta, confidence, axial, mean_settings):
        theta = 90 - theta
        from_, to_, interval = self.from_to()
        if interval and axial:
            from_, to_ = radians(from_), radians(to_)
            f = np.mean(
                ((cos(from_), sin(from_)), (cos(to_), sin(to_))), axis=0
            )
            p = (cos(radians(theta)), sin(radians(theta)))
            if np.dot(f, p) < 0:
                theta += 180.0
        if confidence is not None:
            confcirc = Arc(
                (0, 0),
                width=2.08,
                height=2.08,
                angle=0.0,
                theta1=theta - confidence,
                theta2=theta + confidence,
                ec=mean_settings["color"],
                lw=mean_settings["linewidth"],
                linestyle=mean_settings["linestyle"],
                fill=None,
                zorder=0,
            )
            self.plotaxes.add_patch(confcirc)

        rtheta = radians(theta)
        lin = Line2D(
            (
                cos(rtheta) + cos(rtheta) * 0.11,
                cos(rtheta) + cos(rtheta) * 0.065,
            ),
            (
                sin(rtheta) + sin(rtheta) * 0.11,
                sin(rtheta) + sin(rtheta) * 0.065,
            ),
            c=mean_settings["color"],
            lw=mean_settings["linewidth"],
            linestyle=mean_settings["linestyle"],
        )
        self.plotaxes.add_line(lin)

    def plot_rose(self, nodes, radii, rose_settings):
        patches = []
        n = nodes.shape[0]
        # self.plotaxes.scatter(*nodes.T, c=np.arange(n))

        mid_cn = (nodes[0] + nodes[1]) / 2.0
        theta1 = degrees(atan2(mid_cn[1], mid_cn[0]))
        m = degrees(atan2(nodes[0, 1], nodes[0, 0]))
        self.plotaxes.add_patch(
            Wedge((0, 0), radii[0], theta1, 2 * m - theta1, **rose_settings)
        )

        for i in range(1, n - 1):
            pn, cn, nn = (
                nodes[i - 1],
                nodes[i],
                nodes[(i + 1)],
            )  # this is wrong...
            mid_pc = (pn + cn) / 2.0
            mid_cn = (cn + nn) / 2.0
            theta1 = degrees(atan2(mid_pc[1], mid_pc[0]))
            theta2 = degrees(atan2(mid_cn[1], mid_cn[0]))
            radius = radii[i]
            self.plotaxes.add_patch(
                Wedge((0, 0), radius, theta2, theta1, **rose_settings)
            )
        mid_pc = (nodes[-2] + nodes[-1]) / 2.0
        theta1 = degrees(atan2(mid_pc[1], mid_pc[0]))
        m = degrees(atan2(nodes[-1, 1], nodes[-1, 0]))
        self.plotaxes.add_patch(
            Wedge((0, 0), radii[-1], 2 * m - theta1, theta1, **rose_settings)
        )

    def plot_kite(self, nodes, radii, full_circle, kite_settings):
        xy = (
            nodes * radii
            if full_circle
            else np.concatenate((nodes * radii, ((0, 0),)), axis=0)
        )
        polygon = Polygon(xy, **kite_settings)
        self.plotaxes.add_patch(polygon)

    def plot_lines(self, nodes, radii, mean_deviation, line_settings):
        patches = []
        mean = radii.mean()
        for node, radius in zip(nodes, radii):
            patches.append(
                (mean * node, radius * node)
                if mean_deviation
                else ((0.0, 0.0), radius * node)
            )
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

        separators = [
            a
            for a in self.plot_toolbar.findChildren(QtWidgets.QAction)
            if a.isSeparator()
        ]
        self.plot_toolbar.insertWidget(separators[-1], self.vollmer)
        self.plot_toolbar.insertWidget(separators[-1], self.flinn)

    def read_vollmer(self, X, Y):
        if X > 0 and X > Y / sqrt3 and X < 1 - Y / sqrt3:
            R = Y / sqrt3_2
            G = X - R / 2.0
            P = 1 - R - G
            return "P %.2f, R %.2f, G %.2f" % (P, R, G)
        else:
            return ""

    def read_flinn(self, X, Y):
        if X > 0 and Y > 0:
            return "ln(S2/S3) %.2f, ln(S1/S2) %.2f\nK %.2f, C %.2f" % (
                X,
                Y,
                Y / X,
                X + Y,
            )
        else:
            return ""

    def plot_data(self, plot_item):
        self.plot_list.append(plot_item)

    def draw_plot(self):
        if self.flinn.isChecked():
            self.draw_Flinn()
        elif self.vollmer.isChecked():
            self.draw_Vollmer()
        if self.legend_items:
            self.plotaxes.legend(
                *list(zip(*self.legend_items)),
                bbox_to_anchor=(1.1, 1),
                loc=2,
                fontsize=self.settings.general_settings["fontsize"],
                numpoints=1,
                fancybox=True
            )
        self.legend_items = []
        self.plot_list = []
        self.plot_canvas.draw()
        self.drawn = True

    def draw_Vollmer(self):
        self.plotFigure.clf()
        fontsize = self.settings.general_settings["fontsize"]
        self.plotaxes = axes = Subplot(
            self.plotFigure,
            111,
            clip_on="True",
            xlim=(-0.1, 1.05),
            ylim=(-0.1, 1.05),
            autoscale_on="True",
            label="vollmer",
            aspect="equal",
            adjustable="box",
            anchor="SW",
        )
        self.plotFigure.add_subplot(axes)
        self.plotaxes.format_coord = self.read_vollmer
        axes.axis["right"].set_visible(False)
        axes.axis["top"].set_visible(False)
        axes.axis["bottom"].set_visible(False)
        axes.axis["left"].set_visible(False)

        tr1 = Line2D((0, 1), (0, 0), c="black")
        axes.add_line(tr1)
        tr2 = Line2D((0, 0.5), (0, sqrt3_2), c="black")
        axes.add_line(tr2)
        tr3 = Line2D((1, 0.5), (0, sqrt3_2), c="black")
        axes.add_line(tr3)

        for i in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            diag = Line2D(
                (i / 2, 1.0 - i / 2),
                (sqrt3_2 * i, sqrt3_2 * i),
                c="grey",
                lw=0.5,
            )
            axes.add_line(diag)
            diag2 = Line2D((i / 2, i), (sqrt3_2 * i, 0), c="grey", lw=0.5)
            axes.add_line(diag2)
            diag3 = Line2D(
                (i, i + (1 - i) / 2),
                (0, sqrt3_2 - sqrt3_2 * i),
                c="grey",
                lw=0.5,
            )
            axes.add_line(diag3)

        axes.text(
            -0.08,
            -0.05,
            "Point",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="left",
        )
        axes.text(
            0.97,
            -0.05,
            "Girdle",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="left",
        )
        axes.text(
            0.5,
            0.88,
            "Random",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
        )

        for i in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            axes.text(
                (1 - i) / 2,
                sqrt3_2 * (1 - i) - 0.01,
                "%d" % (i * 100),
                family="sans-serif",
                size=fontsize,
                horizontalalignment="right",
                color="grey",
                rotation="60",
            )
            axes.text(
                i,
                -0.02,
                "%d" % (i * 100),
                family="sans-serif",
                size=fontsize,
                horizontalalignment="center",
                verticalalignment="top",
                color="grey",
            )
            axes.text(
                1.0 - i / 2,
                sqrt3_2 * i - 0.01,
                "%d" % (i * 100),
                family="sans-serif",
                size=fontsize,
                horizontalalignment="left",
                color="grey",
                rotation="-60",
            )

        for plot_item in self.plot_list:
            x = plot_item.G + (plot_item.R / 2.0)
            y = plot_item.R * sqrt3_2
            element, = axes.plot(
                x, y, linestyle="", **plot_item.point_settings
            )
            if plot_item.legend:
                self.legend_items.append((element, plot_item.legend_text))

        axes.set_xlim(-0.1, 1.05)
        axes.set_ylim(-0.1, 1.05)

    def draw_Flinn(self):
        self.plotFigure.clf()
        fontsize = self.settings.general_settings["fontsize"]
        self.plotaxes = axes = Subplot(
            self.plotFigure,
            111,
            clip_on="True",
            xlim=(-0.2, 7.2),
            ylim=(-0.2, 7.2),
            autoscale_on="True",
            xlabel="ln(S2/S3)",
            ylabel="ln(S1/S2)",
            label="flinn",
            aspect="equal",
            adjustable="box",
            anchor="W",
        )
        self.plotFigure.add_subplot(axes)
        self.plotaxes.format_coord = self.read_flinn
        axes.axis["right"].set_visible(False)
        axes.axis["top"].set_visible(False)

        for i in [0.2, 0.5, 1.0, 2.0, 5.0]:
            if i <= 1.0:
                diag = Line2D((0, 7.0), (0, (i * 7.0)), c="grey", lw=0.5)
                axes.add_line(diag)
            else:
                diag = Line2D((0, (7.0 / i)), (0, 7.0), c="grey", lw=0.5)
                axes.add_line(diag)

        for j in [2, 4, 6]:
            diag2 = Line2D((0, j), (j, 0), c="grey", lw=0.5)
            axes.add_line(diag2)

        axes.text(
            6.25,
            0.05,
            "K = 0",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="left",
            color="grey",
        )
        axes.text(
            0.15,
            6.1,
            "K = inf.",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="left",
            color="grey",
            rotation="vertical",
        )
        axes.text(
            6.45,
            6.4,
            "K = 1",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
            color="grey",
            rotation="45",
        )
        axes.text(
            3.2,
            6.4,
            "K = 2",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
            color="grey",
            rotation="63.5",
        )
        axes.text(
            1.2,
            6.4,
            "K = 5",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
            color="grey",
            rotation="78.7",
        )
        axes.text(
            6.4,
            3.1,
            "K = 0.5",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
            color="grey",
            rotation="26.6",
        )
        axes.text(
            6.5,
            1.3,
            "K = 0.2",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
            color="grey",
            rotation="11.3",
        )
        axes.text(
            2.6,
            3.35,
            "C = 6",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
            color="grey",
            rotation="-45",
        )
        axes.text(
            1.75,
            2.2,
            "C = 4",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
            color="grey",
            rotation="-45",
        )

        axes.text(
            3.5,
            3.75,
            "Girdle/Cluster Transition",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="left",
            verticalalignment="bottom",
            color="grey",
            rotation="45",
        )
        axes.text(
            6.5,
            7.2,
            "CLUSTERS",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="right",
            verticalalignment="bottom",
            color="grey",
        )
        axes.text(
            7.2,
            6.5,
            "GIRDLES",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="left",
            verticalalignment="top",
            color="grey",
            rotation="-90",
        )

        for plot_item in self.plot_list:
            element, = axes.plot(
                plot_item.kx,
                plot_item.ky,
                linestyle="",
                **plot_item.point_settings
            )
            if plot_item.legend:
                self.legend_items.append((element, plot_item.legend_text))

        axes.set_xlim(0.0, 7.2)
        axes.set_ylim(0.0, 7.2)


# Really need to remake this
def PlotStereoNetCircle(axes, caxes, fontsize, rotate):
    """Function to create the stereonet circle"""
    caxes.cla()
    caxes.set_axis_off()
    axes.cla()
    axes.set_axis_off()
    if not rotate:
        axes.text(
            0.01,
            1.025,
            "N",
            family="sans-serif",
            size=fontsize,
            horizontalalignment="center",
        )
        x_cross = [0, 1, 0, -1, 0]
        y_cross = [0, 0, 1, 0, -1]
        axes.plot(x_cross, y_cross, "k+", markersize=8, label="_nolegend_")
    circ = Circle(
        (0, 0),
        radius=1,
        edgecolor="black",
        facecolor="none",
        clip_box="None",
        label="_nolegend_",
    )
    axes.add_patch(circ)
    return circ
