OpenStereo Reference
====================

.. _project-files:

Project Files
-------------

Project files in OpenStereo have the extension ``.openstereo``, and are
zip files containing json files and (in case of a packed project) data
files.

.. _legend:

Legend
------

When specifying the legend of a plot item it is possible to get parameters
of your data automatically using the :pep:`3101` format strings specification.
The auttitude container object of the dataset is passed as ``data``, and any
of its parameters can be recalled using this.

..
    This table summarizes the available information: