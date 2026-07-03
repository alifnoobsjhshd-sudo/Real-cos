---
name: Discord bot custom emoji system
description: How custom Discord emojis are centrally managed in this bot, and where they are intentionally kept vs. replaced with Unicode.
---

The bot has a centralized custom-emoji registry at `utils/emojis.py` (`_FALLBACK` dict + `/upload emojis` store override), exposed via `e(name)`. Most cogs historically hardcoded literal `<:name:id>` / `<a:name:id>` tags directly in message strings instead of calling `e()`.

**Decision:** All user-facing bot messages (moderation, automod, security, tickets, giveaways, leveling, welcomer, etc.) were converted from literal custom emoji tags to plain Unicode emojis. The help system was deliberately left untouched:
- `cogs/commands/help.py` and `utils/help.py` (pagination/dropdown UI) still use `e()`/custom emojis.
- Each cog's `help_custom()` method and its `emoji = '<:name:id>'` attribute (used only to show a category icon in the help menu) were preserved.
- `utils/emojis.py` itself was left as-is since it still backs the help system and the `/upload emojis` feature.

**Why:** User explicitly asked to strip custom emojis from all bot messages except the help command, to reduce dependency on the bot having those emojis uploaded to a server, while keeping help's richer branded look.

**How to apply:** When adding new messages/embeds to non-help cogs, use Unicode emojis, not `e()`/custom tags. When touching help-related files, custom emojis via `e()` are still the correct pattern.

**Gotcha found during the mechanical replacement:** a naive regex like `_?e\(['"]name['"]\)` to catch `e("name")`/`_e('name')` call sites will false-positive match inside unrelated calls whose name ends in "e", e.g. `fetch_waifu_image("waifu")` contains `e("waifu")` as a substring. Always anchor such regexes with a `(?<![A-Za-z0-9_])` lookbehind (word boundary) before the `e(`, and recompile/py_compile every changed file afterward to catch corruption.
