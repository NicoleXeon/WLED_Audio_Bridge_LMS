# WLED Audio Bridge (LMS Edition)

A high-performance, containerized digital audio bridge that connects **Lyrion Music Server (LMS)** directly to **WLED** instances over UDP multicast for zero-latency, sound-reactive LED lighting.

Instead of relying on analog or I2S microphones wired to microcontrollers—which suffer from room acoustics, background noise, and hardware gain clipping—this bridge taps directly into the master digital audio stream, calculates real-time 16-band Fast Fourier Transform (FFT) spectrum analysis on the host CPU, and broadcasts native WLED AudioReactive V2 sync packets across your local network.

---

## How It Works

1. **Digital Audio Ingestion:** A headless Squeezelite instance connects to your LMS server as a dedicated virtual audio player, streaming raw 44.1 kHz 16-bit PCM stereo audio to a local pipe.
2. **Frequency Mapping (40 Hz – 12 kHz):** Audio samples are passed through a pre-computed Hanning window and split into 16 logarithmically spaced frequency bins, capturing everything from 40 Hz sub-bass kicks up to crisp 12 kHz treble transients.
3. **$1/f$ Pink Noise Compensation (Treble Tilt):** Natural acoustic power drops off rapidly at higher frequencies. The bridge applies a logarithmic power curve across the 16 bands so high-frequency percussive elements register with the same visual impact as heavy basslines.
4. **Asymmetric Auto Gain Control (AGC):**
   * **Instant Attack:** Instantly raises the ceiling on heavy drum drops to prevent harsh 8-bit clipping (`255` whiteouts).
   * **Slow Decay (~10s):** Slowly recovers during quiet passages without aggressively boosting background noise or ruining the artist's intended dynamic contrast.
   * **Dynamic Clamping:** Restricts visual scaling between strict `GAIN_MIN` and `GAIN_MAX` boundaries to prevent gain pumping.
5. **Metronome Hardware Pacing & Gap Detection:** A frame-based master clock maintains a strict ~43 FPS output rate to prevent UDP packet floods to the ESP32. If a track change or pause is detected (>200ms empty pipe), the metronome automatically resets to eliminate start-of-track lag.
6. **Silence Gating:** During quiet passages or pauses, DSP computation and UDP transmissions are suspended, allowing WLED instances to drop into idle mode.
7. **Multicast Broadcast:** Processed spectral frames are packed into the canonical 44-byte WLED AudioReactive V2 C-struct (`00002` header) and broadcast via UDP multicast (`239.0.0.1:11988`).

---

## Why Use This?

* **Zero Hardware Microphones:** Eliminates messy analog wiring, mic modules, and dedicated GPIO usage on your microcontrollers.
* **Master-Quality Signal:** Direct mathematical analysis of the pure digital stream without room reflections, chatter, or acoustic distortion.
* **ESP8266 & ESP32 Compatible:** Offloads all floating-point math and FFT processing to the host, giving low-power ESP8266 microcontrollers full 16-band audio reactivity.
* **Network-Wide Synchronicity:** One bridge instance broadcasts to an unlimited number of WLED matrices and strips in lockstep.
* **Multi-Room Audio Friendly:** Group the virtual player with existing physical LMS zones for synchronized visuals across the house.

---

## Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `LMS_IP` | `127.0.0.1` | IP address of your LMS / Lyrion server. |
| `PLAYER_NAME` | `WLED-Audio-Sync` | Name of the virtual player in LMS. |
| `PLAYER_MAC` | `02:00:00:11:98:88` | Unique virtual MAC address for Squeezelite. |
| `FREQ_MIN` | `40.0` | Lower bound frequency (Hz) for Band 0 (Sub-bass / Kick). |
| `FREQ_MAX` | `12000.0` | Upper bound frequency (Hz) for Band 15 (Treble / Air). |
| `GAIN_MIN` | `800.0` | Lower dynamic gain limit (prevents squashing compressed tracks). |
| `GAIN_MAX` | `8500.0` | Upper dynamic gain limit (prevents amplifying background noise). |
| `TILT_EXPONENT`| `0.42` | Treble tilt compensation exponent ($1/f$ pink noise curve). |
| `DECAY_RATE` | `0.998` | Per-frame decay rate for the AGC ceiling (~10s slow decay). |
| `SILENCE_THRESHOLD` | `0.5` | Peak threshold (0–255 scale) below which the stream is gated. |
| `UDP_IP` | `239.0.0.1` | Multicast group IP for WLED AudioReactive. |
| `UDP_PORT` | `11988` | Target UDP port for WLED AudioReactive sync. |

---

## Deployment

### 1. Docker Compose

Ensure the container runs with `network_mode: host` so UDP multicast packets route directly to your local subnet:

```yaml
services:
  wled-audio-bridge:
    build: .
    container_name: wled-audio-bridge
    restart: unless-stopped
    network_mode: host
    environment:
      - LMS_IP=10.0.0.10
      - PLAYER_NAME=WLED-Audio-Sync
      - FREQ_MIN=40.0
      - FREQ_MAX=12000.0
      - GAIN_MIN=800.0
      - GAIN_MAX=8500.0
    command: sh -c "squeezelite -s $$LMS_IP -n$$PLAYER_NAME -m 02:00:00:11:98:88 -o - -r 44100 -d all=info | python3 bridge.py"
