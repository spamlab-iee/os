if __name__ == '__main__':
    import sys
    from os import path

    from openstereo.os_base import Main
    from PyQt5 import QtWidgets

    app = QtWidgets.QApplication(sys.argv)
    main = Main()
    main.add_plots()
    if len(sys.argv) > 1:
        main.open_project(sys.argv[1])
        main.current_project = path.abspath(sys.argv[1])
        main.set_title()
    main.show()
    sys.exit(app.exec_())
