# Lavalink Server — Render Deployment Guide

A self-hosted Lavalink v4 node tuned for Render's free tier (512 MB RAM).
Once deployed, your bot connects to it automatically via two environment variables.

---

## What's included

| File | Purpose |
|---|---|
| `Dockerfile` | Lavalink + youtube-source + LavaSrc on Alpine/musl, with HEALTHCHECK |
| `application.yml` | Full config: YouTube OAuth, Spotify via ISRC, SoundCloud, filters |
| `render.yaml` | Render Blueprint — one-click service creation (optional) |
| `.dockerignore` | Keeps build context clean (only Dockerfile + yml go into image) |

### Sources enabled out of the box
- ✅ YouTube + YouTube Music (via youtube-source plugin)
- ✅ Spotify (via LavaSrc — needs a free Spotify app key)
- ✅ SoundCloud, Bandcamp, Twitch, Vimeo
- ⚠️ Deezer — disabled (requires a master decryption key you must source yourself)
- ⚠️ Apple Music — disabled (requires a `mediaAPIToken`)

### Baked-in versions

| Component | Version |
|---|---|
| Lavalink | 4.2.2 (musl/Alpine build) |
| youtube-source | 1.18.1 |
| LavaSrc | 4.8.3 |

---

## Step 1 — Choose your deployment method

### Method A — Separate GitHub repo (recommended)

Create a fresh repo, copy the **contents** of this `lavalink-server/` folder to its
root, and push. The `render.yaml` will be at the repo root where Render expects it.

### Method B — From your bot's existing repo

Render lets you set a **Root Directory** per service, so it only builds
`lavalink-server/`. No separate repo needed.

If you want to use the Blueprint (render.yaml):
1. Copy `render.yaml` to the **root** of your bot's repo.
2. Uncomment the `rootDir: lavalink-server` line inside it.
3. Merge with any existing `render.yaml` if one exists — don't create two.

---

## Step 2 — Create the Render web service

### Option A: Render Blueprint (fastest)

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**.
2. Connect the GitHub repo (your new Lavalink repo or your bot repo).
3. Render reads `render.yaml` and pre-fills the service for you.
4. Review the settings → **Apply**.
5. Skip to **Step 3** to set your environment variables.

### Option B: Manual setup

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**.
2. Connect your GitHub repo.
3. Fill in these fields:

| Setting | Value |
|---|---|
| **Name** | `lavalink-server` (or anything) |
| **Root Directory** | `lavalink-server` (only if using the bot repo — leave empty for a standalone repo) |
| **Runtime** | `Docker` |
| **Instance Type** | See below |

**Which instance type to pick:**

| Tier | RAM | Verdict |
|---|---|---|
| **Free (512 MB)** | 512 MB | Works for testing and light personal use. Render spins it down after 15 min of inactivity — music stops until someone runs `/play`. The bot's WebSocket keeps it alive during active use. |
| **Starter ($7/mo)** | 1 GB | Best value. Stays up 24/7, handles 3–5 concurrent streams. Set `JAVA_OPTS=-Xms64M -Xmx600M -XX:+UseG1GC` in env vars. |
| **Standard ($25/mo)** | 2 GB | Heavy use / multiple large servers. Set `JAVA_OPTS=-Xms128M -Xmx900M -XX:+UseG1GC`. |

4. Click **Advanced** → confirm **Auto-Deploy** is on.
5. Click **Create Web Service** — add env vars in the next step.

---

## Step 3 — Set environment variables

In Render → your Lavalink service → **Environment**, add the following.

### Required

| Key | Value |
|---|---|
| `LAVALINK_PASSWORD` | A strong password you invent, e.g. `Zyrox#Lava2026!` |

> ⚠️ **Remember this password exactly.** You'll paste it into the bot's env vars as `LAVALINK_PASSWORDS` (case-sensitive).

---

### For Spotify support (free, 2 minutes)

| Key | Value |
|---|---|
| `SPOTIFY_CLIENT_ID` | From [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard |

**Getting Spotify credentials:**
1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) — log in (free account is fine).
2. Click **Create app** — name it anything. Set redirect URI to `http://localhost`.
3. Open your new app → **Settings** → copy **Client ID** and **Client Secret**.
4. Paste both into your **Lavalink** service env vars.
5. Also set the same two vars on your **bot's** Render service (the bot uses them for playlist metadata).

