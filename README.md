# WLED Audio Bridge (LMS)

A high-performance digital audio bridge that connects **Lyrion Music Server (LMS)** directly to **WLED** instances over UDP multicast for synchronized, sound-reactive LED lighting.

Instead of relying on analog or I2S microphones wired to microcontrollers—which suffer from room reflections, background noise, and hardware gain clipping—this bridge taps directly into the master digital stream. It executes a real-time 16-band Fast Fourier Transform (FFT) on the host CPU and broadcasts native WLED AudioReactive V2 sync packets across your local network.

> **⚠️ OS ARCHITECTURE WARNING**
> The primary, zero-latency architecture relies on the Linux kernel's ALSA loopback module (`snd-aloop`) to act as a flawless hardware metronome. A fallback pipeline is provided for macOS and Windows, but it is entirely software-paced and **will** suffer from buffer bloat and accumulating sync drift. Spin this up on a Linux machine if you want it to run perfectly.

---

## How It Works

1. **Digital Audio Ingestion:** A headless Squeezelite instance connects to your LMS server, streaming uncompressed 44.1 kHz 16-bit PCM stereo audio.
2. **Hardware Metronome (Linux Only):** On Linux, the audio is routed through a virtual ALSA loopback device (`snd-aloop`). The kernel physically throttles the playback stream to exactly 44,100 samples per second, completely eliminating TCP buffer bloat and sync drift. 
3. **2:1 Decimation:** The bridge pulls 1024-sample chunks and decimates the stream down to 22.05 kHz (512 samples). This tightens frequency bin resolution to **43.06 Hz per bin**, allowing the DSP to isolate sub-bass rumbles from kick drums.
4. **Logarithmic Frequency Mapping:** Samples are windowed with a pre-computed Hanning curve and partitioned into 16 logarithmically spaced bands (40 Hz – 6 kHz).
5. **Asymmetric Auto Gain Control (AGC) & Contrast Shaping:** The script executes real-time dynamic range compression, applying exponential contrast curves to violently crush background noise into dead black while allowing transient beats to hit blinding peak brightness. 
6. **Multicast Broadcast:** Processed spectral frames are packed into the canonical 44-byte WLED AudioReactive V2 C-struct (`00002` header) and broadcast via UDP multicast (`239.0.0.1:11988`) at a glassy ~43 FPS.

---

## Environment Variables & Tunables

Adjust these in your compose file to shape how your matrix reacts to the math:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `LMS_IP` | *Empty* | IP of your LMS / Lyrion server. Leave empty for auto-discovery. |
| `PLAYER_NAME` | `WLED-Audio-Sync` | Virtual player name visible inside LMS. |
| `PLAYER_MAC` | `02:00:00:11:98:88` | Virtual MAC address assigned to Squeezelite. |
| `FREQ_MIN` | `40.0` | Lower frequency bound (Hz) for Band 00 (Sub-bass / Kick). |
| `FREQ_MAX` | `6000.0` | Upper frequency bound (Hz). Lowering this stops wasting LED bands on inaudible high-hat hiss. |
| `GAIN_MIN` | `200.0` | Minimum AGC multiplier. Keep this low so the lights can physically rest between beats. |
| `GAIN_MAX` | `3500.0` | Maximum AGC multiplier. Amplifies quiet signals to maintain visual height. |
| `TILT_EXPONENT` | `0.25` | Treble compensation exponent. Boosts the high-end so snares aren't overshadowed by massive kick drums. |
| `DECAY_RATE` | `0.88` | AGC peak envelope decay. Lower = faster drop-off and harder visual punches. |
| `CONTRAST_EXPONENT` | `1.5` | Exponential curve factor. > 1.0 crushes noise into black. < 1.0 boosts low-level audio for a constant glow. |
| `BASELINE_OFFSET` | `8.0` | Minimum resting baseline (0–255). Adds a simmer to the matrix during silence. |

---

## Deployment

The bridge executes inside a single Docker container, sharing the same `Dockerfile` across all platforms. Choose your path based on your host OS.

### Option A: Linux / ALSA (The Right Way)
Linux users get the flawless ALSA loopback architecture. Simply execute the wrapper script. It will verify your kernel, load the `snd-aloop` module on the fly, and build the container using `docker-compose.yml` and `bridge.py`.

```bash
./launch.sh
```

*(Note: Running `modprobe` only loads the virtual soundcard until you reboot. To make the ALSA loopback survive a host restart, run `echo "snd-aloop" | sudo tee -a /etc/modules` on your host).*

### Option B: macOS / Windows (The Fallback)
If you are running on a non-Linux host, the container cannot mount the ALSA hardware metronome. You are forced to use the software-paced fallback pipe (`bridge-nonlinux.py`). This method is functional but susceptible to TCP buffer bloat.

Run the fallback compose file directly:
```bash
docker compose -f docker-compose-nonlinux.yml up -d --build
```

---

## Configuration

### 1. WLED Receiver Setup

On each WLED instance, open the web UI and navigate to **Config** > **Usermods** > **AudioReactive**:

* **Type:** Set to `None` / `Generic I2S (Disabled)` (disables hardware mic polling).
* **Frequency Scale:** Set to `None` (logarithmic scaling is handled by the bridge).
* **AGC:** Set to `Off` (handled host-side).
* **Dynamics:** Set **Rise** to `40–60 ms` and **Fall** to `400–600 ms`.
* **Sync Mode:** Set to `Receive`.
* **Port:** Ensure it matches `11988`.

Save and power-cycle your microcontroller.

### 2. LMS Audio Sync Alignment

Because the audio is dumped into a digital pipe instead of physical speakers, you must align the visualizer in the LMS web UI (**Settings** > **Player** > **Audio** > **Audio Sync Delay**). 

* **For Linux/ALSA Users:** The processing lag is **100% static**. Adjust the offset negatively (typically around `-500 ms` to `-1000 ms`) until the transient strikes match your room speakers. Once dialed in, it will never drift.
* **For macOS/Windows Users:** The software pipe accumulates drift over time. You will need to periodically tweak the delay slider or restart the container when the visual lag becomes unbearable. 

---

## Diagnostic Tuner (`bridge_tuner.py`)

A desktop GUI monitor built with Pygame to inspect the live DSP output of the bridge across the network in real-time.

![WLED DSP Tuner](tuner.png)

1. Ensure Pygame is installed (`pip install pygame`).
2. Run `python3 bridge_tuner.py`.
3. If running across separate VLANs where UDP multicast is blocked, temporarily set `- UDP_IP=192.168.x.x` in your compose file to target the tuner machine directly.

---

## License
MIT License. Feel free to modify, fork, and integrate into your home automation setups.
