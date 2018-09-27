from PyQt5 import QtWidgets, QtCore, QtGui


# http://stackoverflow.com/a/20295812/1457481
def waiting_effects(function):
    def new_function(*args, **kwargs):
        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.WaitCursor)
        )
        try:
            return function(*args, **kwargs)
        except Exception as e:
            raise e
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    return new_function