---

### For YouTube OAuth (strongly recommended)

OAuth eliminates most "Video unavailable" and HTTP 429 errors. It takes ~2 minutes
to set up and is free.

**First deployment — to capture the token:**

| Key | Value |
|---|---|
| `YOUTUBE_OAUTH_ENABLED` | `true` |

Leave `YOUTUBE_REFRESH_TOKEN` and `YOUTUBE_SKIP_INIT` **unset** for now.

> This tells Lavalink to print the authorization URL in the logs on boot.

---

## Step 4 — Deploy and watch the logs

1. Click **Save Changes** → Render triggers a deploy.
2. Build takes **2–4 minutes** (downloads jars during Docker build — done once).
3. Once live, open **Logs** and look for:
   ```
   Lavalink is ready to accept connections.
   ```

---

## Step 5 — Complete YouTube OAuth

1. In Render **Logs**, look for:
   ```
   Visit the following URL to authorize YouTube:
   https://www.youtube.com/activate?user_code=XXXX-XXXX
   ```
   > ⚠️ If you don't see this: confirm `YOUTUBE_OAUTH_ENABLED=true` is set on the
   > **Lavalink** service (not the bot), and that `YOUTUBE_SKIP_INIT` is not set.
   > Trigger a **Manual Deploy** if needed — the URL only appears on first boot
   > when no refresh token exists.

2. Open that URL on any device. Sign into Google → click **Allow**.

3. Back in Render Logs, look for:
   ```
   OAuth token saved. Refresh token: eyJhb...
   ```
   Copy the **entire** token (starts with `eyJ` — it will be long).

4. In Render → Lavalink service → **Environment**, add:

   | Key | Value |
   |---|---|
   | `YOUTUBE_REFRESH_TOKEN` | The token you copied |
   | `YOUTUBE_SKIP_INIT` | `true` |

5. Click **Save Changes** → Render redeploys. OAuth is now permanently active.

---

## Step 6 — Point your bot at the Lavalink server

Your Lavalink URL looks like:
```
https://lavalink-server.onrender.com
```
Find it under your service name in the Render dashboard (not `http://` — Render always uses HTTPS).

In your **bot's** Render service → **Environment**, set:

```
LAVALINK_URIS      = https://your-lavalink-name.onrender.com
LAVALINK_PASSWORDS = Zyrox#Lava2026!
```

Replace the URL and password with your actual values. The password must **exactly** match `LAVALINK_PASSWORD` on the Lavalink service.

### Adding public fallback nodes (optional but recommended)

If your self-hosted node restarts, having fallbacks means music continues on public nodes while yours comes back:

```
LAVALINK_URIS      = https://your-lavalink-name.onrender.com|https://lavalink-v4.triniumhost.com|https://lavalink.kennyy.com.br
LAVALINK_PASSWORDS = Zyrox#Lava2026!|free|kennyy.com.br
```

The bot tries nodes in order and fails over automatically.

---

## Step 7 — Redeploy the bot

After setting the bot's env vars, Render redeploys it automatically (with Auto-Deploy on).
Watch the **bot's** Render logs for:

```
[Music] Connected to N Lavalink node(s): https://your-lavalink-name.onrender.com ...
```

> If you see 0 nodes or a connection error, check Step 6 carefully — the most
> common mistake is `http://` vs `https://`, or a password mismatch.

---

## Troubleshooting

### "Visit the following URL" never appears in logs

- Confirm `YOUTUBE_OAUTH_ENABLED=true` is set on the **Lavalink** service — not the bot.
- Confirm `YOUTUBE_SKIP_INIT` is not set or is `false`.
- Trigger a **Manual Deploy** from the Render dashboard.

### OAuth token expired (429 errors return after working fine)

Tokens can expire after months of inactivity. To renew:
1. Delete `YOUTUBE_REFRESH_TOKEN` and `YOUTUBE_SKIP_INIT` from the Lavalink service.
2. Make sure `YOUTUBE_OAUTH_ENABLED=true`.
3. Deploy → get a new token from the logs (Step 5).
4. Add the new `YOUTUBE_REFRESH_TOKEN` and `YOUTUBE_SKIP_INIT=true`.
5. Redeploy.

