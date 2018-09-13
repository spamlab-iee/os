import math
from math import radians, pi, sin, asin, cos, acos, degrees, sqrt
import itertools
import os
from csv import Sniffer, reader
sniffer = Sniffer()
import multiprocessing
from multiprocessing import cpu_count, Pipe

import numpy as np
#from openstereo.conversion import Attitude

import auttitude as au

#translator = Attitude()

import_scipy = True
if import_scipy:
    try:
        from scipy.special import ndtri
    except ImportError:
        from openstereo.ndtri_back import ndtri
else:
    from openstereo.ndtri_back import ndtri

#set this for experimental multi-core support.
multicore_when_possible = False

rotation_to_direction = np.array(((0., 1.), (-1., 0.)))


def dcos(data):
    """Converts poles into direction cossines."""
    theta, phi = np.radians(data.T)
    return np.array((-np.sin(phi) * np.sin(theta),
                     -np.sin(phi) * np.cos(theta), -np.cos(phi))).T


def dcos_lines(data):
    """Converts lines into direction cosines."""
    return dcos(invert(data))


def dcos_circular(data):
    data = np.radians(data)
    return np.array((np.sin(data), np.cos(data))).T


def sphere(data):
    """Calculates the attitude of poles direction cossines."""
    x, y, z = data.T
    sign_z = np.copysign(1, z)
    z = np.clip(z, -1., 1.)
    return np.array((np.degrees(np.arctan2(sign_z * x, sign_z * y)) % 360,
                     np.degrees(np.arccos(np.abs(z))))).T


def sphere_lines(data):
    """Calculate the attitude of lines direction cosines."""
    return invert(sphere(data))


def circle(data, axial=False):
    azimuths = np.degrees(np.arctan2(*data.T)) % 360.
    return azimuths if not axial else azimuths / 2.


def invert(data):
    """Inverts poles into planes and vice versa."""
    theta, phi = np.transpose(data)
    return np.array(((theta - 180) % 360, 90 - phi)).T


def RHR(data):
    """Converts data into Right Hand Rule."""
    theta, phi = data.T
    return np.array(((theta - 90) % 360, phi)).T


def equal_angle(data):
    x, y, z = data.T
    return x / (1 - z), y / (1 - z)


def equal_area(data):
    x, y, z = data.T
    return x * np.sqrt(2 / (1 - z)), y * np.sqrt(2 / (1 - z))


def concatenate(A, B):
    """Concatenate A and B directional datasets, retaining A's additional attributes"""
    return DirectionalData(np.vstack((A.data, B.data)), *A.args, **A.kwargs)


def intersect(A, B):
    """Calculate all intersections between A and B directional datasets, retaining A's additional attributes"""
    all_intersections = np.array(
        [np.cross(a, b) for a, b in itertools.product(A.data, B.data)])
    intersections = all_intersections[np.nonzero(
        np.linalg.norm(all_intersections, axis=1))]
    return DirectionalData(intersections, *A.args, **A.kwargs)


def regular_grid(node_spacing):
    """\
Builds a regular grid over the hemisphere, with the given average node spacing."""
    nodes = [
        (0., 90.),
    ]
    spacing = math.radians(node_spacing)
    for phi in np.linspace(
            node_spacing, 90., 90. / node_spacing, endpoint=False):
        azimuth_spacing = math.degrees(2 * math.asin(
            (math.sin(spacing / 2) / math.sin(math.radians(phi)))))
        for theta in np.linspace(0., 360., 360. / azimuth_spacing):
            nodes.append((theta + phi + node_spacing / 2, 90. - phi))
    for theta in np.linspace(0., 360., 360. / azimuth_spacing):
        nodes.append(((theta + 90. + node_spacing / 2) % 360., 0.))
    return np.array(nodes)


