
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
    def __init__(self, nodes, count, contour_settings, contour_line_settings,
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
