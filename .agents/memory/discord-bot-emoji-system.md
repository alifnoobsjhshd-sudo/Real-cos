---
name: Discord bot emoji system
description: Central custom-emoji helper; help command keeps custom emojis, all others use Unicode
---

**Rule:** All emojis go through `utils/emojis.py` (`e` shorthand from `from utils.emojis import e as _e`). The help command intentionally uses custom Discord emojis (uploaded via `/upload`). All other bot messages use plain Unicode emojis for portability.

**Why:** Custom emojis only render if the bot is in the server that owns them. Help embed is safe because it always runs in a server context where the bot has those emojis. Embed messages may be sent cross-server so they use Unicode.

**How to apply:** In new commands, use Unicode emojis directly (e.g. `✅`, `❌`). Only use `_e("emojiname")` in help-cog docstrings or dedicated help embeds.
