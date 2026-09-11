import socket
import struct
import sys
import math
import time

# Check requirements before doing anything else
try:
    import pygame
except ImportError:
    sys.stderr.write("\n[ERROR] Missing required dependency: pygame\n")
    sys.stderr.write("Install it inside your virtualenv with: pip install pygame\n\n")
    sys.exit(1)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# Aligned with the dialed-in bridge DSP boundaries
FREQ_MIN = 40.0
FREQ_MAX = 8000.0

log_min = math.log10(FREQ_MIN)
log_max = math.log10(FREQ_MAX)
edges = [10 ** (log_min + (i * (log_max - log_min) / 16)) for i in range(17)]
centers = [math.sqrt(edges[i] * edges[i+1]) for i in range(16)]

def format_freq(f):
    if f < 1000:
        return f"{int(f)}"
    else:
        return f"{f/1000:.1f}k"

freq_labels = [format_freq(c) for c in centers]

UDP_IP = "" 
UDP_PORT = 11988

STRUCT_FMT_V2 = "<6s2xffB3x16sd"
PAYLOAD_SIZE = struct.calcsize(STRUCT_FMT_V2)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

pygame.init()
WIDTH, HEIGHT = 800, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("WLED DSP Tuner")
font = pygame.font.SysFont("monospace", 14, bold=True)
small_font = pygame.font.SysFont("monospace", 12)
alert_font = pygame.font.SysFont("monospace", 24, bold=True)

local_ip = get_local_ip()
running = True
data_received = False

total_packets = 0
packets_last_sec = 0
pps_display = 0
last_fps_time = time.time()

peaks = [0.0] * 16
GRAVITY = 2.5 

clock = pygame.time.Clock()

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    new_packets = []
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            if len(data) == PAYLOAD_SIZE:
                data_received = True
                total_packets += 1
                packets_last_sec += 1
                new_packets.append(data)
        except BlockingIOError:
            break
            
    current_time = time.time()
    if current_time - last_fps_time >= 1.0:
        pps_display = packets_last_sec
        packets_last_sec = 0
        last_fps_time = current_time

    if not data_received:
        screen.fill((15, 15, 15))
        warn_txt = alert_font.render("STARVING FOR PACKETS", True, (255, 50, 50))
        sub_txt = font.render(f"Set UDP_IP = '{local_ip}' in bridge.py on your DSP node", True, (150, 150, 150))
        screen.blit(warn_txt, (WIDTH//2 - warn_txt.get_width()//2, HEIGHT//2 - 20))
        screen.blit(sub_txt, (WIDTH//2 - sub_txt.get_width()//2, HEIGHT//2 + 20))
        pygame.display.flip()
        clock.tick(30)
        continue

    if new_packets:
        screen.fill((15, 15, 15))
        bar_width = (WIDTH - 40) // 16
        
        latest_unpacked = struct.unpack(STRUCT_FMT_V2, new_packets[-1])
        raw_mag = latest_unpacked[1]
        sample_smth = latest_unpacked[2]
        sample_peak = latest_unpacked[3]
        latest_fft = latest_unpacked[4]
        
        stats = f"MAG: {raw_mag:06.1f} | AGC: {sample_smth:06.1f} | PEAK: {sample_peak} | PPS: {pps_display} | TOTAL PKTS: {total_packets}"
        text = font.render(stats, True, (255, 255, 255))
        screen.blit(text, (20, 20))

        BAR_BOTTOM = HEIGHT - 40
        MAX_BAR_HEIGHT = HEIGHT - 100

        for i, val in enumerate(latest_fft):
            if val > peaks[i]:
                peaks[i] = float(val)
            else:
                peaks[i] = max(0.0, peaks[i] - GRAVITY)

            bar_h = int((val / 255.0) * MAX_BAR_HEIGHT)
            peak_h = int((peaks[i] / 255.0) * MAX_BAR_HEIGHT)
            
            x = 20 + i * bar_width
            y = BAR_BOTTOM - bar_h
            peak_y = BAR_BOTTOM - peak_h
            
            r = min(255, int(val))
            g = max(0, min(255, int(255 - val + 50)))
            color = (r, g, 50)
            pygame.draw.rect(screen, color, (x + 2, y, bar_width - 4, bar_h))
            
            pygame.draw.rect(screen, (200, 200, 200), (x + 2, peak_y, bar_width - 4, 3))
            
            lbl_num = font.render(f"{i:02d}", True, (100, 100, 100))
            screen.blit(lbl_num, (x + (bar_width//2) - (lbl_num.get_width()//2), BAR_BOTTOM + 5))
            
            lbl_freq = small_font.render(freq_labels[i], True, (160, 160, 160))
            screen.blit(lbl_freq, (x + (bar_width//2) - (lbl_freq.get_width()//2), BAR_BOTTOM + 20))

        pygame.display.flip()
        
    clock.tick(60)

pygame.quit()
sys.exit(0)
