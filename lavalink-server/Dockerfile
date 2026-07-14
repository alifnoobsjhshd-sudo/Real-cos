FROM eclipse-temurin:17-jre-alpine

# ── Versions ──────────────────────────────────────────────────────────────────
ARG LAVALINK_VERSION=4.0.8
ARG LAVASRC_VERSION=4.3.0
# youtube-source 1.11.1 drops the WEB player-script parser that broke on
# YouTube's rotating player_embed.vflset hash ("Must find action functions
# from script" errors).  Update this when youtube-source publishes a newer fix.
ARG YTSOURCE_VERSION=1.11.1

WORKDIR /lavalink

# ── System dependencies ────────────────────────────────────────────────────────
# libgcc is required by Lavalink's native UDP queue library (libudpqueue.so).
# Without it the JVM throws UnsatisfiedLinkError on Alpine and falls back to a
# slower Java-based UDP implementation, which hurts audio stability under load.
# libstdc++ is needed by some native audio codecs.
RUN apk add --no-cache libgcc libstdc++

# ── Download Lavalink jar ──────────────────────────────────────────────────────
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

# ── Copy config ────────────────────────────────────────────────────────────────
COPY application.yml application.yml

# ── Port ───────────────────────────────────────────────────────────────────────
EXPOSE 2333

# ── JVM memory tuning ─────────────────────────────────────────────────────────
# Default: 300 MB heap — tuned for Render's free tier (512 MB total RAM).
# Override via JAVA_OPTS env var on Render for larger instances.
ENV JAVA_OPTS="-Xms32M -Xmx300M -XX:+UseG1GC -XX:G1HeapRegionSize=4M -XX:MaxGCPauseMillis=100 -XX:+UseStringDeduplication"

# ── Startup ────────────────────────────────────────────────────────────────────
# The user may set the password as either:
#   LAVALINK_PASSWORD  (single-L — standard Lavalink convention)
#   LAVALLINK_PASSWORD (double-L — the name used in Render / Replit secrets)
#
# This ENTRYPOINT normalises both into LAVALINK_PASSWORD before Java starts,
# so application.yml's ${LAVALINK_PASSWORD:youshallnotpass} always resolves
# to the real password regardless of which env var name the user chose.
ENTRYPOINT ["sh", "-c", "\
  : \"${LAVALINK_PASSWORD:=${LAVALLINK_PASSWORD:-youshallnotpass}}\" && \
  export LAVALINK_PASSWORD && \
  exec java $JAVA_OPTS -jar Lavalink.jar \
"]
