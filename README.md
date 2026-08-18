# WLED Audio Bridge

A containerized audio bridge that connects **Lyrion Music Server (LMS)** directly to **WLED** instances over UDP multicast for synchronized, sound-reactive LED lighting.

Instead of relying on physical I2S or analog microphones wired to microcontrollers—which suffer from room noise, drywall acoustics, and gain clipping—this bridge taps directly into the digital audio stream, calculates real-time FFT spectrum analysis on the host machine, and broadcasts native WLED AudioReactive sync packets across your local network.

---

## How It Works

1. **Audio Ingestion:** A headless Squeezelite instance connects to your LMS server as a dedicated virtual audio player.
2. **Real-time DSP:** The bridge ingests raw 44.1 kHz 16-bit PCM audio from the stream, computes 16 logarithmically spaced frequency bands via Fast Fourier Transform (FFT), and tracks volume/peak dynamics.
3. **Clock Pacing:** Software pacing keeps PCM consumption tied directly to real-time audio playback, preventing CPU spikes from unthrottled decoders.
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
```

### 3. Configure WLED Nodes

On each WLED instance, open the web UI and go to **Config** > **Usermods** > **AudioReactive**:

* **Type:** Set to `None` / `Generic I2S (Disabled)` (disables hardware mic polling).
* **Frequency Scale:** Set to `None` (logarithmic scaling is handled by the bridge).
* **AGC:** Set to `Off`.
* **Dynamics:** Set **Rise** to `40–60 ms` and **Fall** to `400–600 ms` for snappy visuals.
* **Sync Mode:** Set to `Receive`.
* **Port:** Ensure it matches `11988`.

Save and power-cycle your microcontroller.

### 4. Link in LMS

Open the LMS web interface and synchronize the new `WLED-Audio-Sync` player with your active music zone. Any track playing in that zone will now stream reactive lighting effects in real time.

---

## Technical Notes

* **Protocol Version:** Uses the 44-byte WLED AudioReactive V2 packet format (`00002` header).
* **Network Mode:** Must run on the host network (`network_mode: host`) so multicast traffic traverses directly onto the local subnet without being blocked by Docker NAT bridges.
* **Wi-Fi Optimization:** If packets are delayed or dropped on certain routers, disable *Wi-Fi Multimedia (WMM)* or *IGMP Snooping* features that interfere with UDP multicast delivery to low-power microcontrollers.

---

## License

MIT License. Feel free to modify, distribute, and integrate into your home automation setups.
