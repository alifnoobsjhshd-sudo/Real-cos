# Lavalink Server — Render Deployment Guide

This folder contains everything needed to run your own Lavalink v4 server on Render.
After deploying it you will point your bot at it using the `LAVALINK_URIS` and
`LAVALINK_PASSWORDS` environment variables.

---

## What's included

| File | Purpose |
|---|---|
| `Dockerfile` | Downloads Lavalink 4.0.8 + LavaSrc plugin and runs them |
| `application.yml` | Full Lavalink config — sources, filters, plugins, logging |

**Sources enabled out of the box:**
- ✅ YouTube + YouTube Music
- ✅ SoundCloud
- ✅ Bandcamp, Twitch, Vimeo
- ✅ Spotify (via LavaSrc — needs a free Spotify app credential)
- ⚠️ Deezer (disabled by default — needs a master key; enable in `application.yml` only if you have one)

---

## Step 1 — Push the lavalink-server folder to GitHub

Render deploys from a Git repository.  You have two options:

### Option A — Deploy from the same repo (recommended)

Your bot is already in a GitHub repo.  Render lets you set a **Root Directory**
so it only builds the `lavalink-server/` subfolder.  No extra repo needed.

### Option B — Separate repo

Create a new GitHub repo, copy just the `lavalink-server/` folder contents
(Dockerfile + application.yml) into its root, and push.

---

## Step 2 — Choose your Render plan

### Free tier (tight, but possible)

The Dockerfile and `application.yml` are already tuned for Render's free tier:

- **Heap:** 300 MB (`JAVA_OPTS` in Dockerfile)
- **Audio quality:** lowered to `opusEncodingQuality: 5`
- **Frame buffer:** 2 seconds instead of 5 seconds
- **Playlist page load:** 3 pages instead of 6

Choose this if you have no money to spend. It will work for **1–2 concurrent streams**, light usage, and short playlists.

| Setting | Free tier value |
|---|---|
| **Name** | `lavalink` |
| **Root Directory** | `lavalink-server` |
| **Runtime** | `Docker` |
| **Instance Type** | **Free (512 MB RAM)** |

> ⚠️ **Important free-tier limitation:** Render free web services **spin down after 15 minutes of inactivity**. Lavalink keeps a WebSocket connection open to your bot, so when the server sleeps, the connection drops and any currently playing music stops. The bot will reconnect when someone runs `/play`, but you cannot have 24/7 background music on the free tier. This is a Render platform limit, not a Lavalink bug.

### Paid Starter (recommended for reliability)

If you later have $7/month, switch to **Starter (1 GB RAM)**. The default Dockerfile already works fine there — just leave `JAVA_OPTS` as-is.

4. Click **Advanced** → make sure **Auto-Deploy** is on so every push updates automatically.

---

## Step 3 — Set environment variables

In Render → your Lavalink service → **Environment**, add:

| Key | Value | Required? |
|---|---|---|
| `LAVALINK_PASSWORD` | A strong password you choose (e.g. `Zyrox#Lava2026!`) | ✅ Yes |
| `JAVA_OPTS` | `-Xms64M -Xmx512M -XX:+UseG1GC` | Optional (free-tier defaults already set in Dockerfile) |
| `SPOTIFY_CLIENT_ID` | From [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) | For Spotify support |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard | For Spotify support |
| `DEEZER_MASTER_KEY` | Deezer master decrypt key | Only if you enable `deezer: true` in `application.yml` |

### Getting a free Spotify credential (takes 2 minutes)

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
   and **Log in** with your Spotify account (free account is fine).
