FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    squeezelite \
    python3 \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY bridge.py .

ENV LMS_SERVER="127.0.0.1"
ENV PLAYER_NAME="WLED-Audio-Sync"
ENV MAC_ADDR="00:04:20:11:98:88"

CMD ["sh", "-c", "squeezelite -s ${LMS_SERVER} -n ${PLAYER_NAME} -m ${MAC_ADDR} -o - -r 44100 | python3 bridge.py"]
