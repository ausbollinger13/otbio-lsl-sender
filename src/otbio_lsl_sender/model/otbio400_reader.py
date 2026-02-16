import socket
import numpy as np
import time
import threading
from datetime import datetime

from pylsl import StreamInfo, StreamOutlet, local_clock
from queue import Queue

import pygame

from .session_message import SessionMessage

class OTBioelettronica400_Reader:

    #region Some options

    DEBUG_MODE: bool = False

    # CRITICAL FOR TTL LATENCY: Higher FPS = smaller chunks = lower latency
    # At 5120 Hz: 16 FPS = 320 samples/chunk = 62.5ms max latency
    #             32 FPS = 160 samples/chunk = 31.25ms max latency  
    #             64 FPS = 80 samples/chunk = 15.6ms max latency
    # Trade-off: Higher FPS increases CPU/network overhead slightly
    FRAMES_PER_SECOND = 128  # Increased from 16 to minimize TTL latency

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

    # TTL channel configuration (channels 385-400, 0-indexed: 384-399)
    TTL_START_CHANNEL = 384  # 0-indexed (channels 385-400 in 1-indexed)
    TTL_END_CHANNEL = 399    # 0-indexed
    TTL_HIGH_THRESHOLD = 1000    # mV - signal above this is considered HIGH (5V ≈ 5000mV)
    TTL_LOW_THRESHOLD = 100      # mV - signal below this is considered LOW (0V)
    TTL_CHANNELS = ['IN1', 'IN2', 'IN3', 'IN4', 'IN5', 'IN6', 'IN7', 'IN8',
                   'IN9', 'IN10', 'IN11', 'IN12', 'IN13', 'IN14', 'IN15', 'IN16']
    
    # Latency compensation: estimate of network + processing delay in seconds
    # Adjust this based on your system's actual latency measurements
    TTL_LATENCY_COMPENSATION = 0.000  # seconds (0ms default, tune as needed)

    #endregion

    #region Constructor

    def __init__(self):

        self.communication: bool = False
        self.thread_out_messages: Queue = Queue()

        self.ConfString: list = []

        self.AnOutSource: int = 9  # Source input for analog output
        self.AnOutChan: int = 0    # Channel for analog output
        self.AnOutGain = int('00000000', 2)
        self.Decim: int = 64
        
        self.SamplingFrequency: int = 5120
        self.NumberOfChannels: int = 408

        self.SamplingFrequencyCode: int = OTBioelettronica400_Reader.SAMPLING_FREQUENCY_OPTIONS[self.SamplingFrequency]
        self.NumberOfChannelsCode: int = OTBioelettronica400_Reader.NUMBER_OF_CHANNEL_OPTIONS[self.NumberOfChannels]

        self.IpAddress: str = '169.254.1.10'
        self.TCPPort: int = 23456
        self.GainFactor = 5 / 2**16 / 150 * 1000  # Provide amplitude in mV
        self.AuxGainFactor = 5 / 2**16 / 0.5      # Gain factor to convert Aux Channels in V

        self.error_count: int = 0
        self.first_error_time: datetime = datetime.min
        self.most_recent_error_time: datetime = datetime.min

        # TTL detection state tracking - improved for professional edge detection
        self.ttl_previous_raw_values = np.zeros(16, dtype=np.int16)  # Track raw values
        self.ttl_current_states = np.zeros(16, dtype=bool)  # Current digital states
        self.ttl_previous_states = np.zeros(16, dtype=bool)  # Previous digital states
        self.ttl_enabled = True  # Flag to enable/disable TTL detection
        self.ttl_debug_counter = 0  # For periodic debugging
        
        # Professional TTL detection parameters - optimized for precision
        self.TTL_GainFactor = (5.0 / 32768.0) * 1000  # Convert to mV
        self.TTL_HIGH_VOLTAGE = 1500.0  # mV - lowered for better detection
        self.TTL_LOW_VOLTAGE = -500.0   # mV - account for negative baseline
        
        # Sample timing for precise marker placement
        self.sample_period = 1.0 / self.SamplingFrequency  # Time per sample
        self.samples_per_chunk = int(self.SamplingFrequency / OTBioelettronica400_Reader.FRAMES_PER_SECOND)
        
        # Track sample count for precise timing calculation
        self.total_samples_processed = 0
        self.stream_start_time = None
        
        # Only monitor IN1 initially - can be expanded later
        self.active_ttl_channels = [0]  # Index 0 = IN1

        pass

    #endregion

    #region Methods

    def StartCommunication (self) -> None:
        #Create the command that we will send to the OtBioelettronica device
        self._CreateCommand()

        # Open the TCP socket
        self.tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpSocket.connect((self.IpAddress, self.TCPPort))
        self.tcpSocket.settimeout(5)

        # Send the configuration to Quattrocento
        self.tcpSocket.sendall(bytearray(self.ConfString))

        self.ConfString[0] = self.ConfString[0] + int('00100000', 2)  # Force the trigger to go high (bit 5)
        self.ConfString[39] = self._CRC8(self.ConfString, 39)  # Estimates the new CRC
        time.sleep(1)
        self.tcpSocket.sendall(bytearray(self.ConfString))

        #Set the "communication" boolean flag to True, indicating that we are now receiving data
        self.communication = True

        #Instantiate a thread to receive the data
        self.data_receiver_thread = threading.Thread(target=self._receive_data)
        self.data_receiver_thread.start()

    def StopCommunication (self) -> None:
        # Stop data transfer
        self.communication = False

        try:
            # Stop data transfer command
            self.ConfString[0] = int('10000000', 2)          # First byte that stops the data transfer
            self.ConfString[39] = self._CRC8(self.ConfString, 39)  # Estimates the new CRC
            
            # Check if socket is still connected before sending
            if hasattr(self, 'tcpSocket') and self.tcpSocket:
                self.tcpSocket.sendall(bytearray(self.ConfString))
        except Exception as e:
            # If socket is already disconnected, that's fine
            print(f"Warning during stop communication: {e}")

        # Close the communication
        try:
            if hasattr(self, 'tcpSocket') and self.tcpSocket:
                self.tcpSocket.close()
        except Exception as e:
            print(f"Warning during socket close: {e}")
        
        # Wait for data receiver thread to finish
        if hasattr(self, 'data_receiver_thread') and self.data_receiver_thread.is_alive():
            self.data_receiver_thread.join(timeout=5.0)  # Wait up to 5 seconds

    def _is_socket_connected(self) -> bool:
        """Check if the TCP socket is still connected"""
        try:
            if not hasattr(self, 'tcpSocket') or not self.tcpSocket:
                return False
            
            # Try to send a zero-length message to check connection
            self.tcpSocket.send(b'', socket.MSG_DONTWAIT)
            return True
        except (socket.error, AttributeError):
            return False        

    def set_ttl_thresholds(self, high_threshold_mv: float, low_threshold_mv: float) -> None:
        """Set the TTL detection thresholds in millivolts
        
        Args:
            high_threshold_mv: Voltage above which signal is considered HIGH (default: 2500mV for 5V logic)
            low_threshold_mv: Voltage below which signal is considered LOW (default: 500mV for 0V logic)
        """
        OTBioelettronica400_Reader.TTL_HIGH_THRESHOLD = high_threshold_mv
        OTBioelettronica400_Reader.TTL_LOW_THRESHOLD = low_threshold_mv
        self.thread_out_messages.put(SessionMessage(f"TTL thresholds set to HIGH: {high_threshold_mv}mV, LOW: {low_threshold_mv}mV"))

    def enable_ttl_detection(self, enabled: bool) -> None:
        """Enable or disable TTL detection"""
        self.ttl_enabled = enabled
        status = "enabled" if enabled else "disabled"
        self.thread_out_messages.put(SessionMessage(f"TTL detection {status}"))
    
    def set_ttl_latency_compensation(self, latency_ms: float) -> None:
        """Set latency compensation for TTL markers
        
        Args:
            latency_ms: Latency in milliseconds to subtract from marker timestamps
                       Positive values shift markers earlier in time
                       Use this to compensate for network/processing delays
        """
        OTBioelettronica400_Reader.TTL_LATENCY_COMPENSATION = latency_ms / 1000.0
        self.thread_out_messages.put(SessionMessage(f"TTL latency compensation set to {latency_ms:.2f}ms"))
    
    def get_ttl_chunk_latency_ms(self) -> float:
        """Get the maximum latency introduced by chunk-based processing
        
        Returns:
            Maximum latency in milliseconds (depends on chunk size)
        """
        chunk_size = self.SamplingFrequency / OTBioelettronica400_Reader.FRAMES_PER_SECOND
        max_latency_ms = (chunk_size / self.SamplingFrequency) * 1000
        return max_latency_ms

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

    def _detect_ttl_events(self, data_chunk: np.ndarray, marker_outlet: StreamOutlet, chunk_timestamp: float) -> None:
        """TTL detection synchronized with EMG data stream using LSL backwards timestamping
        
        CRITICAL for synchronization (LSL best practice):
        - chunk_timestamp represents when the FIRST sample occurred (calculated backwards from 'now')
        - Each sample's timestamp is: chunk_timestamp + (sample_idx / sampling_rate)
        - LSL will assign identical timestamps when push_chunk is called with the same chunk_timestamp
        - This "backwards timestamping" approach eliminates network jitter for maximum accuracy
        
        Args:
            data_chunk: The data chunk containing TTL channels
            marker_outlet: LSL outlet for sending TTL markers
            chunk_timestamp: Calculated timestamp for the first sample in the chunk
        """
        if not self.ttl_enabled:
            return
            
        # Check if we have enough channels for TTL detection
        if self.NumberOfChannels < 385:
            if self.ttl_debug_counter % 1000 == 0:
                self.thread_out_messages.put(SessionMessage(f"Warning: Only {self.NumberOfChannels} channels available, channel 385 not accessible"))
            self.ttl_debug_counter += 1
            return
        
        # Extract TTL channels (we have 16 channels: 384-399)
        ttl_data = data_chunk[:, self.TTL_START_CHANNEL:self.TTL_END_CHANNEL + 1]
        
        # Convert to voltage (mV) using the correct gain factor
        ttl_voltages = ttl_data * self.TTL_GainFactor
        
        # Debug output every 500 frames for IN1
        self.ttl_debug_counter += 1
        if self.ttl_debug_counter % 500 == 0:
            ch1_voltages = ttl_voltages[:, 0]  # IN1
            self.thread_out_messages.put(SessionMessage(
                f"TTL IN1 Debug: Voltage range=[{ch1_voltages.min():.1f}, {ch1_voltages.max():.1f}]mV, "
                f"Mean={ch1_voltages.mean():.1f}mV, Current state={'HIGH' if self.ttl_current_states[0] else 'LOW'}"
            ))
        
        # Process each sample in the chunk
        for sample_idx in range(ttl_data.shape[0]):
            current_voltages = ttl_voltages[sample_idx, :]
            
            # CRITICAL: Use EXACT same timestamp calculation as LSL does internally
            # When push_chunk is called with chunk_timestamp, LSL assigns:
            #   Sample 0: chunk_timestamp
            #   Sample 1: chunk_timestamp + (1 / sampling_rate)
            #   Sample N: chunk_timestamp + (N / sampling_rate)
            # We must use the identical formula for perfect synchronization
            sample_timestamp = chunk_timestamp + (sample_idx / self.SamplingFrequency)
            
            # Process only active TTL channels (currently just IN1)
            for ch_idx in self.active_ttl_channels:
                voltage = current_voltages[ch_idx]
                
                # Simple threshold detection for clean edges
                current_state = voltage > self.TTL_HIGH_VOLTAGE
                previous_state = self.ttl_current_states[ch_idx]
                
                # Detect edges with sample-accurate timing
                if current_state != previous_state:
                    # State changed - determine edge type
                    if current_state and not previous_state:
                        # Rising edge (LOW to HIGH)
                        marker_name = f"TTL_{self.TTL_CHANNELS[ch_idx]}_RISING"
                        edge_type = "RISING"
                    elif not current_state and previous_state:
                        # Falling edge (HIGH to LOW) 
                        marker_name = f"TTL_{self.TTL_CHANNELS[ch_idx]}_FALLING"
                        edge_type = "FALLING"
                    else:
                        continue  # No valid edge
                    
                    try:
                        # Send the marker with timestamp synchronized to EMG stream
                        marker_outlet.push_sample([marker_name], sample_timestamp)
                        
                        # Log the event
                        self.thread_out_messages.put(SessionMessage(
                            f"TTL Event: {marker_name} at sample {self.total_samples_processed + sample_idx} "
                            f"(Voltage: {voltage:.1f}mV, Time: {sample_timestamp:.6f}s)"
                        ))
                        
                        if self.DEBUG_MODE:
                            print(f"TTL Event: {marker_name} at {sample_timestamp:.6f}s")
                            
                    except Exception as e:
                        self.thread_out_messages.put(SessionMessage(f"Error sending TTL marker: {e}"))
                
                # Update current state
                self.ttl_current_states[ch_idx] = current_state

    def _receive_data(self):
        # Create a new StreamInfo object that will tell LSL what our stream contains
        info: StreamInfo = StreamInfo("OTBioelettronica 400", "EMG", self.NumberOfChannels, self.SamplingFrequency, "float32", "myuid34234")

        # Next make an outlet for LSL
        outlet: StreamOutlet = StreamOutlet(info)

        # Create LSL marker stream for TTL events
        marker_info: StreamInfo = StreamInfo("OTBio_TTL_Markers", "Markers", 1, 0, "string", "otbio_ttl_markers")
        marker_outlet: StreamOutlet = StreamOutlet(marker_info)

        # Initialize timing for professional marker accuracy
        self.stream_start_time = local_clock()
        self.total_samples_processed = 0

        #Instantiate a byte buffer to hold data as it comes in from the device
        buffer = b''

        #Define the number of bytes we expect to receive each frame
        expected_bytes = 2 * int((self.NumberOfChannels * self.SamplingFrequency) / OTBioelettronica400_Reader.FRAMES_PER_SECOND)

        #Track some performance metrics
        frame_count: int = 0
        samples_streamed: int = 0
        dt_start: datetime = datetime.now()
        dt_end: datetime = dt_start

        sound_the_alarm: bool = False
        consecutive_errors: int = 0
        max_consecutive_errors: int = 5

        #Loop infinitely
        while self.communication:

            #Keep track of some performance metrics
            dt_end = datetime.now()
            if (dt_end - dt_start).total_seconds() >= 10.0:
                if (OTBioelettronica400_Reader.DEBUG_MODE):
                    print(f"Samples = {samples_streamed}, frames = {frame_count}")
                self.thread_out_messages.put(SessionMessage(f"Samples = {samples_streamed}, frames = {frame_count}"))
                dt_start = dt_end
                samples_streamed = 0
                frame_count = 0

            try:
                #Pull in the expected number of bytes
                dt_recv_start: datetime = datetime.now()
                recv_failed: bool = False
                
                while len(buffer) < expected_bytes and self.communication:
                    try:
                        # Check if socket is still connected
                        remaining_bytes = expected_bytes - len(buffer)
                        data_chunk = self.tcpSocket.recv(remaining_bytes)
                        
                        if not data_chunk:
                            # Socket was closed on the other end
                            raise ConnectionError("Socket connection closed by device")
                            
                        buffer += data_chunk
                        
                    except socket.timeout:
                        # Handle timeout gracefully - this is expected occasionally
                        if (OTBioelettronica400_Reader.DEBUG_MODE):
                            print("Socket timeout occurred, retrying...")
                        continue
                        
                    except (ConnectionError, ConnectionResetError, BrokenPipeError) as conn_err:
                        # Network connection issues
                        self.thread_out_messages.put(SessionMessage(f"Connection error: {conn_err}"))
                        recv_failed = True
                        break
                        
                    except Exception as e:
                        # Other socket errors
                        self.thread_out_messages.put(SessionMessage(f"Socket error: {e}"))
                        recv_failed = True
                        break

                    dt_current: datetime = datetime.now()
                    if ((dt_current - dt_recv_start).total_seconds() >= 15.0):  # Increased timeout
                        recv_failed = True
                        break
                
                if (recv_failed):
                    consecutive_errors += 1
                    self.thread_out_messages.put(SessionMessage(f"Warning: no data received from OTBio device! (Attempt {consecutive_errors}/{max_consecutive_errors})"))
                    
                    # Clear corrupted buffer
                    buffer = b''
                    
                    if consecutive_errors >= max_consecutive_errors:
                        self.thread_out_messages.put(SessionMessage(f"Too many consecutive errors ({consecutive_errors}), stopping stream"))
                        sound_the_alarm = True
                        break
                    
                    # Brief pause before retry
                    time.sleep(0.1)
                    continue
                
                # Reset consecutive error counter on successful data reception
                consecutive_errors = 0

                #Extract the first N bytes, where N = expected_bytes. Place into the data variable.
                samples_streamed += expected_bytes
                frame_count += 1

                data = buffer[:expected_bytes]
                buffer = buffer[expected_bytes:]

                #Reshape the data array based on the number of channels we are using
                try:
                    new_data = np.frombuffer(data, dtype=np.int16).reshape(int(self.SamplingFrequency / OTBioelettronica400_Reader.FRAMES_PER_SECOND), self.NumberOfChannels)
                    data_length = new_data.shape[0]
                    
                    # LSL BEST PRACTICE for minimal jitter: "Backwards timestamping"
                    # Get timestamp NOW (when we're about to push) - this represents the last sample
                    # Then calculate backwards to find when the first sample occurred
                    # This eliminates network jitter since we timestamp from a stable reference point
                    now = local_clock()
                    
                    # Calculate when the FIRST sample in this chunk occurred
                    # If we have N samples, the first one was (N-1) / fs seconds ago
                    chunk_timestamp = now - ((data_length - 1) / self.SamplingFrequency)
                    
                    # Detect TTL events using the calculated chunk start time
                    # Each sample's exact timestamp will be: chunk_timestamp + (sample_idx / fs)
                    self._detect_ttl_events(new_data, marker_outlet, chunk_timestamp)
                    
                    # Update total sample count for tracking
                    self.total_samples_processed += data_length
                    
                except ValueError as ve:
                    self.thread_out_messages.put(SessionMessage(f"Data reshape error: {ve}. Buffer may be corrupted."))
                    # Clear corrupted buffer and continue
                    buffer = b''
                    continue

                #Push the chunk to LSL with proper timing - use push_chunk for better performance
                try:
                    # LSL BEST PRACTICE: Push chunk with backwards-calculated timestamp
                    # chunk_timestamp was calculated as: now - (num_samples - 1) / sampling_rate
                    # This ensures the timestamp is stable and free from network jitter
                    # LSL will timestamp each sample as: chunk_timestamp + sample_idx / sampling_rate
                    outlet.push_chunk(new_data.tolist(), chunk_timestamp)
                except Exception as e:
                    self.thread_out_messages.put(SessionMessage(f"LSL push error: {e}"))
                    # Don't break on LSL errors, just log and continue

            except Exception as e:
                consecutive_errors += 1
                self.thread_out_messages.put(SessionMessage(f"Error in background thread: {e} (Attempt {consecutive_errors}/{max_consecutive_errors})"))
                
                if (OTBioelettronica400_Reader.DEBUG_MODE):
                    print(f"An error occurred: {e}")

                self.error_count += 1
                self.most_recent_error_time = datetime.now()
                if (self.error_count == 1):
                    self.first_error_time = self.most_recent_error_time
                
                # Clear potentially corrupted buffer
                buffer = b''
                
                # Check if we should stop due to too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    self.thread_out_messages.put(SessionMessage(f"Too many consecutive errors ({consecutive_errors}), stopping stream"))
                    sound_the_alarm = True
                    break
                
                # Brief pause before retry
                time.sleep(0.1)
        
        if (sound_the_alarm):
            pygame.mixer.init()
            pygame.mixer.music.load("./assets/loud-emergency-alarm-54635.wav")
            play_count: int = 0
            while(self.communication):
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                play_count += 1

                if (play_count > 100):
                    break
            pygame.mixer.quit()
            pass

    #endregion


