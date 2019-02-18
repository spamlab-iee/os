# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_files\item_table.ui'
#
# Created by: PyQt5 UI code generator 5.6
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(279, 460)
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.data_table = QtWidgets.QTableWidget(Dialog)
        self.data_table.setObjectName("data_table")
        self.data_table.setColumnCount(0)
        self.data_table.setRowCount(0)
        self.verticalLayout.addWidget(self.data_table)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.update_data_button = QtWidgets.QPushButton(Dialog)
        self.update_data_button.setObjectName("update_data_button")
        self.horizontalLayout.addWidget(self.update_data_button)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.toolButton_2 = QtWidgets.QToolButton(Dialog)
        self.toolButton_2.setObjectName("toolButton_2")
        self.horizontalLayout.addWidget(self.toolButton_2)
        self.toolButton = QtWidgets.QToolButton(Dialog)
        self.toolButton.setObjectName("toolButton")
        self.horizontalLayout.addWidget(self.toolButton)
        self.toolButton_3 = QtWidgets.QToolButton(Dialog)
        self.toolButton_3.setObjectName("toolButton_3")
        self.horizontalLayout.addWidget(self.toolButton_3)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Item Table"))
        self.update_data_button.setText(_translate("Dialog", "Update Data"))
        self.toolButton_2.setText(_translate("Dialog", "w"))
        self.toolButton.setText(_translate("Dialog", "sc"))
        self.toolButton_3.setText(_translate("Dialog", "ff"))

