# Lavalink Server — Render Deployment Guide

This folder contains everything needed to run your own Lavalink v4 server on Render.
Once deployed you point your bot at it using the `LAVALINK_URIS` and `LAVALINK_PASSWORDS`
environment variables.

**What's included:**

| File | Purpose |
|---|---|
| `Dockerfile` | Lavalink 4.2.2 + youtube-source 1.18.1 + LavaSrc 4.8.3, tuned for Alpine + low RAM |
| `application.yml` | Full config — sources, clients, OAuth, Spotify, filters |

**Sources enabled out of the box:**
- ✅ YouTube + YouTube Music  
- ✅ SoundCloud, Bandcamp, Twitch, Vimeo  
- ✅ Spotify (via LavaSrc — needs a free Spotify app key)  
- ⚠️ Deezer — disabled by default (enable in `application.yml` only if you have a master key)

---

## Step 1 — Choose how to deploy

### Option A — From your existing bot repo (recommended)

Render lets you set a **Root Directory** per service, so it only builds the
`lavalink-server/` subfolder. You don't need a separate repo.

### Option B — Separate repo

Create a new GitHub repo, copy just the `lavalink-server/` folder contents into
its root, push, and connect that repo in Render.

---

## Step 2 — Create the Render web service

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**.
2. Connect your GitHub repo.
3. Fill in these fields:

| Setting | Value |
|---|---|
| **Name** | `lavalink` (or anything you like) |
| **Root Directory** | `lavalink-server` |
| **Runtime** | `Docker` |
| **Instance Type** | See below |

**Instance type:**

| Tier | RAM | Recommended for |
|---|---|---|
| **Free (512 MB)** | 512 MB | Testing / light use. Spins down after 15 min of inactivity — music stops until someone runs `/play` again. |
| **Starter ($7/mo)** | 1 GB | Best value. Stays online 24/7, handles 3–5 concurrent streams. |
| **Standard ($25/mo)** | 2 GB | Heavy use / large servers with many concurrent streams. |

4. Click **Advanced** → confirm **Auto-Deploy** is on.
5. Click **Create Web Service** — do NOT add env vars yet (do Step 3 first).

---

## Step 3 — Set environment variables

In Render → your Lavalink service → **Environment**, add the following.

### Required

| Key | Value | Notes |
|---|---|---|
| `LAVALINK_PASSWORD` | A strong password you choose, e.g. `Zyrox#Lava2026!` | Must match what you set in the bot env vars |

### For Spotify support (free, takes 2 minutes)

