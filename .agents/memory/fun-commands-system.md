---
name: Fun commands system
description: Root cause of fun commands not working + how the system is structured
---

## Root cause (investigated and fixed)

`on_message` listeners read `message.content`, which Discord sends as an empty string
when the **MESSAGE_CONTENT privileged intent is not enabled** in the Discord Developer
Portal — even if `discord.Intents.all()` is set in code. This caused the listener to
hit `if not content: return` silently with no response.

Leveling/autoresponder "appeared" to work because their `on_message` handlers don't
parse content (they only check `message.author.bot` / `message.guild`).

## Fix

`/sun action:<autocomplete> user:<member>` slash command added as the **primary**
interface in `cogs/commands/fun.py`. Slash command parameters come from the Discord
interaction, not from message content — no privileged intent required.

The `on_message` listener is kept as a **bonus** (fires when MESSAGE_CONTENT intent IS
enabled in the Portal). Both paths share `_build_embed()`.

**Why:** Slash commands are always the robust choice for new features on this bot
because the Developer Portal intent setup cannot be verified from code.

**How to apply:** For any new bot feature that needs to read arbitrary message text,
prefer slash commands over on_message listeners unless MESSAGE_CONTENT intent is
confirmed enabled.

## Structure

- `PAST_TENSE`, `EMOTIONS`, `_WAIFUPICS`, `KEYWORDS` — module-level dicts
- `Fun._get_gif(keyword)` — fetches from waifu.pics SFW API (free, no key)
- `Fun._build_embed(author, target, keyword)` — shared embed builder
- `Fun.sun` — `/sun` slash command with autocomplete on `action` param
- `Fun._sun_autocomplete` — `@sun.autocomplete("action")` handler
- `Fun.on_message` — message trigger `sun <keyword> @mention`

## waifu.pics API

Base URL: `https://api.waifu.pics/sfw/{endpoint}` — returns `{"url": "..."}`.
Free, no auth required. 5-second timeout. Falls back to no-image embed on failure.
