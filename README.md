# WLED Audio Bridge (LMS)

A high-performance digital audio bridge that connects **Lyrion Music Server (LMS)** directly to **WLED** instances over UDP multicast for synchronized, sound-reactive LED lighting with zero acoustic latency.

Instead of relying on analog or I2S microphones wired to microcontrollers which suffer from room reflections, background noise, and hardware gain clipping this bridge taps directly into the master digital stream, executes real-time 16-band Fast Fourier Transform (FFT) DSP on the host CPU, and broadcasts native WLED AudioReactive V2 sync packets across your local network.

## How It Works

1.  **Digital Audio Ingestion:** A headless Squeezelite instance connects to your LMS server as a dedicated virtual player (via auto-discovery or explicit IP), streaming uncompressed 44.1 kHz 16-bit PCM stereo audio to a local pipe.
    
2.  **Frequency Mapping (40 Hz – 12 kHz):** Audio samples are windowed with a pre-computed Hanning curve and split into 16 logarithmically spaced frequency bins, capturing deep sub-bass kicks at 40 Hz up to crisp 12 kHz transients.
    
3.  **1/f Pink Noise Compensation (Treble Tilt):** Natural acoustic power rolls off steeply at higher octaves. The bridge applies a logarithmic power curve across the 16 bands so high-frequency percussive elements register with the same visual impact as heavy basslines.
    
4.  **Asymmetric Auto Gain Control (AGC):**
    
    -   **Instant Attack:** Instantly raises the tracking ceiling on heavy drops and drum transients to eliminate 8-bit clipping (255 whiteouts).
        
    -   **Slow Decay (~10s):** Decays the ceiling at a crawl during quiet passages, preserving musical dynamics and quiet intros without gain pumping.
        
    -   **Hard Clamping:** Bounds output gain strictly between `GAIN_MIN` and `GAIN_MAX` to prevent amplifying background tape hiss or squashing over-compressed modern masters.
        
5.  **Metronome Hardware Pacing & Gap Detection:** A frame-based master clock maintains a strict ~43.06 FPS output rate to prevent UDP packet floods to low-power microcontrollers. An integrated gap detector resets the metronome if an empty pipe (>200ms) occurs during track changes or pauses, eliminating start-of-track delays.
    
6.  **Silence Gating:** During quiet passages or pauses, DSP computation and UDP transmissions are suspended, allowing WLED instances to drop into idle mode.
    
7.  **Multicast Broadcast:** Processed spectral frames are packed into the canonical 44-byte WLED AudioReactive V2 C-struct (`00002` header) and broadcast via UDP multicast (`239.0.0.1:11988`).
    

## Why Use This?

-   **Zero Microphones:** Eliminates analog microphone wiring, noise floors, and GPIO contention on your ESP boards.
    
-   **Master-Quality Signal:** Direct mathematical analysis of the pure digital stream without room reflections or acoustic distortion.
    
-   **ESP8266 & ESP32 Compatible:** Offloads all floating-point math and FFT DSP to the host CPU, giving low-power ESP8266 boards full 16-band reactivity.
    
-   **Network-Wide Synchronicity:** A single bridge instance broadcasts to an unlimited number of WLED matrices and strips in lockstep.
    
-   **Multi-Room Audio Friendly:** Synchronize the virtual player with existing physical LMS zones for unified visuals throughout your network.
    
## Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `LMS_IP` | *Empty (Auto-discovery)* | IP address of your LMS / Lyrion server. Leave empty for automatic network discovery. |
| `PLAYER_NAME` | `WLED-Audio-Sync` | Name of the virtual player visible inside LMS. |
| `PLAYER_MAC` | `02:00:00:11:98:88` | Unique virtual MAC address assigned to the virtual Squeezelite. |
| `FREQ_MIN` | `40.0` | Lower bound frequency (Hz) for Band 0 (Sub-bass / Kick). |
| `FREQ_MAX` | `12000.0` | Upper bound frequency (Hz) for Band 15 (Treble / Air). |
| `GAIN_MIN` | `800.0` | Lower dynamic gain floor (prevents squashing compressed EDM/metal). |
| `GAIN_MAX` | `8500.0` | Upper dynamic gain ceiling (prevents amplifying background noise). |
| `TILT_EXPONENT`| `0.42` | Treble tilt compensation exponent (1/f pink noise curve). |
| `CONTRAST_EXPONENT` | `2.0` | Non-linear power curve exponent. Crushes mid-level musical clutter to exaggerate transient punches and beats. |
| `DECAY_RATE` | `0.998` | Per-frame decay multiplier for the AGC ceiling (~10s slow decay). |
| `SILENCE_THRESHOLD` | `0.5` | Peak threshold (0–255 scale) below which the stream is gated. |
| `UDP_IP` | `239.0.0.1` | Multicast group IP for WLED AudioReactive. |
| `UDP_PORT` | `11988` | Target UDP port for WLED AudioReactive sync. |

---

## Deployment

### Option A: Docker Compose (Recommended)

Ensure the container runs with `network_mode: host` so UDP multicast packets route directly onto your physical subnet:

