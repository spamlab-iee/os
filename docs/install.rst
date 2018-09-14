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

Ubuntu
------

First install pyqt5 and pip::

    $ sudo apt install python3-pyqt5 python3-pip

Once that is done, install OpenStereo from `github`_ using pip3::

    $ pip3 install https://github.com/endarthur/os/tarball/master#egg=openstereo

Mint Cinnamon
-------------

First install pyqt5, pip and setuptools from the distribution repository::

    $ sudo apt install python3-pyqt5 python3-pip python3-setuptools

Then install wheel using pip::

    $ pip3 install wheel

Once that is done, install OpenStereo from `github`_ using pip3::

    $ pip3 install https://github.com/endarthur/os/tarball/master#egg=openstereo

Fedora
------

First install pyqt5::

    $ sudo yum install python3-qt5

Once that is done, install OpenStereo from `github`_ using pip3::

    $ sudo pip3 install https://github.com/endarthur/os/tarball/master#egg=openstereo

openSUSE
--------

First install pyqt5::

    $ sudo zypper install python3-qt5

Once that is done, install OpenStereo from `github`_ using pip3::

    $ sudo pip3 install https://github.com/endarthur/os/tarball/master#egg=openstereo

Other Linux distros
-------------------

In general, install pyqt5 for python3, either from the distro repositories or
PyPI. PyQT5 is not listed as a requirement on OpenStereo's setup file, as its
installation may fail in some cases, though the other requirements can usually
be installed automatically without any issues.

After installing pyqt5, install openstereo using pip3 (to force it to use
python3)::

    $ pip3 install git+https://github.com/endarthur/os#egg=openstereo

You may either have to run this command with sudo or by adding the ``--user``
flag to pip3. In case you use the flag, you'll have to run OpenStereo using::

    $ python3 -m openstereo

Instead of just ``openstereo``, though you can add this as an alias to your
.bash_aliases file.

From PyPI
---------

At the command line::

    pip install git+https://github.com/endarthur/os#egg=openstereo

Additionally, install PyQt5 from PyPI if needed (for python 2.7, use package
python-qt5 instead).
