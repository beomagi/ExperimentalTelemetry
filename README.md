<img width="900" height="557" alt="BETTv1 1" src="https://github.com/user-attachments/assets/86d853a9-f1ad-435d-bfaa-3fa4680f476c" />

# Beomagi's Experimental Telemetry Tool

A real-time telemetry dashboard for **Forza Horizon 6** data streaming (should also work with FH5).

## Overview

Main Tool:
- **`bett.py`** — Terminal-based telemetry dashboard that displays live vehicle dynamics in real-time

supplementary Tools:
- **`udpreplay.py`** — Records and replays UDP telemetry streams for testing and debugging

---

## Requirements

- Python 3.x
- Linux or Windows, should work with Mac too.
- Forza Horizon 6 running on the same network or localhost. Should be fine with FH5.
- UDP port `9999` available (or custom port via `-port`)

---

## Quick Start

### 1. Start the Dashboard

```bash
./bett.py
```

This listens on `0.0.0.0:9999` and displays incoming Forza telemetry packets.

### 2. Send Telemetry to Dashboard

From Forza Horizon 6 configure it to send UDP packets to your machine on port `9999`.

(Settings -> HUD and Gameplay -> scroll all the way down)

---

## `bett.py` — Telemetry Dashboard

A terminal UI that displays:

- **Telemetry Data**: Speed (MPH), Gear, RPM, throttle, brake
- **Car Dynamics**: Yaw, pitch, roll, orientation vector
- **Tire Slip**: Ratio, sideways angle, combined slip per wheel
- **Tire Temperature**: Front and rear tire temps with thermal efficiency analysis
- **Speed History Graph**: 75-sample rolling speed history with grid
- **Camber & Alignment Analyzer**: Real-time garage setup suggestions based on tire temps
- **Input Bars**: Visual throttle/brake gauge

### Usage

```bash
./bett.py
```
or
```
python3 bett.py
```

- `Ctrl+C` to exit


---

## `udpreplay.py` — Record & Replay

Record live Forza telemetry streams and replay them for testing and debugging.

### Record Mode

Listens on `0.0.0.0:9999` and saves all incoming packets to a binary file:

```bash
./udpreplay.py -rec <filename>
```

**Example:**

```bash
./udpreplay.py -rec my_lap.cap
```

This records packets with timestamps and packet lengths for accurate replay timing.

### Playback Mode

Loads a recorded file and replays packets to a destination (default: `127.0.0.1:9999`):

```bash
./udpreplay.py -play <filename>
```

**Example:**

```bash
./udpreplay.py -play my_lap.cap
```

### Playback Options

| Option | Default | Description |
|--------|---------|-------------|
| `-play <file>` | — | Play this file to destination |
| `-rec <file>` | — | Record from UDP to this file |
| `-IP <addr>` | `127.0.0.1` | Destination IP for playback |
| `-dest-port <port>` | `9999` | Destination port for playback |
| `-port <port>` | `9999` | Source port for recording |
| `-repeat` | — | Loop playback indefinitely |

## File Format

### Recording File Structure

Each recorded packet is stored as:

```
[8 bytes: double]   timestamp (seconds since epoch)
[4 bytes: uint]     payload length
[N bytes: payload]  raw Forza packet (usually 324 bytes)
```

This allows accurate replay timing and packet reconstruction.

---


## License

See [LICENSE](LICENSE)
