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

## User preferences

- Keep the existing project structure and stack.
