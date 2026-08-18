import os
import sys
import time
import socket
import struct
import numpy as np

# Network settings
UDP_IP = os.environ.get("UDP_IP", "239.0.0.1")
UDP_PORT = int(os.environ.get("UDP_PORT", "11988"))

# Audio stream constants
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024
CHUNK_DURATION = CHUNK_SIZE / SAMPLE_RATE
FRAME_BYTES = CHUNK_SIZE * 4
MAX_SILENT_FRAMES = 43  # ~1 second of silence at 43.06 FPS

# DSP tuning environment overrides
FREQ_MIN = float(os.environ.get("FREQ_MIN", "100.0"))
FREQ_MAX = float(os.environ.get("FREQ_MAX", "8000.0"))
GAIN_MULT = float(os.environ.get("GAIN_MULT", "3500.0"))
SILENCE_THRESHOLD = float(os.environ.get("SILENCE_THRESHOLD", "0.5"))

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

# Compute 16 logarithmic frequency bands
FREQ_EDGES = np.logspace(np.log10(FREQ_MIN), np.log10(FREQ_MAX), 17)
fft_freqs = np.fft.rfftfreq(CHUNK_SIZE, 1.0 / SAMPLE_RATE)

bins_idx = []
for i in range(16):
    low = FREQ_EDGES[i]
    high = FREQ_EDGES[i + 1]
    idx = np.where((fft_freqs >= low) & (fft_freqs < high) & (fft_freqs > 0))[0]
    if len(idx) == 0:
        non_zero_bins = np.where(fft_freqs > 0)[0]
        closest = non_zero_bins[np.argmin(np.abs(fft_freqs[non_zero_bins] - low))]
        idx = [closest]
    bins_idx.append(idx)

sample_smth = 0.0
clock_target = time.perf_counter()
silence_frames = 0

# Canonical 44-byte WLED AudioReactive V2 struct layout
STRUCT_FMT_V2 = "<6s2xffB3x16sd"

while True:
    raw_data = sys.stdin.buffer.read(FRAME_BYTES)
    if not raw_data or len(raw_data) < FRAME_BYTES:
        break

    # Pacing at real-time audio speed to avoid CPU runaway
    clock_target += CHUNK_DURATION
    delay = clock_target - time.perf_counter()
    if delay > 0:
        time.sleep(delay)
    elif delay < -0.2:
        clock_target = time.perf_counter()

    audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
    left = audio[0::2]
    right = audio[1::2]
    mono = (left + right) / (2.0 * 32768.0)

    raw_mag = float(np.max(np.abs(mono)) * 255.0)
    sample_smth = 0.7 * sample_smth + 0.3 * raw_mag
    sample_peak = 1 if raw_mag > (sample_smth * 1.5 + 20) else 0

    if raw_mag < SILENCE_THRESHOLD:
        silence_frames += 1
    else:
        silence_frames = 0

    if silence_frames > MAX_SILENT_FRAMES:
        continue

    windowed = mono * np.hanning(CHUNK_SIZE)
    fft_vals = np.abs(np.fft.rfft(windowed)) / (CHUNK_SIZE / 2)

    fft_result = bytearray(16)
    for i in range(16):
        energy = float(np.mean(fft_vals[bins_idx[i]])) * GAIN_MULT
        fft_result[i] = min(255, int(np.clip(energy, 0, 255)))

    payload = struct.pack(
        STRUCT_FMT_V2,
        b"00002\x00",
        float(raw_mag),
        float(sample_smth),
        sample_peak,
        bytes(fft_result),
        float(raw_mag)
    )

    try:
        sock.sendto(payload, (UDP_IP, UDP_PORT))
    except Exception:
        pass