| Key | Value |
|---|---|
| `SPOTIFY_CLIENT_ID` | From [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard |

**Getting Spotify credentials:**
1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and log in (free account is fine).
2. Click **Create app** — name it anything, set redirect URI to `http://localhost`.
3. Open your new app → **Settings** → copy **Client ID** and **Client Secret**.
4. Paste both into your Lavalink service env vars.

### For YouTube OAuth (strongly recommended)

YouTube OAuth makes your server dramatically more reliable — it drastically
reduces 429 rate-limit errors and "Video unavailable" blocks.

**First deployment — to get your token:**

| Key | Value |
|---|---|
| `YOUTUBE_OAUTH_ENABLED` | `true` |

Leave `YOUTUBE_REFRESH_TOKEN` and `YOUTUBE_SKIP_INIT` **unset** for now.

> This tells Lavalink to print the authorization URL in its logs.
> If you skip this step and jump straight to setting a token, the token won't be used.

### Optional

| Key | Value | Notes |
|---|---|---|
| `JAVA_OPTS` | `-Xms64M -Xmx600M -XX:+UseG1GC` | Starter plan only — gives more heap. Leave unset on free tier. |
| `DEEZER_MASTER_KEY` | your key | Only if you enable `deezer: true` in `application.yml` |

---

## Step 4 — Deploy and watch the logs

1. Click **Save Changes** → Render triggers a deploy.
2. Build takes ~2–3 minutes (downloads Lavalink jar + plugins during image build).
3. Once live, open **Logs** and look for:
   ```
   Lavalink is ready to accept connections.
   ```

---

## Step 5 — Complete YouTube OAuth (if you enabled it)

1. In **Logs**, look for a line that looks like this:
   ```
   Visit the following URL to authorize YouTube: https://www.youtube.com/activate?user_code=XXXX-XXXX
   ```
   > ⚠️ If you don't see this line, make sure `YOUTUBE_OAUTH_ENABLED=true` is set
   > and `YOUTUBE_SKIP_INIT` is **not** set (or is `false`).

2. Open that URL in **any browser** on any device. Sign in to your Google account and click **Allow**.

3. Back in Render **Logs**, look for:
   ```
   OAuth token saved. Refresh token: eyJhb...
   ```
   Copy the full token (starts with `eyJ` — it will be long).

4. Go to Render → your Lavalink service → **Environment** and add:

   | Key | Value |
   |---|---|
   | `YOUTUBE_REFRESH_TOKEN` | The token you just copied |
   | `YOUTUBE_SKIP_INIT` | `true` |

   > Setting `YOUTUBE_SKIP_INIT=true` stops Lavalink from printing the auth URL on
   > every future restart (since you already have a token).

5. Click **Save Changes** → Render redeploys. OAuth is now active.

---

## Step 6 — Point your bot at the new server

Your Render Lavalink URL looks like:
```
https://lavalink.onrender.com
```
(Find it under your service name in the Render dashboard.)

In your **bot's** Render service → **Environment**, set:

```
LAVALINK_URIS=https://your-lavalink-name.onrender.com
LAVALINK_PASSWORDS=Zyrox#Lava2026!
```

Replace the URL and password with your actual values.

### Adding public fallback nodes (optional but recommended)

Your server might restart occasionally. Adding fallback nodes means music keeps
playing on the public ones while yours comes back:

```
LAVALINK_URIS=https://your-lavalink-name.onrender.com|https://lavalink-v4.triniumhost.com|https://lavalink.kennyy.com.br
LAVALINK_PASSWORDS=Zyrox#Lava2026!|free|kennyy.com.br
```

The bot will use your node first and fail over automatically.

---

## Step 7 — Redeploy the bot

After updating the bot's env vars, Render redeploys it automatically. Watch the
bot logs for:

```
[Music] Connected to N Lavalink node(s): https://your-lavalink-name.onrender.com ...
```

---

## Troubleshooting

### "Visit the following URL" never appears in logs

- Confirm `YOUTUBE_OAUTH_ENABLED=true` is set in your **Lavalink** service (not the bot).
- Confirm `YOUTUBE_SKIP_INIT` is **not** set or is `false`.
- Trigger a manual redeploy — the URL appears only on first boot when no token exists.

### OAuth token expired — 429 errors return after working fine

YouTube refresh tokens can expire if unused for several months.
Repeat Step 5: temporarily remove `YOUTUBE_REFRESH_TOKEN` and `YOUTUBE_SKIP_INIT`,
redeploy, get a new token, then restore both env vars and redeploy again.

### Build fails — cannot download Lavalink.jar

The GitHub release URL changes when a new version is released. Update
`ARG LAVALINK_VERSION` in the `Dockerfile` to the latest tag on
[github.com/lavalink-devs/Lavalink/releases](https://github.com/lavalink-devs/Lavalink/releases).

### Server starts but bot can't connect

- Use `https://` not `http://` — Render always serves HTTPS.
- Make sure the password in the bot's `LAVALINK_PASSWORDS` matches `LAVALINK_PASSWORD`
  on the Lavalink service **exactly** (case-sensitive).

### Music cuts out every 15 minutes (free tier)

This is Render's spin-down behaviour — free web services sleep after 15 minutes of
no traffic. The WebSocket connection from the bot keeps it alive during active use,
but if everyone leaves the voice channel and no commands are run, the server sleeps.
Upgrade to **Starter ($7/mo)** to eliminate this. No config changes needed — the
same Dockerfile and `application.yml` work on all tiers.

### Lavalink crashes with OOM (Out of Memory)

- On free tier: leave `JAVA_OPTS` unset (the Dockerfile defaults to 300 MB heap).
- On Starter: set `JAVA_OPTS=-Xms64M -Xmx600M -XX:+UseG1GC` (600 MB heap).
- Reduce concurrent listeners — each active voice connection uses ~5–10 MB of heap.

### Spotify not resolving tracks

- `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` must be set on the **Lavalink**
  service, not the bot.
- In the Spotify Developer Dashboard, make sure your app has at least one redirect
  URI set (the value doesn't matter — `http://localhost` is fine).

### YouTube gives 429 even with OAuth

Your OAuth token may have expired. See **"OAuth token expired"** above.
If the token is fresh, reduce the number of concurrent players or switch some
users to SoundCloud (`scsearch:`) or Spotify links.

---

## Keeping Lavalink up to date

When a new version is released:
1. Update `ARG LAVALINK_VERSION` in `Dockerfile`.
2. Update `ARG YTSOURCE_VERSION` if youtube-source also updated.
3. Update `ARG LAVASRC_VERSION` if LavaSrc also updated.
4. Push to GitHub — Render rebuilds automatically.

Current versions baked into this setup:

| Component | Version |
|---|---|
| Lavalink | 4.2.2 |
| youtube-source | 1.18.1 |
| LavaSrc | 4.8.3 |

---

## Free alternatives to Render (no spin-down)

If you need 24/7 music and can't afford Render Starter, these options are genuinely free:

| Host | Free RAM | Notes |
|---|---|---|
| **Oracle Cloud Free Tier** | 1 GB (2× AMD VMs) | Best free option. Create Ubuntu VM, install Java 17, run the jar directly. |
| **Google Cloud Free Tier** | 1 GB (`e2-micro`) | Always-free in US regions. Same setup — install Java 17, run the jar. |
| **Fly.io** | 256 MB | Tight but possible with the `-Xmx200M` JVM flag. Use this Dockerfile. |
| **Old laptop / PC** | Whatever you have | Install Ubuntu + Java 17, run the jar, forward port 2333 on your router. |

**Quick direct-run (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install -y openjdk-17-jre wget
mkdir -p ~/lavalink/plugins && cd ~/lavalink
wget https://github.com/lavalink-devs/Lavalink/releases/download/4.2.2/Lavalink.jar
wget -O plugins/youtube-plugin.jar https://github.com/lavalink-devs/youtube-source/releases/download/1.18.1/youtube-plugin-1.18.1.jar
wget -O plugins/lavasrc-plugin.jar https://github.com/topi314/LavaSrc/releases/download/4.8.3/lavasrc-plugin-4.8.3.jar
# Copy application.yml from this repo into ~/lavalink/
export LAVALINK_PASSWORD="your-password"
export SPOTIFY_CLIENT_ID="your-id"
export SPOTIFY_CLIENT_SECRET="your-secret"
export YOUTUBE_OAUTH_ENABLED=true
java -Xms64M -Xmx900M -XX:+UseG1GC -jar Lavalink.jar
```
