import os
import sys
import time
import socket
import struct
import numpy as np

UDP_IP = os.environ.get("UDP_IP", "239.0.0.1")
UDP_PORT = int(os.environ.get("UDP_PORT", "11988"))

INPUT_SAMPLE_RATE = 44100
INPUT_CHUNK = 1024
FRAME_BYTES = INPUT_CHUNK * 4
DSP_SAMPLE_RATE = 22050
DSP_CHUNK = 512
CHUNK_DURATION = INPUT_CHUNK / INPUT_SAMPLE_RATE
MAX_SILENT_FRAMES = 22

FREQ_MIN = 40.0
FREQ_MAX = 5000.0
SILENCE_THRESHOLD = 0.5
GAIN_MIN = 300.0
GAIN_MAX = 2500.0 
TILT_EXPONENT = 0.25
DECAY_RATE = 0.88
CONTRAST_EXPONENT = 0.6
BASELINE_OFFSET = 12.0

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

HANNING_WINDOW = np.hanning(DSP_CHUNK).astype(np.float32)
FREQ_EDGES = np.logspace(np.log10(FREQ_MIN), np.log10(FREQ_MAX), 17)
fft_freqs = np.fft.rfftfreq(DSP_CHUNK, 1.0 / DSP_SAMPLE_RATE)
band_centers = np.sqrt(FREQ_EDGES[:-1] * FREQ_EDGES[1:])
TILT_WEIGHTS = ((band_centers / FREQ_MIN) ** TILT_EXPONENT).astype(np.float32)

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

sample_smth = 0.0
silence_frames = MAX_SILENT_FRAMES + 1
running_peak = 0.05
STRUCT_FMT_V2 = "<6s2xffB3x16sd"

print("[DSP] ALSA kernel metronome locked. Awaiting arecord pipe...", flush=True)

start_time = None
frames_processed = 0

while True:
    raw_data = read_exact_chunk(sys.stdin.buffer, FRAME_BYTES)
    
    if not raw_data:
        print("[DSP] Pipe closed.", flush=True)
        break

    if start_time is None:
        start_time = time.perf_counter()
        frames_processed = 0

    audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
    mono = (audio[0::2] + audio[1::2]) * (1.0 / 65536.0)
    mono_dsp = mono[::2]

    raw_mag = float(np.max(np.abs(mono_dsp)) * 255.0)
    sample_smth = 0.7 * sample_smth + 0.3 * raw_mag
    sample_peak = 1 if raw_mag > (sample_smth * 1.5 + 20) else 0

    if raw_mag < SILENCE_THRESHOLD:
        silence_frames += 1
    else:
        silence_frames = 0

    if silence_frames <= MAX_SILENT_FRAMES:
        windowed = mono_dsp * HANNING_WINDOW
        fft_vals = np.abs(np.fft.rfft(windowed)) * (2.0 / DSP_CHUNK)
        tilted_energies = BIN_MATRIX @ fft_vals

        current_max = float(np.max(tilted_energies))
        if current_max > running_peak:
            running_peak = current_max
        else:
            running_peak = max(0.005, running_peak * DECAY_RATE)

        dynamic_gain = np.clip(1.0 / running_peak, GAIN_MIN / 255.0, GAIN_MAX / 255.0)
        normalized = np.clip(tilted_energies * dynamic_gain, 0.0, 1.0)
        contrasted = (normalized ** CONTRAST_EXPONENT) * (255.0 - BASELINE_OFFSET)
        final_bins = contrasted + BASELINE_OFFSET

        if silence_frames == MAX_SILENT_FRAMES:
            fft_result = bytes(16)
        else:
            fft_result = bytes(np.clip(final_bins, 0, 255).astype(np.uint8))

        payload = struct.pack(
            STRUCT_FMT_V2, b"00002\x00", float(raw_mag), float(sample_smth),
            sample_peak, fft_result, float(raw_mag)
        )

        try:
            sock.sendto(payload, (UDP_IP, UDP_PORT))
        except Exception:
            pass
    else:
        silence_frames = MAX_SILENT_FRAMES + 1
        running_peak = 0.05
        sample_smth = 0.0

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
