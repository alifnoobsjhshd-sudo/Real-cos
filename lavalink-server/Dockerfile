FROM eclipse-temurin:17-jre-alpine

# ── Versions ──────────────────────────────────────────────────────────────────
ARG LAVALINK_VERSION=4.0.8
ARG LAVASRC_VERSION=4.3.0
ARG YTSOURCE_VERSION=1.8.3

WORKDIR /lavalink

# ── Download Lavalink jar ─────────────────────────────────────────────────────
RUN wget -q -O Lavalink.jar \
    "https://github.com/lavalink-devs/Lavalink/releases/download/${LAVALINK_VERSION}/Lavalink.jar"

# ── Download plugins ───────────────────────────────────────────────────────────
# LavaSrc: Spotify / Apple Music / Yandex support
# youtube-source: required by LavaSrc 4.x — replaces built-in YouTube source
RUN mkdir -p plugins && \
    wget -q -O plugins/lavasrc-plugin.jar \
    "https://github.com/topi314/LavaSrc/releases/download/${LAVASRC_VERSION}/lavasrc-plugin-${LAVASRC_VERSION}.jar" && \
    wget -q -O plugins/youtube-plugin.jar \
    "https://github.com/lavalink-devs/youtube-source/releases/download/${YTSOURCE_VERSION}/youtube-plugin-${YTSOURCE_VERSION}.jar"

# ── Copy config ───────────────────────────────────────────────────────────────
COPY application.yml application.yml

# ── Port ──────────────────────────────────────────────────────────────────────
EXPOSE 2333

# ── JVM memory tuning — override via JAVA_OPTS env var on Render ──────────────
# Default: 300 MB heap — tuned for Render's free tier (512 MB total RAM).
# If you move to a 1 GB+ instance, set JAVA_OPTS=-Xms64M -Xmx512M ... in Render.
ENV JAVA_OPTS="-Xms32M -Xmx300M -XX:+UseG1GC -XX:G1HeapRegionSize=4M -XX:MaxGCPauseMillis=100 -XX:+UseStringDeduplication"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar Lavalink.jar"]
