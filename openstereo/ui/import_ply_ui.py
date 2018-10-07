# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_files\import_ply.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(314, 327)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtWidgets.QLabel(Dialog)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.verticalLayout_2.addLayout(self.horizontalLayout)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.color_list = QtWidgets.QListWidget(Dialog)
        self.color_list.setObjectName("color_list")
        self.horizontalLayout_3.addWidget(self.color_list)
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.add_color_button = QtWidgets.QPushButton(Dialog)
        self.add_color_button.setObjectName("add_color_button")
        self.verticalLayout.addWidget(self.add_color_button)
        self.remove_color_button = QtWidgets.QPushButton(Dialog)
        self.remove_color_button.setObjectName("remove_color_button")
        self.verticalLayout.addWidget(self.remove_color_button)
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem1)
        self.horizontalLayout_3.addLayout(self.verticalLayout)
        self.verticalLayout_2.addLayout(self.horizontalLayout_3)
        self.check_separate = QtWidgets.QCheckBox(Dialog)
        self.check_separate.setChecked(True)
        self.check_separate.setObjectName("check_separate")
        self.verticalLayout_2.addWidget(self.check_separate)
        self.check_export_ply = QtWidgets.QCheckBox(Dialog)
        self.check_export_ply.setObjectName("check_export_ply")
        self.verticalLayout_2.addWidget(self.check_export_ply)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem2)
        self.ok_button = QtWidgets.QPushButton(Dialog)
        self.ok_button.setObjectName("ok_button")
        self.horizontalLayout_2.addWidget(self.ok_button)
        self.cancel_button = QtWidgets.QPushButton(Dialog)
        self.cancel_button.setObjectName("cancel_button")
        self.horizontalLayout_2.addWidget(self.cancel_button)
        self.verticalLayout_2.addLayout(self.horizontalLayout_2)

        self.retranslateUi(Dialog)
        self.ok_button.clicked.connect(Dialog.accept)
        self.cancel_button.clicked.connect(Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Import Planes from Mesh"))
        self.label.setText(_translate("Dialog", "Painted Colors:"))
        self.add_color_button.setText(_translate("Dialog", "Add Color"))
        self.remove_color_button.setText(_translate("Dialog", "Remove"))
        self.check_separate.setText(_translate("Dialog", "Export each color to a separate file"))
        self.check_export_ply.setText(_translate("Dialog", "Export 3d model of resulting planes"))
        self.ok_button.setText(_translate("Dialog", "OK"))
        self.cancel_button.setText(_translate("Dialog", "Cancel"))