2. Click **Create app**.
   - **App name:** anything, e.g. `CodeX Music`
   - **App description:** anything, e.g. `Lavalink music source`
   - **Redirect URI:** `http://localhost`  (it doesn't need to be real; LavaSrc only needs the app to exist)
   - Check the box agreeing to the terms.
3. Click **Save**.
4. You are now on the app's overview page. Click **Settings** (top-right of the app page).
5. Under **Basic Information** you will see:
   - **Client ID** — a long string like `1a2b3c4d5e6f7g8h9i0j`
   - **Client Secret** — click **View client secret** to reveal it
6. Copy both values and paste them into your Render Lavalink service environment variables:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
7. Redeploy the Lavalink service. After it restarts, Spotify links will resolve.

---

## Step 4 — Deploy and get your URL

1. Click **Create Web Service** — Render will build the Docker image and start the server.
2. Build takes ~2–3 minutes (downloads Lavalink jar + plugin).
3. Once live the Render URL looks like:
   ```
   https://lavalink.onrender.com
   ```
4. In Render → your service → **Logs**, look for:
   ```
   Lavalink is ready to accept connections.
   ```
   That confirms the server is running.

---

## Step 5 — Point your bot at the new server

In your **bot's** Render service → **Environment**, set:

```
LAVALINK_URIS=https://your-lavalink-name.onrender.com
LAVALINK_PASSWORDS=Zyrox#Lava2026!
```

Replace the URL and password with your actual values.

### Adding a public node as fallback

If you want to keep a public node as a backup in case your server restarts:

```
LAVALINK_URIS=https://your-lavalink-name.onrender.com|https://lava-v4.ajieblogs.eu.org
LAVALINK_PASSWORDS=Zyrox#Lava2026!|https://dsc.gg/ajidevserver
```

The bot will use your node first and fall over to the public one automatically if yours is unreachable.

---

## Step 6 — Redeploy the bot

After updating the bot's env vars, Render will automatically redeploy it. Once it
comes back up, watch the bot logs for:

```
[Music] Connected to 1 Lavalink node(s): https://your-lavalink-name.onrender.com
```

---

## Troubleshooting

### Build fails — "could not download Lavalink.jar"
Render's build containers have internet access. If the GitHub release URL changes
with a new Lavalink version, update `ARG LAVALINK_VERSION` in `Dockerfile`.

### Server starts but bot can't connect
- Make sure the bot is using `https://` not `http://` for the Render URL (Render
  always puts HTTPS in front of your service).
- Confirm the password in `LAVALINK_PASSWORDS` matches `LAVALINK_PASSWORD` on the
  Lavalink service exactly.

### Lavalink crashes after a few songs (OOM)
- Upgrade to the Render Starter plan (1 GB RAM) if on free tier.
- Or set `JAVA_OPTS=-Xms32M -Xmx300M` and accept slightly slower GC pauses.

### Spotify not working
- Double-check `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are set on the
  **Lavalink** service (not the bot service).
- In the Spotify Developer Dashboard, make sure the app's **Redirect URI** has
  at least one entry (it doesn't need to be real).

### YouTube gives 429 Too Many Requests
Public Lavalink nodes rotate IPs to avoid this. On a single IP it can happen
under heavy load. Options:
- Reduce `youtubePlaylistLoadLimit` in `application.yml` (currently 3 for free tier).
- Add YouTube account credentials to `youtubeConfig` in `application.yml`.
- Use SoundCloud or Spotify as the primary source instead.

### Free tier — music stops after 15 minutes of no commands
This is the **Render free-tier spin-down**. The server sleeps when no WebSocket
traffic happens. It will reconnect on the next `/play`. For 24/7 music you need a
paid plan or a different free host that does not sleep. See the alternatives below.

---

## Free alternatives to Render (if the spin-down is a problem)

If you need music that stays on without waking up, Render free is the wrong
choice because of the 15-minute sleep rule. These are genuinely free options
with more RAM or no sleep:

| Host | Free tier | Notes |
|---|---|---|
| **Oracle Cloud Free Tier** | 2x AMD VM, 1 GB RAM each | Best free option. Create an Ubuntu instance, install Java 17, upload `application.yml` + `Lavalink.jar`, and run it. |
| **Google Cloud Free Tier** | 1x `e2-micro` (1 GB RAM) | Always-free VM in US regions. Same setup: install Java, run the jar. |
| **AWS Free Tier** | 1x `t2.micro` (1 GB RAM) for 12 months | Good for one year. |
| **Fly.io** | 256 MB RAM, no sleep | Tight but possible; use the same Dockerfile in this folder. |
| **Old laptop / PC** | Whatever RAM you have | Run Ubuntu or Debian, install Java 17, and forward port 2333 from your router. Completely free. |

For any of these, use the same `application.yml` and the same `Lavalink.jar` the
Dockerfile downloads. The only difference is you run it directly instead of inside Docker.

### Quick direct-run command (Ubuntu/Debian)

```bash
sudo apt update && sudo apt install -y openjdk-17-jre wget
mkdir -p ~/lavalink && cd ~/lavalink
wget https://github.com/lavalink-devs/Lavalink/releases/download/4.0.8/Lavalink.jar
mkdir -p plugins
wget -O plugins/lavasrc-plugin.jar https://github.com/topi314/LavaSrc/releases/download/4.3.0/lavasrc-plugin-4.3.0.jar
# Copy application.yml from this repo into ~/lavalink/
export LAVALINK_PASSWORD="your-password"
export SPOTIFY_CLIENT_ID="your-id"
export SPOTIFY_CLIENT_SECRET="your-secret"
java -Xms32M -Xmx300M -jar Lavalink.jar
```

---

## Keeping Lavalink up to date

When a new Lavalink version is released:
1. Change `ARG LAVALINK_VERSION=4.x.x` in `Dockerfile`.
2. Change `ARG LAVASRC_VERSION=4.x.x` if LavaSrc also updated.
3. Push to GitHub — Render rebuilds automatically.
