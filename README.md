# WLED Audio Bridge 0.2

A containerized audio bridge that connects **Lyrion Music Server (LMS)** directly to **WLED** instances over UDP multicast for synchronized, sound-reactive LED lighting.

Instead of relying on physical I2S or analog microphones wired to microcontrollers—which suffer from room noise, drywall acoustics, and gain clipping—this bridge taps directly into the digital audio stream, calculates real-time FFT spectrum analysis on the host machine, and broadcasts native WLED AudioReactive sync packets across your local network.

---

## How It Works

1. **Audio Ingestion:** A headless Squeezelite instance connects to your LMS server as a dedicated virtual audio player.
2. **Real-time DSP:** The bridge ingests raw 44.1 kHz 16-bit PCM audio from the stream, computes 16 logarithmically spaced frequency bands via Fast Fourier Transform (FFT), and tracks volume/peak dynamics.
3. **Metronome Pacing & Burn-off:** Because standard software players use massive network buffers that cause multi-second visual delays, the bridge utilizes an absolute frame-based hardware clock. It instantly burns through OS pipe backlogs at max CPU speed to stay on the live edge, then rigidly locks transmission to ~43 FPS to prevent UDP packet storms.
4. **Silence Gating:** When music is paused or quiet passages occur, the bridge halts FFT computations and suspends UDP packet transmission, allowing ESP receivers to drop gracefully into idle mode.
5. **Multicast Broadcast:** The processed spectrum is packed into the canonical WLED AudioReactive V2 C-struct and broadcast via UDP multicast (`239.0.0.1:11988`), where any number of ESP8266 or ESP32 devices can consume it simultaneously.

---

## Why Use This?

* **Zero Hardware Mics:** Frees up GPIOs on your ESP microcontrollers and eliminates microphone wiring entirely.
* **Flawless Digital Signal:** Clean FFT analysis from the master audio stream without room echoes, background voices, or ambient noise.
* **Network-Wide Sync:** One bridge instance can drive all WLED devices in your home in lockstep.
* **ESP8266 Support:** Brings full 16-band audio reactivity to low-power ESP8266 devices that lack the processing power to perform on-chip FFT analysis.
* **Multi-Room Audio Friendly:** Easily group the virtual player with existing LMS audio zones for synchronized visuals.

---

## Prerequisites

* A host machine running Docker and Docker Compose.
* An active **Lyrion Music Server (LMS)** or Logitech Media Server instance.
* One or more ESP8266 / ESP32 boards flashed with **WLED v0.14.0+** (with the `AudioReactive` usermod enabled).
* Host network access for Docker (required for UDP multicast routing).

---

## Usage

### 1. Configure the Environment

The bridge is configured using standard environment variables passed into the container:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `LMS_IP` | `127.0.0.1` | IP address of your LMS / Lyrion server. |
| `PLAYER_NAME` | `WLED-Audio-Sync` | Name of the virtual audio player inside LMS. |
| `PLAYER_MAC` | `02:00:00:11:98:88` | Unique virtual MAC address for Squeezelite. |
| `FREQ_MIN` | `100.0` | Lower bound frequency (Hz) for Band 0. |
| `FREQ_MAX` | `8000.0` | Upper bound frequency (Hz) for Band 15. |
| `GAIN_MULT` | `3500.0` | Visual sensitivity multiplier for FFT bands. |
| `SILENCE_THRESHOLD` | `0.5` | Peak threshold (0–255 scale) below which the stream is gated. |
| `UDP_IP` | `239.0.0.1` | Multicast group IP for WLED AudioReactive. |
| `UDP_PORT` | `11988` | Target UDP port for WLED AudioReactive sync. |

### 2. Deploy

Clone this repository and start the stack:

```bash
docker compose up -d
