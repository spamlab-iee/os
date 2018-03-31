#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name="OpenStereo",
    version="0.9.0",
    py_modules=['openstereo'],
    entry_points={
        'console_scripts': [
            'openstereo = openstereo.os_base:os_main',
        ]
    },

    install_requires=[
        'numpy',
        'matplotlib',
        # 'PyQt5',
        'PyShp',
        'networkx'
    ],

    # metadata for upload to PyPI
    author="Arthur Endlein",
    author_email="endarthur@gmail.com",
    description="Software for analysis of structural data",
    license="GPLv3",
    keywords="geology attitude stereonet projection structural",
    url="https://github.com/endarthur/os",
    dowload_url="https://github.com/endarthur/os/archive/v0.9.0.tar.gz",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ]
)