YAML

```
services:
  wled-audio-bridge:
    build: .
    container_name: wled-audio-bridge
    restart: unless-stopped
    network_mode: host
    environment:
      - LMS_IP=                     # Optional: leave empty for automatic UDP discovery
      - PLAYER_NAME=WLED-Audio-Sync
      - PLAYER_MAC=02:00:00:11:98:88
      - FREQ_MIN=40.0
      - FREQ_MAX=12000.0
      - GAIN_MIN=800.0
      - GAIN_MAX=8500.0
    command: >
      sh -c 'squeezelite
      $${LMS_IP:+-s $$LMS_IP}
      -n "$${PLAYER_NAME:-WLED-Audio-Sync}"
      -m "$${PLAYER_MAC:-02:00:00:11:98:88}"
      -o -
      -r 44100
      -d all=info | python3 bridge.py'

```

Start the container:

Bash

```
docker compose up -d

```

### Option B: Bare-Metal / Standalone Shell

If running standalone on a host machine with Python 3 and Squeezelite installed:

Bash

```
# Auto-discovery mode (discovers LMS automatically on your subnet):
squeezelite -n "WLED-Audio-Sync" -m "02:00:00:11:98:88" -o - -r 44100 | python3 bridge.py

# Explicit IP mode (for cross-VLAN or routed networks):
squeezelite -s 10.0.0.10 -n "WLED-Audio-Sync" -m "02:00:00:11:98:88" -o - -r 44100 | python3 bridge.py

```

## Configuration

### 1. WLED Receiver Setup

On each WLED instance, open the web UI and navigate to **Config** > **Usermods** > **AudioReactive**:

-   **Type:** Set to `None` / `Generic I2S (Disabled)` (disables hardware mic polling).
    
-   **Frequency Scale:** Set to `None` (logarithmic scaling is handled by the bridge).
    
-   **AGC:** Set to `Off` (handled host-side via asymmetric AGC).
    
-   **Dynamics:** Set **Rise** to `40–60 ms` and **Fall** to `400–600 ms`.
    
-   **Sync Mode:** Set to `Receive`.
    
-   **Port:** Ensure it matches `11988`.
    

Save and power-cycle your microcontroller.

### 2. LMS Audio Sync Alignment

Because Squeezelite outputs to a software pipe instead of a physical motherboard DAC, LMS cannot automatically estimate acoustic room delay:

1.  Open the LMS web interface and sync `WLED-Audio-Sync` with your primary listening zone.
    
2.  Go to **Settings** > **Player** > **Audio** > **Audio Sync Delay**.
    
3.  Select `WLED-Audio-Sync` from the dropdown.
    
4.  Adjust the offset (typically between -200 ms and +200 ms) until visual impacts snap precisely to the audio coming from your room speakers.
    

## DSP & Math Breakdown

### Logarithmic Treble Compensation

To counter the natural 1/f energy falloff of recorded audio, each of the 16 frequency bands is scaled using a geometric center frequency calculation:

Plaintext

```
Center_Frequency = sqrt(Band_Low_Hz * Band_High_Hz)
Weight = (Center_Frequency / FREQ_MIN) ^ TILT_EXPONENT
Tilted_Energy = Raw_Band_Energy * Weight

```

Where `TILT_EXPONENT` is set to `0.42`. This ensures that high-frequency transients (like cymbals and snares) produce equivalent visual height to low-end bass fundamentals.

### Asymmetric Peak Decay (AGC)

Dynamic range tracking updates every frame without hard pumping or volume flattening:

Python

```
Current_Peak = max(Tilted_Energies)

If Current_Peak > Running_Ceiling:
    Running_Ceiling = Current_Peak                   # Instant Attack
Else:
    Running_Ceiling = Running_Ceiling * DECAY_RATE   # Slow Crawl Decay (~10s)

Dynamic_Gain = clamp(255.0 / Running_Ceiling, GAIN_MIN, GAIN_MAX)
Final_Bands = clamp(Tilted_Energies * Dynamic_Gain, 0, 255)

```

### Dynamic Contrast Power Curve

To prevent sustained instruments and background harmonics from keeping the visualizer bars hovering statically mid-scale, an exponential power curve is applied to normalized bands:

Contrasted_Energy = (Normalized_Energy ^ CONTRAST_EXPONENT) * 255.0

Setting `CONTRAST_EXPONENT` between `1.8` and `2.2` aggressively pulls low-to-mid level audio down toward zero while preserving full ceiling hits on transient peaks. This gives the LED matrix a snappy, rhythmic bounce with distinct drops between beats instead of a flat, muddy visual floor.


## Technical Specifications

-   **Packet Format:** 44-byte WLED AudioReactive V2 struct layout (`<6s2xffB3x16sd`).
    
-   **Frame Rate:** Hard-clocked to ~43.06 FPS (1024 samples @ 44.1 kHz).
    
-   **Memory Footprint:** ~31 MB RSS.
    
-   **CPU Footprint:** ~2.5% single-core on modern x86 hypervisors.
    

## License

MIT License. Feel free to modify, fork, and integrate into your home automation setups.
