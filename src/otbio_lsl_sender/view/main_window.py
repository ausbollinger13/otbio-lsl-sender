from PySide6.QtWidgets import (
    QMainWindow, 
    QWidget, 
)

from PySide6.QtGui import QFont

class MainWindow(QMainWindow):
    """
    Main application window for H-Reflex Conditioning with input fields for experimental variables
    and plots to visualize trial and live EMG data.
    """

    #region Constructor

    def __init__(self) -> None:
        super().__init__()

        # Set up window title and size
        self.setWindowTitle("TxBDC OTBioelettronica Quattrocento LSL Sender")
        self.resize(900, 600)  # Increased the width of the window

        #Create some fonts that will be used for the ui elements
        self._regular_font: QFont = QFont("Arial", 12)
        self._bold_font: QFont = QFont("Arial", 12, QFont.Bold)
        self._large_bold_font: QFont = QFont("Arial", 20, QFont.Bold)

        # Set the central widget for the main window layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

    #endregion

    #region Overrides

    def closeEvent(self, event):
        '''
        This method is called when the user attempts to close the application window.
        This method handles gracefully shutting the application down.
        '''

        #Accept the event
        event.accept()

    #endregion