def sphere_regular_grid(node_spacing):
    """\
Builds a regular grid over the sphere, with the given average node spacing."""
    nodes = [(0., 90.), (0, -90.)]
    spacing = math.radians(node_spacing)
    for phi in np.linspace(
            node_spacing, 90., 90. / node_spacing, endpoint=False):
        azimuth_spacing = math.degrees(2 * math.asin(
            (math.sin(spacing / 2) / math.sin(math.radians(phi)))))
        for theta in np.linspace(0., 360., 360. / azimuth_spacing):
            nodes.append((theta + phi + node_spacing / 2, 90. - phi))
            nodes.append((theta + phi + node_spacing / 2, phi - 90.))
    for theta in np.linspace(0., 360., 360. / azimuth_spacing):
        nodes.append(((theta + 90. + node_spacing / 2) % 360., 0.))
    return np.array(nodes)


def universal_loader(fin, extension=None, worksheet=0, dialect=None):
    """\
Loads many different possible file formats, dispatching them to
the proper specific loader."""
    input_data = None
    extension = extension if extension is not None\
                    else os.path.splitext(fin)[-1]
    if extension in [".csv", ".txt", ".dat"]:
        #thanks http://stackoverflow.com/a/1303266/1457481
        f = open(fin) if isinstance(fin, str) else fin
        try:
            #data = f.readlines()
            #geoeas_offset = sniff_geoeas(data)
            dialect = sniffer.sniff(f.read(1024))
            f.seek(0)
        except:
            f.seek(0)
            input_data = np.loadtxt(fin)
        else:
            input_data = reader(f, dialect=dialect)
            #input_data = np.loadtxt(fin)
    elif extension in [".npy", ".npz"]:
        input_data = np.load(fin)
    elif extension in [".xls", ".xlsx"]:
        from xlrd import open_workbook
        data = open_workbook(fin).sheets()[worksheet]
        input_data = [data.row_values(i) for i in range(data.nrows)]
    return input_data

def universal_translator(data, longitude_column=0, colatitude_column=1,\
                         colatitude=True, dip_direction=False,\
                         circular=False):
    """Translates data from many different notations into dipdirection/dip,
    semi-automatically"""
    translated_data = []
    if not circular:
        for line in data:
            try:
                translated_data.append(
                    au.translate_attitude(
                line[longitude_column],
                line[colatitude_column],
                strike=not dip_direction))
            except ValueError:
                continue
        # translated_data = np.array([
        #     au.translate_attitude(
        #         line[longitude_column],
        #         line[colatitude_column],
        #         strike=not dip_direction) for line in data if line
        # ])
    else:
        translated_data = np.array([
            au.translate_attitude(
                line[longitude_column], "45", strike=not dip_direction)
            for line in data if line
        ])[:, 0]
        for line in data:
            try:
                translated_data.append(
                    au.translate_attitude(
                line[longitude_column],
                "45",
                strike=not dip_direction))
            except ValueError:
                continue
    return np.array(translated_data)


def load(fin, *args, **kwargs):
    """\
Attempts to automatically load the given filename, using whatever extra information is
made available by the user, returning a DirectionalData object. See universal_translator
and universal_loader signatures for additional information. Important options:
dip_direction, defaults True:
interpret data as dip direction, or strike if set to False.
line, defaults to False:
interpret data as lines, instead of planes."""
    extension = kwargs.get('extension', None)
    worksheet = kwargs.get('worksheet', 0)
    if isinstance(fin, str):
        extension = extension if extension is not None else os.path.splitext(
            fin)[-1]
        input_data = universal_loader(
            fin, extension=extension, worksheet=worksheet)
    else:
        input_data = fin
    if kwargs.get("keep_input", False):
        input_data = kwargs["input_data"] = list(input_data)
    dip_direction = kwargs.get('dip_direction', True)
    line = kwargs.get('line', False)
    longitude_column = kwargs.get('strike_column', 0) if kwargs.get('strike_column', 0)\
                            else kwargs.get('dipdir_column', 0)
    colatitude_column = kwargs.get('dip_column', 1)
    translate = kwargs.get('translate_data', True)
    circular = kwargs.get('circular', False)
    converted_data = universal_translator(
        input_data,
        longitude_column=longitude_column,
        colatitude_column=colatitude_column,
        colatitude=line,
        dip_direction=dip_direction,
        circular=circular) if translate else input_data
    if not circular:
        if not line:
            converted_data = invert(converted_data)
        vector_data = dcos_lines(converted_data)
    else:
        vector_data = dcos_circular(converted_data)
    return DirectionalData(vector_data, *args, **kwargs)


