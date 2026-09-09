import os
import sys
import time
import socket
import struct
import numpy as np
import fcntl

# Loosen the lobotomy slightly to 8192 bytes. 
try:
    F_SETPIPE_SZ = 1031
    fcntl.fcntl(sys.stdin.fileno(), F_SETPIPE_SZ, 8192)
except Exception:
    pass

# Network settings
UDP_IP = os.environ.get("UDP_IP", "239.0.0.1")
UDP_PORT = int(os.environ.get("UDP_PORT", "11988"))

# Audio stream constants optimized for 24kHz downsampling
SAMPLE_RATE = 24000
CHUNK_SIZE = 512
CHUNK_DURATION = CHUNK_SIZE / SAMPLE_RATE
FRAME_BYTES = CHUNK_SIZE * 4
MAX_SILENT_FRAMES = 43

# Hardcoded DSP tuning for violent clipping
FREQ_MIN = 44.0
FREQ_MAX = 12000.0
SILENCE_THRESHOLD = 0.5
GAIN_MIN = 800.0
GAIN_MAX = 1500.0
TILT_EXPONENT = 0.45
DECAY_RATE = 0.40
CONTRAST_EXPONENT = 4.5

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

# Pre-compute Hanning window
HANNING_WINDOW = np.hanning(CHUNK_SIZE).astype(np.float32)

# Compute 16 logarithmic frequency bands
FREQ_EDGES = np.logspace(np.log10(FREQ_MIN), np.log10(FREQ_MAX), 17)
fft_freqs = np.fft.rfftfreq(CHUNK_SIZE, 1.0 / SAMPLE_RATE)

# Pre-compute logarithmic treble tilt weights
band_centers = np.sqrt(FREQ_EDGES[:-1] * FREQ_EDGES[1:])
TILT_WEIGHTS = ((band_centers / FREQ_MIN) ** TILT_EXPONENT).astype(np.float32)

# Build a C-optimized Matrix for dot-product binning
BIN_MATRIX = np.zeros((16, len(fft_freqs)), dtype=np.float32)

for i in range(16):
    low = FREQ_EDGES[i]
    high = FREQ_EDGES[i + 1]
    idx = np.where((fft_freqs >= low) & (fft_freqs < high) & (fft_freqs > 0))[0]
    
    if len(idx) == 0:
        non_zero_bins = np.where(fft_freqs > 0)[0]
        closest = non_zero_bins[np.argmin(np.abs(fft_freqs[non_zero_bins] - low))]
        idx = [closest]
        
    BIN_MATRIX[i, idx] = (1.0 / len(idx)) * TILT_WEIGHTS[i]

# State variables
sample_smth = 0.0
silence_frames = 0
running_peak = 0.05
STRUCT_FMT_V2 = "<6s2xffB3x16sd"

def read_exact_chunk(fd, size):
    buf = bytearray(size)
    view = memoryview(buf)
    pos = 0
    while pos < size:
        chunk = fd.readinto(view[pos:])
        if not chunk:
            return None
        pos += chunk
    return bytes(buf)

start_time = None
frames_processed = 0

while True:
    t0 = time.perf_counter()
    raw_data = read_exact_chunk(sys.stdin.buffer, FRAME_BYTES)
    read_duration = time.perf_counter() - t0

    if not raw_data:
        break

    if read_duration > 0.015:
        start_time = time.perf_counter()
        frames_processed = 0
        running_peak = 0.05

    if start_time is None:
        start_time = time.perf_counter()

    audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
    left = audio[0::2]
    right = audio[1::2]
    mono = (left + right) * (1.0 / 65536.0)

    raw_mag = float(np.max(np.abs(mono)) * 255.0)
    sample_smth = 0.7 * sample_smth + 0.3 * raw_mag
    sample_peak = 1 if raw_mag > (sample_smth * 1.5 + 20) else 0

    if raw_mag < SILENCE_THRESHOLD:
        silence_frames += 1
    else:
        silence_frames = 0

    if silence_frames <= MAX_SILENT_FRAMES:
        windowed = mono * HANNING_WINDOW
        fft_vals = np.abs(np.fft.rfft(windowed)) * (2.0 / CHUNK_SIZE)

        tilted_energies = BIN_MATRIX @ fft_vals

        current_max = float(np.max(tilted_energies))
        if current_max > running_peak:
            running_peak = current_max
        else:
            running_peak = max(0.005, running_peak * DECAY_RATE)

        dynamic_gain = np.clip(1.0 / running_peak, GAIN_MIN / 255.0, GAIN_MAX / 255.0)

        normalized = np.clip(tilted_energies * dynamic_gain, 0.0, 1.0)
        contrasted = (normalized ** CONTRAST_EXPONENT) * 255.0
        fft_result = bytes(np.clip(contrasted, 0, 255).astype(np.uint8))

        payload = struct.pack(
            STRUCT_FMT_V2,
            b"00002\x00",
            float(raw_mag),
            float(sample_smth),
            sample_peak,
            fft_result,
            float(raw_mag)
        )

        try:
            sock.sendto(payload, (UDP_IP, UDP_PORT))
        except Exception:
            pass

    # Hybrid PLL Metronome to provide flawless backpressure
    frames_processed += 1
    target_time = start_time + (frames_processed * CHUNK_DURATION)
    sleep_time = target_time - time.perf_counter()

    if sleep_time > 0.002:
        time.sleep(sleep_time - 0.001)

    while time.perf_counter() < target_time:
        pass

    if sleep_time < -1.0:
        start_time = time.perf_counter()
        frames_processed = 0
