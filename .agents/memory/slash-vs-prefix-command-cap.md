---
name: Slash command cap strategy and sync kwargs
description: How this bot avoids Discord's 100 global slash command cap, and a gotcha about bot constructor kwargs.
---

- The bot constructor passes `sync_commands_debug=True` / `sync_commands=True` to `commands.AutoShardedBot.__init__`. These are **not real discord.py kwargs** — discord.py's `Client.__init__` silently absorbs unknown kwargs into `**options` and does nothing with them. They are vestigial (likely copied from pycord-style code) and have **zero effect**. Actual slash sync only happens via the explicit `client.tree.sync()` call in `on_ready` in `CodeX.py`.
- **Why this matters:** don't assume changing `sync_commands=True/False` changes sync behavior — it doesn't. Only `tree.sync()` (global) or `tree.sync(guild=...)` (per-guild, requires `copy_global_to` first) actually register commands with Discord.
- **Decision:** rather than guild-scoped sync (which is fiddly and was reverted after causing confusion), the bot's strategy for staying under Discord's 100-global-slash-command cap is to **keep most commands prefix-only** (`commands.command`/`commands.group`) and only expose a small, deliberately curated set as `hybrid_command` (slash-capable). E.g. music only exposes `/play` and `/stop`; role-grant commands (`staff`/`girl`/`vip`/`guest`/`friend`), `/setup`, `/prefix`, `/profile`/`/badges`, and `/join-vc`/`/leave-vc` are prefix-only.
- **How to apply:** before adding a new `hybrid_command`/`app_commands.command`, ask whether it truly needs to be a slash command — the default for new commands here should be prefix-only unless there's a clear reason (e.g. music playback controls where slash UX matters).
