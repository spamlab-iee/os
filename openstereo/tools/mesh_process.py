from PyQt5 import QtWidgets, QtGui

from openstereo.ui.import_ply_ui import Ui_Dialog as import_ply_Ui_Dialog


class MeshDialog(QtWidgets.QDialog, import_ply_Ui_Dialog):
    default_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

    def __init__(self, parent=None):
        super(MeshDialog, self).__init__(parent)
        self.setupUi(self)
        for color in self.default_colors:
            self.add_color_to_list(color)
        self.add_color_button.clicked.connect(self.add_color)
        self.remove_color_button.clicked.connect(self.remove_color)

    def add_color_to_list(self, color):
        item = QtWidgets.QListWidgetItem(",".join(str(c) for c in color),
                                         self.color_list)
        item.setForeground(QtGui.QColor(*color))

    def add_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.add_color_to_list((color.red(), color.green(), color.blue()))

    # http://stackoverflow.com/a/7486225/1457481
    def remove_color(self):
        current_item = self.color_list.currentItem()
        self.color_list.takeItem(self.color_list.row(current_item))

    @property
    def colors(self):
        return [
            tuple(
                [int(c) for c in
                 self.color_list.item(i).text().split(',')] + [255, ])
            for i in range(self.color_list.count())]
