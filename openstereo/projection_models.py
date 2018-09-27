from math import sin, cos, radians, sqrt

import numpy as np

from openstereo.os_math import sphere

sqrt2 = sqrt(2.0)


class Projection(object):
    def __init__(self, settings):
        self.settings = settings
        self.build_rotation_matrix()

    def build_rotation_matrix(self):
        azim = radians(self.settings.rotation_settings["azim"])
        plng = radians(self.settings.rotation_settings["plng"])
        rake = radians(self.settings.rotation_settings["rake"])

        R1 = np.array(
            (
                (cos(rake), 0.0, sin(rake)),
                (0.0, 1.0, 0.0),
                (-sin(rake), 0.0, cos(rake)),
            )
        )

        R2 = np.array(
            (
                (1.0, 0.0, 0.0),
                (0.0, cos(plng), sin(plng)),
                (0.0, -sin(plng), cos(plng)),
            )
        )

        R3 = np.array(
            (
                (cos(azim), sin(azim), 0.0),
                (-sin(azim), cos(azim), 0.0),
                (0.0, 0.0, 1.0),
            )
        )

        self.R = R3.dot(R2).dot(R1)
        self.Ri = np.linalg.inv(self.R)

    def rotate(self, x, y, z):
        self.build_rotation_matrix()
        return self.R.dot((x, y, z))

    def project_data(
        self, x, y, z, invert_positive=True, ztol=0.0, rotate=None
    ):
        if (
            self.settings.check_settings["rotate"]
            and rotate is None
            or rotate is True
        ):
            x, y, z = self.rotate(x, y, z)
        if invert_positive:
            c = np.where(z > ztol, -1, 1)
            x, y, z = c * x, c * y, c * z
        if (
            self.settings.general_settings["hemisphere"] == "Upper"
            and rotate is None
        ):
            c = np.where(z != 0.0, -1, 1)
            x, y = c * x, c * y
        return self.project(x, y, z)

    def read_plot(self, X, Y):
        if X * X + Y * Y > 1.0:
            return ""
        x, y, z = self.inverse(X, Y)
        if self.settings.check_settings["rotate"]:
            x, y, z = self.Ri.dot((x, y, z))
        theta, phi = sphere(x, y, z)
        if phi >= 0.0:
            return "Pole: %05.1f/%04.1f\nLine: %05.1f/%04.1f" % (
                theta,
                phi,
                (theta - 180) % 360.0,
                90.0 - phi,
            )
        else:
            return ""


class EqualAreaProj(Projection):
    name = "Equal-area"

    def project(self, x, y, z, radius=1.0):
        return x * np.sqrt(1 / (1 - z)), y * np.sqrt(1 / (1 - z))

    def inverse(self, X, Y, radius=1.0):
        X, Y = X * sqrt2, Y * sqrt2
        x = np.sqrt(1 - (X * X + Y * Y) / 4.0) * X
        y = np.sqrt(1 - (X * X + Y * Y) / 4.0) * Y
        z = -1.0 + (X * X + Y * Y) / 2
        return x, y, z


class EqualAngleProj(Projection):
    name = "Equal-angle"

    def project(self, x, y, z, radius=1.0):
        return x / (1 - z), y / (1 - z)

    def inverse(self, X, Y, radius=1.0):
        x = 2.0 * X / (1.0 + X * X + Y * Y)
        y = 2.0 * Y / (1.0 + X * X + Y * Y)
        z = (-1.0 + X * X + Y * Y) / (1.0 + X * X + Y * Y)
        return x, y, z
