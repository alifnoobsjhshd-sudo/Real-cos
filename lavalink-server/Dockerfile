FROM eclipse-temurin:17-jre-alpine

# ── Versions ──────────────────────────────────────────────────────────────────
# Lavalink-musl.jar is built for Alpine (musl libc). Using the plain
# Lavalink.jar on Alpine causes native-library errors and slower UDP audio.
ARG LAVALINK_VERSION=4.2.2
ARG LAVASRC_VERSION=4.8.3
ARG YT_SOURCE_VERSION=1.11.1

WORKDIR /lavalink

# ── System dependencies ────────────────────────────────────────────────────────
# libgcc / libstdc++ → Lavalink's native UDP queue (libudpqueue) + audio codecs.
#   Without them the JVM falls back to slow Java UDP, hurting audio stability.
# curl → used by the HEALTHCHECK below (wget on Alpine/busybox can't reliably
#   distinguish a live HTTP response from a connection error on all Alpine builds).
RUN apk add --no-cache libgcc libstdc++ curl

# ── Download Lavalink jar ──────────────────────────────────────────────────────
# NOTE: Lavalink-musl.jar is the correct build for Alpine / musl libc containers.
#       The plain Lavalink.jar targets Debian/Ubuntu (glibc) — do NOT use it here.
RUN wget -q --tries=3 -O Lavalink.jar \
    "https://github.com/lavalink-devs/Lavalink/releases/download/${LAVALINK_VERSION}/Lavalink-musl.jar"

# ── Download plugins ───────────────────────────────────────────────────────────
# Plugins are baked into the image at build time so Lavalink starts instantly
# without downloading anything at runtime (critical on Render's slow boot).
#
# youtube-source  — replaces Lavalink's built-in YouTube source (required by
#   LavaSrc 4.x). Fixes the OAuth null-check bug; removes broken TvHtml5Simply.
#
# LavaSrc         — adds native Spotify / Apple Music / Yandex resolution on top
#   of the youtube-source playback backend. ISRC matching gives accurate results.
RUN mkdir -p plugins && \
    wget -q --tries=3 -O plugins/lavasrc-plugin.jar \
      "https://github.com/topi314/LavaSrc/releases/download/${LAVASRC_VERSION}/lavasrc-plugin-${LAVASRC_VERSION}.jar" && \
    wget -q --tries=3 -O plugins/youtube-source.jar \
      "https://github.com/lavalink-devs/youtube-source/releases/download/${YT_SOURCE_VERSION}/youtube-source-${YT_SOURCE_VERSION}.jar"

# ── Copy config ────────────────────────────────────────────────────────────────
COPY application.yml application.yml

# ── Port ───────────────────────────────────────────────────────────────────────
EXPOSE 2333

# ── JVM memory tuning ─────────────────────────────────────────────────────────
# Tuned for Render free tier (512 MB total container RAM).
#
# Heap sizing guide:
#   Free  (512 MB RAM) → leave JAVA_OPTS unset  → this 300 MB default applies
#   Starter (1 GB RAM) → set JAVA_OPTS=-Xms64M -Xmx600M -XX:+UseG1GC in Render
#   Standard (2 GB+)   → set JAVA_OPTS=-Xms128M -Xmx900M -XX:+UseG1GC
#
# G1GC flags:
#   G1HeapRegionSize=4M     — small regions cut GC overhead on a small heap
#   MaxGCPauseMillis=200    — keep audio thread GC pauses under 200 ms
#   UseStringDeduplication  — deduplicates repeated track title/artist strings
#   InitiatingHeapOccupancy — start GC early to avoid long stop-the-world pauses
ENV JAVA_OPTS="-Xms32M -Xmx300M \
  -XX:+UseG1GC \
  -XX:G1HeapRegionSize=4M \
  -XX:MaxGCPauseMillis=200 \
  -XX:+UseStringDeduplication \
  -XX:InitiatingHeapOccupancyPercent=50 \
  -Djdk.tls.acknowledgeCloseNotify=true \
  -Dsun.net.inetaddr.ttl=60"

# ── Health check ───────────────────────────────────────────────────────────────
# Lavalink v4 exposes /v4/info (no auth required) on port 2333.
# start-period=90s gives the JVM enough time to initialise and load plugins.
# Any HTTP response (200, 401, etc.) means Lavalink is alive — we only want
# to detect a dead process (connection refused / timeout).
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -sf --max-time 8 http://localhost:2333/v4/info \
      -H "Authorization: ${LAVALINK_PASSWORD:-youshallnotpass}" \
      > /dev/null || exit 1

# ── Startup ────────────────────────────────────────────────────────────────────
# Accepts both LAVALINK_PASSWORD (standard) and LAVALLINK_PASSWORD (double-L,
# used in some Render / Replit setups) so the bot's env var works either way.
ENTRYPOINT ["sh", "-c", "\
  : \"${LAVALINK_PASSWORD:=${LAVALLINK_PASSWORD:-youshallnotpass}}\" && \
  export LAVALINK_PASSWORD && \
  exec java $JAVA_OPTS -jar Lavalink.jar \
"]
