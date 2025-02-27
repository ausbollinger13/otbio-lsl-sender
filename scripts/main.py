import sys
from PySide6 import QtWidgets
from otbio_lsl_sender.view.main_window import MainWindow

def main () -> None:
    #Create the QT application
    app = QtWidgets.QApplication(sys.argv)

    #Instantiate the MainWindow object
    window = MainWindow()

    #Display the main window
    window.show()

    #Turn control over to QT's main loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()