### Build fails — "cannot download Lavalink-musl.jar"

The GitHub release URL changes when a new version is released. Update
`ARG LAVALINK_VERSION` in `Dockerfile` to the latest tag from
[github.com/lavalink-devs/Lavalink/releases](https://github.com/lavalink-devs/Lavalink/releases).
Do the same for `YTSOURCE_VERSION` and `LAVASRC_VERSION` if needed.

### Server starts but bot can't connect

- Use `https://` — not `http://` — Render always terminates TLS.
- Confirm the password in `LAVALINK_PASSWORDS` on the bot **exactly** matches
  `LAVALINK_PASSWORD` on the Lavalink service (case-sensitive, no trailing spaces).
- Confirm the bot service env vars were saved and a redeploy happened.

### Music cuts out every 15 minutes (free tier)

This is Render's spin-down: free web services sleep after 15 minutes with no
incoming HTTP traffic. The bot's WebSocket keeps the node alive during active
playback, but once everyone leaves voice channels and no commands run, it eventually
sleeps. **Upgrade to Starter ($7/mo)** to eliminate this entirely — no config
changes needed.

### Lavalink crashes (OOM)

- On free tier: leave `JAVA_OPTS` unset — the Dockerfile defaults to 300 MB heap.
- On Starter: set `JAVA_OPTS=-Xms64M -Xmx600M -XX:+UseG1GC`.
- Each active voice player uses ~5–15 MB of heap. 300 MB supports ~15–20 concurrent players on free tier.

### Spotify tracks play as wrong songs / low-quality matches

This usually means Spotify credentials are missing or wrong:
- Verify `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are set on the **Lavalink** service.
- Make sure your Spotify Developer app has at least one redirect URI (`http://localhost` is fine).
- ISRC-based matching (the default in this config) gives the most accurate results — no action needed.

### YouTube 429 even with OAuth

- Your OAuth token may be expired — see "OAuth token expired" above.
- Too many concurrent players for one node. Add a fallback node (Step 6) or upgrade.

---

## Updating Lavalink

When new versions are released:
1. Update `ARG LAVALINK_VERSION` in `Dockerfile`.
2. Update `ARG YTSOURCE_VERSION` if youtube-source updated.
3. Update `ARG LAVASRC_VERSION` if LavaSrc updated.
4. Push to GitHub — Render rebuilds automatically.

**Current versions:**

| Component | Version | Release page |
|---|---|---|
| Lavalink | 4.2.2 | [releases](https://github.com/lavalink-devs/Lavalink/releases) |
| youtube-source | 1.18.1 | [releases](https://github.com/lavalink-devs/youtube-source/releases) |
| LavaSrc | 4.8.3 | [releases](https://github.com/topi314/LavaSrc/releases) |

---

## Free alternatives to Render (no spin-down)

| Host | Free RAM | Notes |
|---|---|---|
| **Oracle Cloud Free Tier** | 1 GB (2× AMD VMs) | Best free option. Ubuntu VM + Java 17 + run the jar directly. |
| **Google Cloud Free Tier** | 1 GB (`e2-micro`) | Always-free in US regions. Same setup. |
| **Fly.io** | 256 MB | Tight but possible with `-Xmx200M`. Use this Dockerfile. |
| **Home server / old laptop** | Whatever you have | Ubuntu + Java 17 + port-forward 2333. |

**Quick direct-run (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install -y openjdk-17-jre wget
mkdir -p ~/lavalink/plugins && cd ~/lavalink
wget https://github.com/lavalink-devs/Lavalink/releases/download/4.2.2/Lavalink.jar
wget -O plugins/youtube-plugin.jar \
  https://github.com/lavalink-devs/youtube-source/releases/download/1.18.1/youtube-plugin-1.18.1.jar
wget -O plugins/lavasrc-plugin.jar \
  https://github.com/topi314/LavaSrc/releases/download/4.8.3/lavasrc-plugin-4.8.3.jar
# Copy application.yml from this repo into ~/lavalink/
export LAVALINK_PASSWORD="your-password"
export SPOTIFY_CLIENT_ID="your-id"
export SPOTIFY_CLIENT_SECRET="your-secret"
export YOUTUBE_OAUTH_ENABLED=true
java -Xms64M -Xmx900M -XX:+UseG1GC -jar Lavalink.jar
```
