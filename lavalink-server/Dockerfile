FROM eclipse-temurin:17-jre-alpine

# ── Versions ──────────────────────────────────────────────────────────────────
# Lavalink-musl.jar is built for Alpine (musl libc). Using the plain
# Lavalink.jar on Alpine causes native-library errors and slower UDP audio.
ARG LAVALINK_VERSION=4.2.2
ARG LAVASRC_VERSION=4.8.3
ARG YTSOURCE_VERSION=1.18.1

WORKDIR /lavalink

# ── System dependencies ────────────────────────────────────────────────────────
# libgcc / libstdc++ are required by Lavalink's native UDP queue (libudpqueue)
# and some native audio codecs.  Without them the JVM falls back to a slower
# Java UDP implementation, hurting audio stability.
RUN apk add --no-cache libgcc libstdc++

# ── Download Lavalink jar ──────────────────────────────────────────────────────
# NOTE: Lavalink-musl.jar is the correct build for Alpine / musl libc containers.
#       The plain Lavalink.jar is for Debian/Ubuntu (glibc) images.
RUN wget -q --tries=3 -O Lavalink.jar \
    "https://github.com/lavalink-devs/Lavalink/releases/download/${LAVALINK_VERSION}/Lavalink-musl.jar"

# ── Download plugins ───────────────────────────────────────────────────────────
# Plugins are baked into the image at build time so Lavalink starts instantly
# without downloading anything at runtime.
#
# youtube-source: replaces Lavalink's built-in YouTube source (required by
#   LavaSrc 4.x). Version 1.18.1 fixes the OAuth null-check bug and removes
#   the broken TvHtml5Simply client.
#
# LavaSrc: adds Spotify / Apple Music / Yandex Music resolution on top of the
#   youtube-source playback backend.
RUN mkdir -p plugins && \
    wget -q --tries=3 -O plugins/youtube-plugin.jar \
    "https://github.com/lavalink-devs/youtube-source/releases/download/${YTSOURCE_VERSION}/youtube-plugin-${YTSOURCE_VERSION}.jar" && \
    wget -q --tries=3 -O plugins/lavasrc-plugin.jar \
    "https://github.com/topi314/LavaSrc/releases/download/${LAVASRC_VERSION}/lavasrc-plugin-${LAVASRC_VERSION}.jar"

# ── Copy config ────────────────────────────────────────────────────────────────
COPY application.yml application.yml

# ── Port ───────────────────────────────────────────────────────────────────────
EXPOSE 2333

# ── JVM memory tuning ─────────────────────────────────────────────────────────
# Defaults are tuned for Render's free tier (512 MB total RAM).
#
# Free tier  → leave JAVA_OPTS unset  (uses these defaults: 300 MB heap)
# Starter    → set JAVA_OPTS=-Xms64M -Xmx600M -XX:+UseG1GC in Render env vars
# Standard+  → set JAVA_OPTS=-Xms128M -Xmx900M -XX:+UseG1GC
#
# G1GC flags explained:
#   G1HeapRegionSize=4M  — small regions reduce GC overhead on a small heap
#   MaxGCPauseMillis=200 — keep audio thread pauses under 200 ms
#   UseStringDeduplication — deduplicates repeated track title/artist strings
ENV JAVA_OPTS="-Xms32M -Xmx300M \
  -XX:+UseG1GC \
  -XX:G1HeapRegionSize=4M \
  -XX:MaxGCPauseMillis=200 \
  -XX:+UseStringDeduplication \
  -Djdk.tls.acknowledgeCloseNotify=true \
  -Dsun.net.inetaddr.ttl=60"

# ── Startup ────────────────────────────────────────────────────────────────────
# The user may set the Lavalink password as either:
#   LAVALINK_PASSWORD  (single-L — the standard Lavalink convention)
#   LAVALLINK_PASSWORD (double-L — the name used in some Render / Replit setups)
# This entrypoint normalises both into LAVALINK_PASSWORD before Java starts.
ENTRYPOINT ["sh", "-c", "\
  : \"${LAVALINK_PASSWORD:=${LAVALLINK_PASSWORD:-youshallnotpass}}\" && \
  export LAVALINK_PASSWORD && \
  exec java $JAVA_OPTS -jar Lavalink.jar \
"]
