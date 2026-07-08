# CodeX / Zyrox Discord Bot

A feature-rich Discord bot with moderation, anti-nuke, automod, AI chat (Groq), music, games, and more.

## How to run

1. Add the required secrets in the **Secrets** tab (see below).
2. Click **Run** — the workflow `Start application` runs `python CodeX.py`.
3. The bot also starts a small Flask keep-alive server on port 19346 (exposed as port 80).

## Required secrets

| Secret key    | Where to get it |
|---------------|-----------------|
| `TOKEN`       | [Discord Developer Portal](https://discord.com/developers/applications) → your app → Bot → Token |
| `GROQ_API_KEY`| [Groq Console](https://console.groq.com/) — used for the AI/chatbot cog |

## Project structure

```
CodeX.py          — Entry point; loads all cogs and starts the bot
config.yml        — Bot configuration (AI model, prefixes, presences, etc.)
core/             — Base bot class (zyrox), Context, Cog helpers
cogs/             — Feature modules (antinuke, automod, commands, events, moderation, zyrox)
db/               — SQLite databases (afk.db, ai_data.db)
assets/           — Images, fonts, emojis used by bot commands
utils/            — Shared utilities (Tools, config loader)
```

## Configuration

Edit `config.yml` to change:
- `MODEL_ID` — Groq model used for AI responses (default: `mixtral-8x7b-32768`)
- `TRIGGER` — prefixes/keywords that activate the chatbot
- `PRESENCES` — rotating status messages
- `MAX_HISTORY` — conversation memory length

Channel IDs for stats and logs are set at the top of `CodeX.py` (`SERVER_COUNT_CHANNEL_ID`, `USER_COUNT_CHANNEL_ID`, `LOG_CHANNEL_ID`).

## Persistent data (Render — IMPORTANT)

Render's filesystem is **ephemeral** — it resets on every redeploy, wiping all SQLite databases and config.

### Fix: Render Persistent Disk + DATA_DIR

1. In Render → your service → **Disks**, add a disk mounted at `/data` (1 GB is plenty).
2. In Render → **Environment**, add: `DATA_DIR` = `/data`
3. Redeploy — on first boot the bot copies all `.db` files to `/data` and replaces the local paths
   with symlinks, so they persist across every future redeploy automatically.

All 40+ SQLite databases in `db/`, root-level `j2c_data.db` / `rr.db`, and the emoji store in
`data/` are covered by this single env var.

### Emoji persistence (alternative / additional)

Custom emojis uploaded via `/upload emojis` are also saved to `data/emoji_store.json` (covered by
`DATA_DIR` above). As an extra fallback without a disk:

1. Upload all emoji branches once via `/upload emojis branch:<name>`.
2. Run `/emoji_export` — the bot sends a `emoji_store.json` file attachment.
3. Copy the entire JSON content.
4. In Render → **Environment**, add: `EMOJI_STORE_JSON` = `<paste full JSON here>`
5. Redeploy — the bot loads emojis from the env var automatically even without a disk.

### New emoji: j2c_wait

A new couch/sofa emoji for the J2C Waiting Room button was added.

1. Run `python generate_emojis.py` — creates `assets/emojis/j2c_wait.png`.
2. Upload it via `/upload emojis branch:features` in your Discord server.
3. The J2C interface embed and control panel will use it automatically.

## J2C system

After `>j2csetup` the bot creates:
- **➕ Join to Create** — voice channel (join to auto-create a private VC)
- **#interface** — read-only text channel with the branded button guide embed
  (no buttons here; buttons appear only inside the created private VC)

## Voice commands

- `/join-vc <channel>` — bot joins the selected VC and stays (admin only)
- `/leave-vc` — bot disconnects from the current VC (admin only)

## User preferences

- Keep the existing project structure and stack.
- Bot is deployed on Render as a web service.
