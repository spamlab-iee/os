#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import distutils.cmd
import distutils.log
from glob import glob
from os import path

from PyQt5.uic import compileUi


class BuildUICommand(distutils.cmd.Command):
    """Runs pyuic5 on all .ui files on the ui folder"""
    description = "runs pyuic5 on .ui files inside ./ui/"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        """Run command."""
        for ui_file in glob("ui_files/*.ui"):
            basename = path.splitext(path.basename(ui_file))[0]
            py_file = path.join("openstereo", "ui", basename + "_ui.py")
            self.announce(
                'Compiling Qt Designer source: %s' % str(ui_file),
                level=distutils.log.INFO)
            with open(py_file, "w") as fout:
                compileUi(ui_file, fout)


setup(
    name="OpenStereo",
    version="0.9.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'openstereo = openstereo.os_base:os_main',
        ]
    },
    install_requires=[
        'numpy',
        'matplotlib',
        # 'PyQt5',
        'xlrd',
        'PyShp',
        'networkx',
        'ply2atti',
        'auttitude'
    ],
    cmdclass={
        'buildui': BuildUICommand
    },
    # metadata for upload to PyPI
    author="Arthur Endlein",
    author_email="endarthur@gmail.com",
    description="Software for analysis of structural data",
    license="GPLv3",
    keywords="geology attitude stereonet projection structural",
    url="https://github.com/endarthur/os",
    download_url="https://github.com/endarthur/os/archive/v0.9.0.tar.gz",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ])