def calculate_axes(data):
    """Calculates the eigenvectors and eigenvalues of the dispersion matrix of the dataset."""
    dispersion_tensor = np.cov(data.T[:3, :])
    eigenvalues, eigenvectors = np.linalg.eigh(dispersion_tensor, UPLO='U')
    eigenvalues_order = eigenvalues.argsort()[::-1]
    eigenvectors = eigenvectors[:, eigenvalues_order].T
    return eigenvectors, eigenvalues


def rotation_matrix(u, theta):
    #From openstereo development notes,
    #from http://stackoverflow.com/questions/6802577/python-rotation-of-3d-vector
    #Using the Euler-Rodrigues formula:
    #http://en.wikipedia.org/wiki/Euler%E2%80%93Rodrigues_parameters
    """
    Return the rotation matrix associated with counterclockwise rotation about
    the given axis u by theta degrees.
    """
    u = np.asarray(u)
    theta = math.radians(theta)
    u = u / np.linalg.norm(u)
    a = math.cos(theta / 2)
    b, c, d = -u * math.sin(theta / 2)
    aa, bb, cc, dd = a * a, b * b, c * c, d * d
    bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
    return np.array([[aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
                     [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
                     [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc]])


def rotate(data, u, theta):
    return DirectionalData(
        np.dot(data.data, rotation_matrix(u, theta)), *data.args,
        **data.kwargs)


def project(data, new_axes):
    return DirectionalData(
        np.dot(data.data, new_axes.T), *data.args, **data.kwargs)


class DirectionalData(object):
    def __init__(self, data, *args, **kwargs):
        """\
        Base class for directional data analysis, either 2d or 3d. Store optionally
        additional arguments for plotting."""
        self.args, self.kwargs = args, kwargs
        self.data = data
        self.data_circle = kwargs.get('data_circle', None)
        self.input_data = kwargs.pop("input_data", [])
        self.n, self.d = data.shape

        if self.d == 3:
            self.data_sphere = kwargs.get('data_sphere',\
                sphere(data/np.linalg.norm(data, axis=1)[:, np.newaxis]))
            if self.kwargs.get('line'):
                self.data_sphere = invert(self.data_sphere)
            if self.data_circle is None:
                circular_data = self.data[:, :2] / np.linalg.norm(
                    self.data[:, :2], axis=1)[:, None]
                circular_data = circular_data[np.isfinite(circular_data).all(
                    axis=1)]
                if not self.kwargs.get('line'): circular_data = -circular_data
                self.data_circle = circle(circular_data,
                                          kwargs.get('axial', False))
        else:
            self.data_sphere = kwargs.get('data_sphere',\
                circle(data, kwargs.get('axial', False)))
            self.data_circle = self.data_circle if self.data_circle is not None else\
                 circle(data, kwargs.get('axial', False))

        if kwargs.get('calculate_statistics', True) and self.n > 1:
            self.initialize_statistics()
        self._grid = None
        self._cgrid = None

    def initialize_statistics(self):
        self.resultant_vector = np.sum(self.data, axis=0)
        self.mean_resultant_vector = self.resultant_vector / self.n
        self.mean_vector = self.resultant_vector / np.linalg.norm(
            self.resultant_vector)
        self.resultant_length = np.linalg.norm(self.resultant_vector)
        self.mean_resultant_length = self.resultant_length / self.n

        if self.d == 3:
            self.resultant_vector_sphere = sphere(self.resultant_vector)
            self.fisher_k = (self.n - 1) / (
                self.n - np.linalg.norm(self.resultant_vector))
            direction_tensor = np.dot(self.data.T, self.data) / self.n
            eigenvalues, eigenvectors = np.linalg.eigh(direction_tensor)
            eigenvalues_order = (-eigenvalues).argsort()

            self.eigenvalues = eigenvalues[eigenvalues_order]
            self.eigenvectors = eigenvectors[:, eigenvalues_order].T
            self.eigenvectors_sphere = sphere_lines(self.eigenvectors)
            self.concentrated_mean_vector = np.mean(\
                self.data*np.where(\
                    self.eigenvectors[0].dot(self.data.T) < 0., 1, -1)[:, None],\
                axis=0)
            self.concentrated_mean_vector /= np.linalg.norm(
                self.concentrated_mean_vector)

            #From Vollmer 1990
            self.vollmer_P = (
                self.eigenvalues[0] - self.eigenvalues[1]) / eigenvalues.sum()
            self.vollmer_G = 2 * (
                self.eigenvalues[1] - self.eigenvalues[2]) / eigenvalues.sum()
            self.vollmer_R = 3 * self.eigenvalues[2] / eigenvalues.sum()

            self.vollmer_classification = ("point", "girdle", "random")[\
                np.argmax((self.vollmer_P,self.vollmer_G, self.vollmer_R))]

            self.vollmer_B = self.vollmer_P + self.vollmer_G
            self.vollmer_C = math.log(
                self.eigenvalues[0] / self.eigenvalues[2])

            #From Woodcock 1977
            self.woodcock_Kx = math.log(
                self.eigenvalues[1] / self.eigenvalues[2])
            self.woodcock_Ky = math.log(
                self.eigenvalues[0] / self.eigenvalues[1])
            self.woodcock_C = math.log(
                self.eigenvalues[0] / self.eigenvalues[2])

            self.woodcock_K = self.woodcock_Ky / self.woodcock_Kx

            circular_data = self.data[:, :2] / np.linalg.norm(
                self.data[:, :2], axis=1)[:, None]
            circular_data = circular_data[np.isfinite(circular_data).all(
                axis=1)]
            if not self.kwargs.get('line'): circular_data = -circular_data
            self.circular_resultant_vector = np.sum(circular_data, axis=0)
            self.circular_mean_resultant_vector = self.circular_resultant_vector / self.n
            self.circular_resultant_length = np.linalg.norm(
                self.circular_resultant_vector)
            self.circular_mean_resultant_length = self.circular_resultant_length / self.n
            #for line_s, line_c in zip(self.data, circular_data):
            #    print(line_c, line_s)

        else:
            self.circular_resultant_vector = self.resultant_vector
            self.circular_mean_resultant_vector = self.mean_resultant_vector
            self.circular_resultant_length = self.resultant_length
            self.circular_mean_resultant_length = self.mean_resultant_length

        self.circular_variance = 1 - self.mean_resultant_length
        self.circular_standard_deviation = math.sqrt(
            -2 * math.log(1 - self.circular_variance))
        self.circular_mean_direction_axial, self.circular_confidence_axial =\
            self.estimate_circular_confidence(axial=True)
        self.circular_mean_direction, self.circular_confidence =\
            self.estimate_circular_confidence(axial=False)

    def __add__(self, other):
        """Concatenate A and B directional datasets, retaining A's additional attributes"""
        return concatenate(self, other)

    def __mul__(self, other):
        """Calculate all intersections between A and B directional datasets, retaining A's additional attributes"""
        return intersect(self, other)

    def estimate_khat(self, R_):
        n = self.n
        if R_ < 0.53:
            K_ = 2.0 * R_ + (R_**3.0) + (5 * (R_**5.0) / 6.0)
        elif 0.53 <= R_ <= 0.85:
            K_ = -0.4 + 1.39 * R_ + 0.43 / (1. - R_)
        else:  # R_ > 0.85:
            K_ = 1.0 / (R_**3.0 - 4.0 * (R_**2.0) + 3.0 * R_)
        if (0.4 <= K_ < 1.0 and n >= 25) or\
           (1.0 <= K_ < 1.5 and n >= 15) or\
           (1.5 <= K_ < 2.0 and n >= 10) or\
           K_ >= 2.0:
            K_ = max(K_ - 2./(n*K_), 0.) if K_ < 2. else\
                 ((n - 1)**3)*K_/(n+ n**3)
        return K_

    def estimate_circular_confidence(self, axial=False, alpha=.95):
        if axial:
            theta = 2 * self.data_circle
            dcos = np.array((np.cos(np.radians(theta)),
                             np.sin(np.radians(theta)))).T
            mean = dcos.sum(axis=0)
            theta_ = circle(mean)
            R_ = np.linalg.norm(mean) / self.n
        else:
            R_ = self.circular_mean_resultant_length
            theta_ = circle(self.circular_resultant_vector)
        if axial:
            theta = theta / 2.
        K_ = self.estimate_khat(R_)
        z = ndtri(alpha)
        sigma = 1.0 / sqrt(self.n * R_ * K_)
        try:
            i = degrees(asin(z * sigma))
            if axial:
                i = i / 2.
        except ValueError:
            i = None
        return theta_, i

    @property
    def grid(self):
        if self._grid is None:
            self._grid = SphericalGrid(**self.kwargs) if self.d == 3 else\
                CircularGrid(**self.kwargs)
        return self._grid

    @property
    def cgrid(self):
        if self._cgrid is None:
            self._cgrid = CircularGrid(**self.kwargs)
        return self._cgrid

    @property
    def grid_nodes(self):
        return self.grid.grid

    def grid_fisher(self, k=None):
        return self.grid.count_fisher(self, k)

    def grid_kamb(self, theta=None):
        return self.grid.count_kamb(self, theta)
    def grid_rose(self, aperture=10., axial=False, spacing=10., offset=0.,\
        data_weight=None, direction=False, nodes=None):
        if self.d == 2:
            circular_data = self.data if data_weight is None\
                else self.data*data_weight[:, None]
        else:
            circular_data = self.data[:, :2] / np.linalg.norm(
                self.data[:, :2], axis=1)[:, None]
            if not self.kwargs.get('line'): circular_data = -circular_data
        if type(self.grid) == CircularGrid:
            grid = self.grid
        else:
            if self._cgrid is None:
                grid = self._cgrid = CircularGrid()
            else:
                grid = self._cgrid
            # count(self, data, aperture=None,\
            #                        axial=False, spacing=None, offset=0, nodes=None)
        if direction: circular_data = circular_data.dot(rotation_to_direction)
        return grid.count(circular_data, aperture, axial, spacing,\
                          offset, nodes, data_weight)
    def grid_munro(self, weight=.9, aperture=11.,\
                   axial=False, spacing=1., offset=0.,\
                   data_weight=None, direction=False, nodes=None):
        if self.d == 2:
            circular_data = self.data
        else:
            circular_data = self.data[:, :2] / np.linalg.norm(
                self.data[:, :2], axis=1)[:, None]
            if not self.kwargs.get('line'): circular_data = -circular_data
        if type(self.grid) == CircularGrid:
            grid = self.grid
        else:
            if self._cgrid is None:
                grid = self._cgrid = CircularGrid()
            else:
                grid = self._cgrid
        if direction: circular_data = circular_data.dot(rotation_to_direction)
        return grid.count_munro(circular_data, weight, aperture,\
                                axial, spacing, offset, nodes, data_weight)

    @property
    def mode(self):
        if self.grid.result is None:
            #if self.d == 3:
            result = self.grid.count_fisher(self)  #?
            #else:
            #result = self.grid_munro()
        return self.grid.grid[self.grid.result.argmax(), :]

    @property
    def mode_sphere(self):
        return sphere_lines(self.mode)

    def __repr__(self):
        return "%s(%s, *%s, **%s)" % (self.__class__, self.data, self.args,
                                      self.kwargs)

    def __str__(self):
        if self.d == 2:
            factor = self.kwargs.get('simm_factor', 1)
            return """\
{filename}\
Circular Statistics:
Number of data lines:
{self.n}
Resultant {datatype}:
{resultant}
Resultant Length:
{self.circular_resultant_length}
Mean Resultant Length :
{self.circular_mean_resultant_length}

Circular Variance:
{self.circular_variance}
Circular Standard Deviation:
{self.circular_standard_deviation}\
""".format(self=self,
           filename=self.kwargs.get('filename', ''),
           datatype=self.kwargs.get('datatype', 'Azimuth'),
           resultant=circle(self.resultant_vector,
                            self.kwargs.get('axial', False)))
        elif self.d == 3:
            statistics = """\
{filename}\
Spherical Statistics:
Number of data lines= {self.n}
Fisher K:
{self.fisher_k}
Expected Distribution:
{self.vollmer_classification}
Eigenvectors: 
1: {self.eigenvectors_sphere[0]}
2: {self.eigenvectors_sphere[1]}
3: {self.eigenvectors_sphere[2]}
Shape parameter
K = {self.woodcock_K}
Strength parameter
C = {self.woodcock_C}
Normalized Eigenvalues:
S1: {self.eigenvalues[0]}
S2: {self.eigenvalues[1]}
S3: {self.eigenvalues[2]}
Fabric (triangular diag.): 
Point  = {self.vollmer_P}
Girdle = {self.vollmer_G}
Random = {self.vollmer_R}
Cilindricity = {self.vollmer_C}

Circular Statistics:
Resultant Vector:
{self.circular_resultant_vector}
Resultant Length:
{self.circular_resultant_length}
Mean Resultant Length :
{self.circular_mean_resultant_length}
Circular Variance:
{self.circular_variance}
Circular Standard Deviation:
{self.circular_standard_deviation}
Mean Orientation:
{self.circular_mean_direction}
Confidence Interval (95%):
+/- {self.circular_confidence}\
""".format(self=self, filename=self.kwargs.get('filename', ''))
            if self.grid.result is not None:
                #set float format params
                statistics += """
Spherical Mode:
{0}/{1}\
""".format(*self.mode_sphere)
        return statistics

    @property
    def statistics(self):
        return str(self)

    @property
    def source(self):
        return "\n".join("{}: {}".format(arg, self.kwargs[arg])
                         for arg in self.kwargs)


class PartProcessor(multiprocessing.Process):
    def run(self):
        connection = self._kwargs.pop("connection")
        connection.send(self._target(*self._args, **self._kwargs))
        connection.close()


def parallel(function):
    """\
A parallelization decorator for simple functions that evaluate over a grid,
splitting it's first dimension among the available cores."""
    core_count = cpu_count()
    if core_count < 2: return function

    def parallel_function(grid, *args, **kwargs):
        output = []
        cores = []
        grid_size = grid.shape[0]
        grid_section = int(grid_size / core_count)
        for n in range(core_count - 1):
            server_p, client_p = Pipe()
            core = PartProcessor(
                grid[n * grid_section:(n + 1) * grid_section, :],
                target=function,
                *args,
                **kwargs)
            core.start()
            cores.append(core)
        core = PartProcessor(
            grid[(core_count - 1) * grid_section:-1, :],
            target=function,
            *args,
            **kwargs)
        core.start()
        cores.append(core)
        for core in cores:
            output.append(core.recv())
            core.close()
        return np.vstack(output)

    return parallel_function


def parallel_counter(counter_factory):  #yes, a factory decorator!
    """\
A factory decorator that applies @parallel on the functions returned by
the decorated factory. See parallel for more details."""

    def parallel_counter_factory(*args, **kwargs):
        if multicore_when_possible:
            return parallel(counter_factory(*args, **kwargs))
        else:
            return counter_factory(*args, **kwargs)

    return parallel_counter_factory


@parallel_counter
def FisherCounter(k):
    try:
        from grid_functions.fisher_counter import count

        def counter(grid, direction_cosines):
            return count(grid, direction_cosines, k)
    except ImportError:

        def counter(grid, direction_cosines):
            try:
                return np.exp(k * (np.dot(grid, direction_cosines.T) - 1)).sum(
                    axis=1)
            except MemoryError:
                result = np.zeros((grid.shape[0], 1))
                for input_node, output_node in zip(grid, result):
                    output_node[:] = np.exp(
                        k *
                        (np.dot(input_node, direction_cosines.T) - 1)).sum()

    return counter


@parallel_counter
def FisherCounterAxial(k):
    try:
        from grid_functions.fisher_counter_axial import count

        def counter(grid, direction_cosines):
            return count(grid, direction_cosines, k)
    except ImportError:

        def counter(grid, direction_cosines):
            try:
                return np.exp(
                    k * (np.abs(np.dot(grid, direction_cosines.T)) - 1)).sum(
                        axis=1)
            except MemoryError:
                result = np.zeros((grid.shape[0], 1))
                for input_node, output_node in zip(grid, result):
                    output_node[:] = np.exp(
                        k *
                        (np.abs(np.dot(input_node, direction_cosines.T)) - 1
                         )).sum()

    return counter


@parallel_counter
def RobinGirdleCounter(k):
    try:
        from grid_functions.robin_girdle_counter import count

        def counter(grid, direction_cosines):
            return count(grid, direction_cosines, k)
    except ImportError:

        def counter(grid, direction_cosines):
            try:
                return np.exp(k * (np.dot(grid, direction_cosines.T)**2)).sum(
                    axis=1)
            except MemoryError:
                result = np.zeros((grid.shape[0], 1))
                for input_node, output_node in zip(grid, result):
                    output_node[:] = np.exp(
                        k *
                        (np.dot(input_node, direction_cosines.T)**2)).sum()

    return counter


class SphericalGrid(object):
    def __init__(self, *args, **kwargs):
        """Creates a spherical counting grid"""
        self.args, self.kwargs = args, kwargs
        node_spacing = self.kwargs.get('node_spacing', 2.5)
        self.grid_nodes = sphere_regular_grid(node_spacing)
        self.grid = dcos_lines(self.grid_nodes)
        self.result = None

    def change_spacing(self, node_spacing):
        self.grid_nodes = sphere_regular_grid(node_spacing)
        self.grid = dcos_lines(self.grid_nodes)
        self.result = None

    def optimize_k(self, direction_cosines):
        #this is here so as to keep scipy as an optional
        from scipy.optimize import minimize_scalar

        def obj(k):
            W = np.exp(k*(np.abs(np.dot(direction_cosines, direction_cosines.T))))\
                *(k/(4*math.pi*math.sinh(k+1e-9)))
            #W = np.power(density, k)
            np.fill_diagonal(W, 0.)
            return -np.log(W.sum(axis=0)).sum()

        return minimize_scalar(obj).x

    def count_fisher(self, data, k=None):
        """\
Performs data counting as in Robin and Jowett (1986). May either receive
as input a DirectionalData object or any numpy array-like. Will guess an appropriate
k if not given and not available from the DirectionalData options."""
        if isinstance(data, DirectionalData):
            k = k if k is not None else data.kwargs.get('counting_k', None)
            n = data.n
            direction_cosines = data.data
        else:
            direction_cosines = data
            n = data.shape[0]
        if k is None:
            if n < 100:  #This is the Recomendation made by Robin & Jowett 86
                k = 2 * (n + 1)
            else:
                k = 100
        try:  #It is bettter to beg forgiveness that ask for permittion.
            self.result = np.exp(
                k * (np.abs(np.dot(self.grid, direction_cosines.T)) - 1)).sum(
                    axis=1)

            return self.result
        except MemoryError:
            result = np.zeros((self.grid.shape[0], 1))
            for input_node, output_node in zip(self.grid, result):
                output_node[:] = np.exp(
                    k * (np.abs(np.dot(input_node, direction_cosines.T)) - 1
                         )).sum()
        self.result = result
        return result

    def count_kamb(self, data, theta=None):
        """\
Performs data counting as in Robin and Jowett (1986) based on Kamb (1956), May either receive
as input a DirectionalData object or any numpy array-like. Will guess an appropriate
counting angle theta if not given and not available from the DirectionalData options."""
        if isinstance(data, DirectionalData):
            theta = theta if theta is not None else data.kwargs.get(
                'counting_theta', None)
            n = data.n
            direction_cosines = data.data
        else:
            direction_cosines = data
            n = data.shape[0]
        if theta is None:
            theta = (n - 1.0) / (n + 1.0)
        else:
            theta = math.cos(math.radians(theta))
        try:
            self.result = np.where(
                np.abs(np.dot(self.grid, direction_cosines.T)) >= theta, 1,
                0).sum(axis=1)
            return self.result
        except MemoryError:
            result = np.zeros((self.grid.shape[0], 1))
            for input_node, output_node in zip(self.grid, result):
                output_node[:] = np.where(
                    np.abs(np.dot(input_node, direction_cosines.T)) >= theta,
                    1, 0).sum()
        self.result = result
        return result

    def count(self, data, method=None):
        """\
If method isn't given, search data for it. If method is a function, execute it with the counting grid
and the data object as parameters, or search SphericalGrid for it, in case it is a string."""
        if isinstance(data, DirectionalData):
            method = method or data.kwargs.get('counting_method', None)
            direction_cosines = data.data
        else:
            direction_cosines = data
        if not method is None:
            if isinstance(method, str):
                return self.__getattribute__(method)(direction_cosines)
            else:
                return method(self.grid, direction_cosines)


class CircularGrid(object):
    def __init__(self, spacing=1., offset=0., **kwargs):
        self.spacing = spacing
        self.grid = self.build_grid(spacing, offset)

    def build_grid(self, spacing, offset=0., from_=0., to_=2 * pi):
        s = radians(spacing)
        o = radians(offset)
        theta_range = np.arange(o, 2 * pi + o, s)
        theta_range = theta_range[np.logical_and(theta_range >= from_,\
                                                 theta_range <= to_)]
        return np.array((np.sin(theta_range), np.cos(theta_range))).T

    def cdis(self, data, nodes=None, axial=False):
        nodes = self.grid if nodes is None else nodes
        d = np.clip(
            np.dot(nodes, np.transpose(data)) / np.linalg.norm(data, axis=1),
            -1, 1)
        if axial:
            d = np.abs(d)
        return d
    def count(self, data, aperture=None,\
                    axial=False, spacing=None, offset=0, nodes=None, data_weight=None):
        aperture = radians(aperture) / 2. if aperture is not None else radians(
            self.spacing) / 2.
        if nodes is None:
            nodes = self.grid if spacing is None else self.build_grid(
                spacing, offset)
        spacing = radians(
            self.spacing) / 2 if spacing is None else radians(spacing) / 2
        c = cos(aperture)
        n = data.shape[0]
        data_weight = np.ones(n) if data_weight is None else data_weight
        return np.where(self.cdis(data, nodes, axial=axial) >= c,\
                        data_weight, 0.).sum(axis=1)[:,None]/data_weight.sum()
    def count_munro(self, data, weight=.9, aperture=10.,\
                    axial=False, spacing=None, offset=0, nodes=None, data_weight=None):
        spacing = 1 if spacing is None else spacing
        if nodes is None:
            nodes = self.grid if spacing is None else self.build_grid(
                spacing, offset)
        d = self.cdis(data, nodes, axial=axial)
        aperture = radians(aperture) / 2. if aperture is not None else radians(
            self.spacing) / 2.
        c = cos(aperture)
        theta = np.arccos(d) * pi / aperture
        data_weight = np.ones(
            data.shape[0]) if data_weight is None else data_weight
        upscale = 1. + 2. * np.power(
            weight, np.linspace(0., aperture, radians(spacing))).sum()
        return (np.where(d >= c, data_weight, 0) * np.power(weight, theta)
                ).sum(axis=1)[:, None] * upscale / data_weight.sum()


def small_circle_axis(data, concentration_axis=None):
    if concentration_axis is not None:
        data = data * np.where(data.dot(concentration_axis) > 0, 1,
                               -1)[:, None]
    S = np.cov(data, rowvar=False)
    eig, eiv = np.linalg.eig(S)
    eig_order = np.argsort(eig)
    eiv = eiv[:, eig_order]
    axis = eiv[:, 0]

    angle_axis = np.arccos(np.abs(data.dot(axis)))

    return axis, angle_axis.mean()