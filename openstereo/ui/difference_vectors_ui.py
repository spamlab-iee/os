# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_files\difference_vectors.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(227, 193)
        self.verticalLayout = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.A = QtWidgets.QComboBox(Dialog)
        self.A.setObjectName("A")
        self.verticalLayout.addWidget(self.A)
        self.formLayout = QtWidgets.QFormLayout()
        self.formLayout.setObjectName("formLayout")
        self.do_percentage = QtWidgets.QRadioButton(Dialog)
        self.do_percentage.setChecked(True)
        self.do_percentage.setObjectName("do_percentage")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.do_percentage)
        self.percentage_largest = QtWidgets.QDoubleSpinBox(Dialog)
        self.percentage_largest.setMaximum(100.0)
        self.percentage_largest.setProperty("value", 100.0)
        self.percentage_largest.setObjectName("percentage_largest")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.percentage_largest)
        self.do_n = QtWidgets.QRadioButton(Dialog)
        self.do_n.setObjectName("do_n")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.do_n)
        self.n_largest = QtWidgets.QLineEdit(Dialog)
        self.n_largest.setObjectName("n_largest")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.n_largest)
        self.verticalLayout.addLayout(self.formLayout)
        spacerItem = QtWidgets.QSpacerItem(20, 61, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem1)
        self.ok_button = QtWidgets.QPushButton(Dialog)
        self.ok_button.setObjectName("ok_button")
        self.horizontalLayout_2.addWidget(self.ok_button)
        self.cancel_button = QtWidgets.QPushButton(Dialog)
        self.cancel_button.setObjectName("cancel_button")
        self.horizontalLayout_2.addWidget(self.cancel_button)
        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.retranslateUi(Dialog)
        self.ok_button.clicked.connect(Dialog.accept)
        self.cancel_button.clicked.connect(Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Difference Vectors"))
        self.do_percentage.setText(_translate("Dialog", "% largest"))
        self.do_n.setText(_translate("Dialog", "n largest"))
        self.ok_button.setText(_translate("Dialog", "OK"))
        self.cancel_button.setText(_translate("Dialog", "Cancel"))

