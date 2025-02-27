from PySide6.QtWidgets import (
    QMainWindow, 
    QLabel, 
    QVBoxLayout, 
    QWidget, 
    QHBoxLayout, 
    QPushButton, 
    QLineEdit, 
    QComboBox, 
    QSizePolicy,
    QFrame,
    QGridLayout,
    QPlainTextEdit,
    QMessageBox
)

from PySide6.QtGui import QFont
from PySide6.QtCore import QThreadPool, QTimer
from PySide6 import QtCore

from ..model.otbio400_reader import OTBioelettronica400_Reader
from ..model.session_message import SessionMessage

class MainWindow(QMainWindow):
    """
    Main application window for OTBio LSL Sender application.
    """

    #region Constructor

    def __init__(self) -> None:
        super().__init__()

        #Create an instance of the OTBio reader
        self._otbio_reader: OTBioelettronica400_Reader = OTBioelettronica400_Reader()

        # Initialize a set of messages that will be displayed in the session message box
        self._session_messages: list[SessionMessage] = []

        #Initialize a timer
        self._background_timer: QTimer = QTimer()
        self._background_timer.timeout.connect(self._check_background_thread_message_queue)

        # Set up window title and size
        self.setWindowTitle("TxBDC OTBioelettronica 400 LSL Sender")
        self.resize(900, 400)  # Increased the width of the window

        #Create some fonts that will be used for the ui elements
        self._regular_font: QFont = QFont("Arial", 12)
        self._bold_font: QFont = QFont("Arial", 12, QFont.Bold)
        self._large_bold_font: QFont = QFont("Arial", 20, QFont.Bold)

        # Main layout container
        self._layout: QGridLayout = QGridLayout()
        self._layout.setRowStretch(0, 1)
        self._layout.setRowStretch(1, 0)

        #Create a text edit control to hold messages to the user
        self._session_message_box = QPlainTextEdit()
        self._session_message_box.setFont(self._regular_font)
        self._session_message_box.setReadOnly(True)
        self._session_message_box.setFixedWidth(850)

        #Create a start/stop button
        self._start_stop_button = QPushButton("Start")
        self._start_stop_button.setFont(self._large_bold_font)
        self._start_stop_button.setFixedWidth(550)
        self._start_stop_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
        self._start_stop_button.setStyleSheet('QPushButton {color: green;}')
        self._start_stop_button.setEnabled(True)
        self._start_stop_button.clicked.connect(self._on_start_stop_button_clicked)

        self._layout.addWidget(self._session_message_box, 0, 0, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        self._layout.addWidget(self._start_stop_button, 1, 0, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)

        # Set the central widget for the main window layout
        central_widget = QWidget()
        central_widget.setLayout(self._layout)
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

    #region Event handlers

    def _on_start_stop_button_clicked (self) -> None:
        #Check to see if the OTBio Reader is currently communicating
        if (self._otbio_reader.communication):
            #If it IS currently communicating...
            self._session_messages.append(SessionMessage("Stopping..."))
            self._update_session_messages()

            #Stop the communication
            self._otbio_reader.StopCommunication()

            #Stop the timer
            self._background_timer.stop()

            #Change the text and the text color of the start/stop button
            self._start_stop_button.setText("Start")
            self._start_stop_button.setStyleSheet('QPushButton {color: green;}')

            self._session_messages.append(SessionMessage("Stopped"))
            self._update_session_messages()

            pass
        else:
            #If it is NOT currently communicating...
            self._session_messages.append(SessionMessage("Starting..."))
            self._update_session_messages()

            try:
                #Start communication
                self._otbio_reader.StartCommunication()

                #Change the text and the text color of the start/stop button
                self._start_stop_button.setText("Stop")
                self._start_stop_button.setStyleSheet('QPushButton {color: red;}')

                self._session_messages.append(SessionMessage("Started"))
                self._update_session_messages()

                self._background_timer.start(1000)
            except Exception as e:
                #If an error was encountered, then show the error to the user
                self._session_messages.append(SessionMessage("Error while attempting to start!"))
                if hasattr(e, 'message'):
                    self._session_messages.append(SessionMessage(f"Error: {e.message}"))
                else:
                    self._session_messages.append(SessionMessage(f"Error: {e}"))
                self._update_session_messages()

            pass

    #endregion

    #region Private methods

    def _check_background_thread_message_queue (self) -> None:
        while not self._otbio_reader.thread_out_messages.empty():
            msg: SessionMessage = self._otbio_reader.thread_out_messages.get()
            self._session_messages.append(msg)
            self._update_session_messages()

    def _update_session_messages (self) -> None:
        self._session_message_box.appendHtml(self._session_messages[-1].formatted_message_text)

        pass

    def _clear_session_messages (self) -> None:
        #Clear the session messages
        self._session_messages.clear()

        #Clear the UI edit box
        self._session_message_box.clear()

    #endregion