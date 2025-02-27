import keyboard
from datetime import datetime
from otbio_lsl_sender.model.otbio400_reader import OTBioelettronica400_Reader

if __name__ == "__main__":

    reader = OTBioelettronica400_Reader()
    reader.StartCommunication()

    dt_start: datetime = datetime.now()

    while True:  
        dt_end: datetime = datetime.now()
        if (dt_end - dt_start).total_seconds() >= 10:
            dt_start = dt_end
            print("Main thread pulse: " + datetime.now().isoformat())
        #Check if the user pressed a key
        try:
            if keyboard.is_pressed('q'): 
                break  # finishing the loop
        except:
            pass