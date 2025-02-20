import socket
import numpy as np
import time
import threading
from datetime import datetime

class OTBioelettronica400_Reader:

    #region Some options

    FRAMES_PER_SECOND = 16

    SAMPLING_FREQUENCY_OPTIONS: dict[int, int] = {
        512: 0,
        2048: 8,
        5120: 16,
        10240: 24
    }

    NUMBER_OF_CHANNEL_OPTIONS: dict[int, int] = {
        120: 0,
        216: 2,
        312: 4,
        408: 6
    }

    #endregion

    #region Constructor

    def __init__(self):

        self.ConfString: list = []

        self.AnOutSource: int = 9  # Source input for analog output
        self.AnOutChan: int = 0    # Channel for analog output
        self.AnOutGain = int('00000000', 2)
        self.Decim: int = 64
        
        self.SamplingFrequency: int = 5120
        self.NumberOfChannels: int = 120

        self.SamplingFrequencyCode: int = OTBioelettronica400_Reader.SAMPLING_FREQUENCY_OPTIONS[self.SamplingFrequency]
        self.NumberOfChannelsCode: int = OTBioelettronica400_Reader.NUMBER_OF_CHANNEL_OPTIONS[self.NumberOfChannels]

        self.IpAddress: str = '169.254.1.10'
        self.TCPPort: int = 23456
        self.GainFactor = 5 / 2**16 / 150 * 1000  # Provide amplitude in mV
        self.AuxGainFactor = 5 / 2**16 / 0.5      # Gain factor to convert Aux Channels in V

        pass

    #endregion

    #region Methods

    def StartCommunication (self) -> None:
        #Create the command that we will send to the OtBioelettronica device
        self._CreateCommand()

        # Open the TCP socket
        self.tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpSocket.connect((self.IpAddress, self.TCPPort))

        # Send the configuration to Quattrocento
        self.tcpSocket.sendall(bytearray(self.ConfString))

        self.ConfString[0] = self.ConfString[0] + int('00100000', 2)  # Force the trigger to go high (bit 5)
        self.ConfString[39] = self._CRC8(self.ConfString, 39)  # Estimates the new CRC
        time.sleep(1)
        self.tcpSocket.sendall(bytearray(self.ConfString))

        #Set the "communication" boolean flag to True, indicating that we are now receiving data
        self.communication: bool = True

        #Instantiate a thread to receive the data
        self.data_receiver_thread = threading.Thread(target=self._receive_data)
        self.data_receiver_thread.start()

    def StopCommunication (self) -> None:
        # Stop data transfer
        self.communication = False

        # Stop data transfer command
        self.ConfString[0] = int('10000000', 2)          # First byte that stops the data transfer
        self.ConfString[39] = self._CRC8(self.ConfString, 39)  # Estimates the new CRC
        self.tcpSocket.sendall(bytearray(self.ConfString))

        # Close the communication
        self.tcpSocket.close()        

    #endregion

    #region Private methods

    def _CreateCommand (self) -> None:

        # Create the command to send to Quattrocento
        self.ConfString = [0] * 40
        self.ConfString[0] = int('10000000', 2) + self.Decim + self.SamplingFrequencyCode + self.NumberOfChannelsCode + 1
        self.ConfString[1] = self.AnOutGain + self.AnOutSource
        self.ConfString[2] = self.AnOutChan
        # -------- IN 1 --------
        self.ConfString[3] = 0
        self.ConfString[4] = 0
        self.ConfString[5] = int('00010100', 2)
        # -------- IN 2 --------
        self.ConfString[6] = 0
        self.ConfString[7] = 0
        self.ConfString[8] = int('00010100', 2)
        # -------- IN 3 --------
        self.ConfString[9] = 0
        self.ConfString[10] = 0
        self.ConfString[11] = int('00010100', 2)
        # -------- IN 4 --------
        self.ConfString[12] = 0
        self.ConfString[13] = 0
        self.ConfString[14] = int('00010100', 2)
        # -------- IN 5 --------
        self.ConfString[15] = 0
        self.ConfString[16] = 0
        self.ConfString[17] = int('00010100', 2)
        # -------- IN 6 --------
        self.ConfString[18] = 0
        self.ConfString[19] = 0
        self.ConfString[20] = int('00010100', 2)
        # -------- IN 7 --------
        self.ConfString[21] = 0
        self.ConfString[22] = 0
        self.ConfString[23] = int('00010100', 2)
        # -------- IN 8 --------
        self.ConfString[24] = 0
        self.ConfString[25] = 0
        self.ConfString[26] = int('00010100', 2)
        # -------- MULTIPLE IN 1 --------
        self.ConfString[27] = 0
        self.ConfString[28] = 0
        self.ConfString[29] = int('00010100', 2)
        # -------- MULTIPLE IN 2 --------
        self.ConfString[30] = 0
        self.ConfString[31] = 0
        self.ConfString[32] = int('00010100', 2)
        # -------- MULTIPLE IN 3 --------
        self.ConfString[33] = 0
        self.ConfString[34] = 0
        self.ConfString[35] = int('00010100', 2)
        # -------- MULTIPLE IN 4 --------
        self.ConfString[36] = 0
        self.ConfString[37] = 0
        self.ConfString[38] = int('00010100', 2)
        # ---------- CRC8 ----------
        self.ConfString[39] = self._CRC8(self.ConfString, 39)

        pass

    def _CRC8(self, Vector, Len):
        crc = 0
        j = 0

        while Len > 0:
            Extract = Vector[j]
            for i in range(8, 0, -1):
                Sum = crc % 2 ^ Extract % 2
                crc //= 2

                if Sum > 0:
                    str_list = [0]* 8
                    a = format(crc, '08b')
                    b = format(140, '08b')
                    
                    for k in range(8):
                        str_list[k] = int(a[k] != b[k])

                    crc = int(''.join(map(str, str_list)), 2)

                Extract //= 2

            Len -= 1
            j += 1

        return crc

    def _receive_data(self):
        #Instantiate a byte buffer to hold data as it comes in from the device
        buffer = b''

        #Define the number of bytes we expect to receive each frame
        expected_bytes = 2 * int((self.NumberOfChannels * self.SamplingFrequency) / OTBioelettronica400_Reader.FRAMES_PER_SECOND)

        #Track some stats
        frame_count: int = 0
        samples_streamed: int = 0
        dt_start: datetime = datetime.now()
        dt_end: datetime = dt_start

        #Loop infinitely
        while self.communication:
            dt_end = datetime.now()
            if (dt_end - dt_start).total_seconds() >= 1.0:
                dt_start = dt_end
                print(f"Samples per second = {samples_streamed}, frames per second = {frame_count}")
                samples_streamed = 0
                frame_count = 0

            try:
                #Pull in the expected number of bytes
                while len(buffer) < expected_bytes:
                    buffer += self.tcpSocket.recv(expected_bytes - len(buffer))

                #Extract the first N bytes, where N = expected_bytes. Place into the data variable.
                samples_streamed += expected_bytes
                frame_count += 1

                data = buffer[:expected_bytes]
                buffer = buffer[expected_bytes:]

                #Reshape the data array based on the number of channels we are using
                new_data = np.frombuffer(data, dtype=np.int16).reshape(int(self.SamplingFrequency / OTBioelettronica400_Reader.FRAMES_PER_SECOND), self.NumberOfChannels)
                data_length = new_data.shape[0]

                if samples_streamed == expected_bytes:
                    print(new_data.shape)

            except Exception as e:
                print(f"An error occurred: {e}")
                break

    #endregion

#def update_plot():
#    latest_data = np.roll(data_buffer, -buffer_index, axis=0)
#    for plot_index, channel_index in enumerate(PlotChan):
#        curves[plot_index].setData((latest_data[:, channel_index]) * GainFactor + offset * plot_index)

if __name__ == "__main__":
    import keyboard
    from datetime import datetime

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

