#!/bin/bash

if [ "$(uname)" != "Linux" ]; then
    echo "[FATAL] This audio bridge requires a Linux kernel and ALSA. Get a real OS."
    exit 1
fi

echo "Checking for ALSA loopback kernel module..."
if ! lsmod | grep -q "snd_aloop"; then
    echo "Module missing. Attempting to load snd-aloop..."
    sudo modprobe snd-aloop || { echo "[FATAL] Failed to load snd-aloop. Are you running a custom kernel?"; exit 1; }
fi

echo "Kernel module verified. Launching the bridge..."
docker compose up -d --build
