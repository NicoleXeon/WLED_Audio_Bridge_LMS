FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    squeezelite \
    alsa-utils \
    python3 \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY bridge.py .
