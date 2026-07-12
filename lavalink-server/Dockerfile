FROM eclipse-temurin:17-jre-alpine

# ── Versions ──────────────────────────────────────────────────────────────────
ARG LAVALINK_VERSION=4.0.8
ARG LAVASRC_VERSION=4.3.0

WORKDIR /lavalink

# ── Download Lavalink jar ─────────────────────────────────────────────────────
RUN wget -q -O Lavalink.jar \
    "https://github.com/lavalink-devs/Lavalink/releases/download/${LAVALINK_VERSION}/Lavalink.jar"

# ── Download LavaSrc plugin (Spotify / Apple Music / Deezer / Yandex) ─────────
RUN mkdir -p plugins && \
    wget -q -O plugins/lavasrc-plugin.jar \
    "https://github.com/topi314/LavaSrc/releases/download/${LAVASRC_VERSION}/lavasrc-plugin-${LAVASRC_VERSION}.jar"

# ── Copy config ───────────────────────────────────────────────────────────────
COPY application.yml application.yml

# ── Port ──────────────────────────────────────────────────────────────────────
EXPOSE 2333

# ── JVM memory tuning — override via JAVA_OPTS env var on Render ──────────────
# Default: 300 MB heap — tuned for Render's free tier (512 MB total RAM).
# If you move to a 1 GB+ instance, set JAVA_OPTS=-Xms64M -Xmx512M ... in Render.
ENV JAVA_OPTS="-Xms32M -Xmx300M -XX:+UseG1GC -XX:G1HeapRegionSize=4M -XX:MaxGCPauseMillis=100 -XX:+UseStringDeduplication"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar Lavalink.jar"]
