from datetime import datetime

class SessionMessage (object):

    #region Constructor

    def __init__(self, message_text):
        #Initialize variable to hold the datetime of the message
        self.message_datetime: datetime = datetime.now()

        #Initialize variable to hold the message text
        self.message_text: str = message_text

    #endregion

    #region Properties

    @property
    def formatted_message_text (self) -> str:
        message_time_text: str = self.message_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        return f"<b>[{message_time_text}]</b> {self.message_text}"

    #endregion

