# CodeX / Cos Discord Bot

A feature-rich Discord bot with moderation, anti-nuke, automod, AI chat (Groq), music, games, and more.

## Current deployment

This bot is deployed and runs on **Render** as a web service. Replit is used for
development and code changes; production environment variables and persistent
storage are configured in the Render service.

## How to run

1. Add the required secrets in the **Secrets** tab (see below).
2. Click **Run** — the workflow `Start application` runs `python CodeX.py`.
3. The bot also starts a small Flask keep-alive server on port 19346 (exposed as port 80).

## Required secrets

| Secret key    | Where to get it |
|---------------|-----------------|
| `TOKEN`       | [Discord Developer Portal](https://discord.com/developers/applications) → your app → Bot → Token |
| `GROQ_API_KEY`| [Groq Console](https://console.groq.com/) — used for the AI/chatbot cog |

Supabase is optional for the existing bot until a cog is migrated to use it.
When using the Supabase helper, configure `SUPABASE_URL` and `SUPABASE_KEY` in
Replit Secrets for development and in the Render service's **Environment** for
production.

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

## Music / Lavalink configuration

The music cog can connect to **one or more Lavalink nodes** for automatic failover.

### Single node (legacy)

```
LAVALINK_URI=https://your-lavalink.example.com
LAVALINK_PASSWORD=your-password
```

### Multiple nodes (recommended for uptime)

```
LAVALINK_URIS=https://your-node.com|https://fallback-node.com|http://node3:2333
LAVALINK_PASSWORDS=pass1|pass2|pass3
```

- Separate entries with `|`.
- If the password list is shorter than the URI list, the last password is repeated.
- A bare host with a port (e.g., `lavalink:2333`) is treated as `http://`; a bare host without a port is treated as `https://`.
- wavelink will use the next available node automatically if one drops.

### Free tier / Render note

Hosting your own Lavalink server on Render's free tier (512 MB RAM) is possible only for very light usage (1–2 concurrent streams). For a reliable bot, run Lavalink on a VPS with at least 1 GB RAM, or combine your own node with a public fallback using the multi-node format above.

## Supabase integration

The bot has a ready-to-use Supabase client at `utils/supabase_client.py`.

### Setup (one-time)

1. Go to [supabase.com](https://supabase.com) → your project → **Settings → API**.
2. Copy your **Project URL** and **anon / public key** (or service-role key for admin ops).
3. Add them to **Replit Secrets** (padlock icon in the sidebar):
   - `SUPABASE_URL` = `https://yourproject.supabase.co`
   - `SUPABASE_KEY` = your anon or service-role key
4. Because production runs on Render, add the same two variables to your
   Render service under **Environment**, then redeploy the service.
5. Keep the `service_role` key only in Render's server-side environment; never
   expose it in client-side code or commit it to the repository.

### Using it in a cog

```python
from utils.supabase_client import get_supabase, sb_select, sb_upsert, sb_delete

# Raw client — full Supabase Python SDK
sb = get_supabase()
result = sb.table("my_table").select("*").execute()

# Convenience helpers (async-friendly wrappers)
rows  = await sb_select("guilds", {"guild_id": str(ctx.guild.id)})
await sb_upsert("guilds", {"id": str(ctx.guild.id), "prefix": ">"}, on_conflict="id")
await sb_delete("warns", {"guild_id": str(ctx.guild.id), "user_id": str(member.id)})
```

The existing SQLite databases are **unchanged** — Supabase is additive.

---

## Custom Emoji System — Branch 4

All bot-facing messages, buttons, and embeds use custom emojis via `utils/emojis.py`.
New emojis in **branch4** were generated with `generate_emojis.py` and must be uploaded
to Discord via `/upload emojis branch:branch4` (overflow to `branch5` if needed).

After uploading, copy the resulting emoji IDs into the `_FALLBACK` dict in `utils/emojis.py`
and run `reload_store()` or restart the bot so the store picks up the new IDs.

**Branch4 emojis (27 total):**
`zpoll`, `zimage`, `zbroom`, `zmood`, `zmask`, `zbrain`, `zflower`, `zrefresh`,
`zcoffee`, `zpickaxe`, `zplug`, `zclipboard`, `zvote`, `zbirthday`, `zenvelope`,
`zvoice`, `zbook`, `znum1`–`znum10`

**Design rule:** Dropdown `placeholder` strings always keep Unicode emojis — Discord
renders custom emojis poorly in placeholder text.

## Recent system behavior

- Ticket panels allow a user to open any number of tickets. Ticket panel buttons
  use the bot's uploaded `zticket` custom emoji.
- Playlist playback resolves and queues the full playlist before starting, so the
  track-end listener can reliably start the next song. Playlist now-playing
  messages are removed between tracks and contain only the existing song display,
  Playlist, and Save actions.
- Automatic logging creates its category as `<branding name> logs` using the
  guild's configured branding. `/log reset` clears the saved configuration and
  removes the configured logging channels/category when Discord permissions allow.
- The help menu places Leveling, Ticket, and Logging in Main Commands and exposes
  Poll Commands under Extra Commands. Slash entries are displayed with `/`.

---

## User preferences

- Keep the existing project structure and stack.
- Bot is deployed on Render as a web service.
