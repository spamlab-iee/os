An OpenStereo Tutorial
======================

Open the program either from your start menu or from command line as either::

    python -m openstereo

Or::

    openstereo

Optionally, an ``.openstereo`` :ref:`project file <project-files>` can be opened::

    openstereo example_project.openstereo

From that, you are brought to the main window:

.. image:: images/os_mainwindow.png

From the File menu you can open or save projects and import files. The quickest
way to open a simple data file is using the specific import actions. for
example, ``Import Plane Data (DD)``:

.. image:: images/os_file_import_plane.png

Download ``tocher_header.csv`` from the `example data`_ directory inside the 
repository and select it after clicking this option. After loading, either
click ``Plot`` or press ``Ctrl+P`` on your keyboard to view the poles of this
example:

.. _example data: https://github.com/endarthur/os/tree/master/example_data

.. image:: images/os_tocher_poles.png

It is also possible to plot the great circles, eigenvectors and contours of
a planar dataset. Click on the check boxes of these options under the
``(P)tocher_header.txt`` item on the data tree and press plot to get a very
busy view of the data:

.. image:: images/os_tocher_full.png

Disable the Great Circles option for now and right click on the Tocher item(or
over any of its options) to get its context menu:

.. image:: images/os_tocher_context.png

You can rename, delete, reorder, reload and change the display properties of
the item using this menu. Click on ``Properties`` to do so:

.. image:: images/os_tocher_props_projection.png
    :align:   center

Most plot options for the Project plot tab on the main window are located on
this first tab, with the exception of contour plots. Try to change some
options, as the color and size of the poles on the top left group, disable
the pole and great circle of the first and second eigenvectors and change the
color of the pole and great circle of the third eigenvector. If you
click ``OK`` the changes will be accepted and the dialog will close, but if
instead you click ``Apply`` the dialog  will be kept open.

You can keep the dialog open and still interact with OpenStereo, even opening
the properties dialog  of multiple items. Press apply and see the changes on
the plot:

.. image:: images/os_tocher_poles_changed.png

On the Contours tab of the properties dialog you may change the many different
related options:

.. image:: images/os_tocher_props_contours.png
    :align:   center

Try a few different graphic options for the contours, as changing the fill
contours gradient to something like ``Greens_r``. You may also change the
number of contours and the way they are built. In the right side, it is
possible to configure with witch method the contouring will be performed,
either as a count of number of poles inside a small circle around each node
or by exponentially smoothing each point to every node using the Fisher 
distribution.

The parameter K controls how smooth the contribution of each point will be.
Smaller values of K will smooth more, while larger ones will make each point
contribute only to a small area around it.

In general you'll have to try a few different options for your dataset to find
the best smoothing coefficient. To help with that, OpenStereo includes two
published methods to estimate good parameters. Robin & Jowett (1986) is very
quick, as it calculates the recommended K based only on the number of poles,
while Diggle & Fisher (1985) perform an optimization using cross validation
to find which parameter best represents your data. Change the K parameter to
50 and plot the results:

.. image:: images/os_tocher_contours_k50.png

Skip to the ``General`` tab on the properties dialog. Here you may change which
of the plot items will be added to the projection legend, and if desired,
specify a legend text for each plot item instead of the default by writing
on the text box besides each option.

It is possible to use parameters from your dataset on the legend text. Check
the :ref:`legend reference <legend>` for how to use this feature. Specify the
Pole legend for the third eigenvector as ``pole to the fitted girdle``, and its
great circle legend as::

    fitted girdle ({data.eigenvectors_sphere[0]})

In most cases you don't need to use the import dialog directly. Download and
open the ``qplot.txt`` dataset using the ``Import Line Data (Trend)``.

..
    .. image:: images/os_import.png
        :align:   center

    If you try to open a CSV file, as is the case, OpenStereo will automatically
    try to detect the dialect used, mainly the delimiter. Following that it will
    check if your dataset contains a header. In this example, the separator is
    comma and it contains a header, as detected. You may change any of these
    options if you think they are wrong.

    By default, it will interpret your file as planes, and try to guess from the
    header which columns represent dip direction and dip, or take the first and
    second columns, respectively. Press ``OK`` to load the data and either click
    ``Plot`` or press ``Ctrl+P`` on your keyboard to view the poles of this
    example: