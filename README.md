# OTBio LSL Sender

A small Windows desktop app that streams data from an **OT Bioelettronica Quattrocento** (OTBio 400) amplifier to [Lab Streaming Layer (LSL)](https://labstreaminglayer.org/), with sample-accurate TTL event markers.

It connects to the Quattrocento over TCP and reads all 408 channels at 5120 Hz. It publishes two LSL streams that any LSL-aware tool (LabRecorder, MNE-LSL, custom Python, and so on) can record or consume in real time.

## Features

- **Full-channel EMG streaming:** all 408 Quattrocento channels are pushed to LSL as `float32` in mV.
- **TTL markers on a separate stream:** rising and falling edges on the auxiliary BNC inputs (`IN1`–`IN16`) become string markers such as `TTL_IN1_RISING`.
- **Sample-accurate timestamps:** EMG chunks and TTL markers both use a sample-counter clock (`start_time + samples_processed / fs`). Markers line up with the exact EMG sample where the edge happened, and don't drift with thread scheduling.
- **Low latency:** data is read at 512 frames per second (10-sample chunks at 5120 Hz) and sent with `push_chunk`.
- **Error handling with an audible alarm:** communication and LSL errors appear in the session log. After repeated consecutive failures, the stream stops and an alarm sounds so a stalled recording doesn't go unnoticed.
- **Simple GUI:** a Start/Stop button and a timestamped session message log (PySide6).

## LSL streams

| Stream name            | Type      | Channels | Rate      | Format    |
|------------------------|-----------|----------|-----------|-----------|
| `OTBioelettronica 400` | `EMG`     | 408      | 5120 Hz   | `float32` |
| `OTBio_TTL_Markers`    | `Markers` | 1        | irregular | `string`  |

Marker values have the form `TTL_<input>_RISING` or `TTL_<input>_FALLING`. By default only `IN1` is monitored. To watch other inputs, change `active_ttl_channels` in `OTBioelettronica400_Reader`.

## Requirements

- Windows with Python 3.10+ (developed on Python 3.12)
- An OT Bioelettronica Quattrocento, connected by Ethernet
  - Default device address: `169.254.1.10`, TCP port `23456`
- Python packages: `PySide6`, `numpy`, `pylsl`, `pygame` (see [requirements.txt](requirements.txt))

## Installation

```bash
git clone https://github.com/ausbollinger13/otbio-lsl-sender.git
cd otbio-lsl-sender
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install --editable .
```

## Usage

```bash
python scripts/main.py
```

1. Connect the Quattrocento to the PC and power it on.
2. Launch the app and click **Start**. The app configures the device and starts publishing both LSL streams.
3. Open LabRecorder (or another LSL client), select the `OTBioelettronica 400` and `OTBio_TTL_Markers` streams, and record.
4. Click **Stop** to end the stream.

Run the app from the repository root so it can find `assets/` for the alarm sound.

## Configuration

These settings are at the top of [otbio400_reader.py](src/otbio_lsl_sender/model/otbio400_reader.py):

| Setting                     | Default                   | Notes                                                    |
|-----------------------------|---------------------------|----------------------------------------------------------|
| `SamplingFrequency`         | `5120`                    | One of 512, 2048, 5120, 10240 Hz                         |
| `NumberOfChannels`          | `408`                     | One of 120, 216, 312, 408                                |
| `IpAddress` / `TCPPort`     | `169.254.1.10` / `23456`  | Quattrocento network address                             |
| `FRAMES_PER_SECOND`         | `512`                     | Higher means smaller chunks and lower marker latency     |
| `TTL_HIGH_VOLTAGE`          | `1500` mV                 | Threshold for a TTL input to count as high               |
| `active_ttl_channels`       | `[0]` (IN1)               | Indices into `IN1`–`IN16`                                |
| `TTL_LATENCY_COMPENSATION`  | `0.0` s                   | Optional fixed offset subtracted from marker timestamps  |

## Building a standalone executable

A PyInstaller spec is included:

```bash
pip install pyinstaller
pyinstaller otbio_lsl_sender.spec
```

This produces `dist/OTBio_LSL_Sender.exe`, which bundles the `assets/` folder.

## Device protocol

The device configuration commands follow OT Bioelettronica's *Quattrocento configuration protocol* (v1.7). That document belongs to OT Bioelettronica and isn't included in this repository. You can get it from [OT Bioelettronica](https://otbioelettronica.it/).

## Authors

- **ausbollinger** ([@ausbollinger13](https://github.com/ausbollinger13)): author and maintainer. Added TTL marker detection, `push_chunk` streaming, sample-accurate marker timing and the high-frame-rate latency fixes.
- **David Pruitt** ([@davepruitt](https://github.com/davepruitt)): author of the original version (Quattrocento reader, LSL integration, GUI, error alarm).

Originally developed at the Texas Biomedical Device Center (TxBDC), University of Texas at Dallas.

## License

[MIT](LICENSE)
