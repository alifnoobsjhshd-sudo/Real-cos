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
- ✅ Deezer (via LavaSrc — works without a key for metadata; needs a key for audio)

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

## Step 2 — Create a new Web Service on Render

1. Go to [render.com/dashboard](https://render.com) → **New → Web Service**
2. Connect your GitHub account and select the repo.
3. Fill in the settings:

| Setting | Value |
|---|---|
| **Name** | `lavalink` (or anything you like) |
| **Root Directory** | `lavalink-server` (Option A) / leave blank (Option B) |
| **Runtime** | `Docker` |
| **Instance Type** | **Starter ($7/month — 1 GB RAM)** — the free tier (512 MB) is too tight for Java + audio buffering |

> **Free tier note:** If you *must* use the free tier, set `JAVA_OPTS=-Xms32M -Xmx300M`
> in the env vars below. Expect occasional OOM crashes under load.

4. Click **Advanced** → make sure **Auto-Deploy** is on so every push updates automatically.

---

## Step 3 — Set environment variables

In Render → your Lavalink service → **Environment**, add:

| Key | Value | Required? |
|---|---|---|
| `LAVALINK_PASSWORD` | A strong password you choose (e.g. `Zyrox#Lava2026!`) | ✅ Yes |
| `JAVA_OPTS` | `-Xms64M -Xmx512M -XX:+UseG1GC` | Optional (default already set in Dockerfile) |
| `SPOTIFY_CLIENT_ID` | From [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) | For Spotify support |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard | For Spotify support |
| `DEEZER_MASTER_KEY` | Deezer master decrypt key | For full Deezer audio (optional) |

### Getting a free Spotify credential (takes 2 minutes)

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. **Create app** → any name → Redirect URI: `http://localhost`
3. Copy **Client ID** and **Client Secret** → paste into Render env vars above.

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
- Reduce `youtubePlaylistLoadLimit` in `application.yml` (currently 6).
- Add YouTube account credentials to `youtubeConfig` in `application.yml`.
- Use SoundCloud or Spotify as the primary source instead.

---

## Keeping Lavalink up to date

When a new Lavalink version is released:
1. Change `ARG LAVALINK_VERSION=4.x.x` in `Dockerfile`.
2. Change `ARG LAVASRC_VERSION=4.x.x` if LavaSrc also updated.
3. Push to GitHub — Render rebuilds automatically.
