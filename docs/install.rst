Installation
============

Windows
-------

Download the latest .exe installer from:

https://github.com/endarthur/os/releases/latest

When updating, please uninstall the previous version before installing the new.

macOS Installation
------------------

First install pyqt5 and python3 (python3 is automatically installed as a
dependency of pyqt5) using `homebrew`_::

    $ brew install pytqt

.. _homebrew: https://brew.sh/

Once that is done, install OpenStereo from `github`_ using pip3::

    $ pip3 install git+https://github.com/endarthur/os#egg=openstereo

.. _github: https://github.com/endarthur/os

From PyPI
---------

At the command line::

    pip install git+https://github.com/endarthur/os#egg=openstereo

Additionally, install PyQt5 from PyPI if needed (for python 2.7, use package
python-qt5 instead).
