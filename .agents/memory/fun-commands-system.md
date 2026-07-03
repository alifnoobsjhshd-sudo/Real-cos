---
name: Fun commands system
description: How the "sun <keyword> @mention" fun command listener works
---

**Rule:** Fun commands are triggered by `on_message` listener in `Fun` cog (`cogs/commands/fun.py`). Trigger format: message starting with `sun ` (case-insensitive), followed by a keyword from `KEYWORDS`, followed by at least one non-bot @mention.

**Why:** Prefix is "sun" (not a bot prefix character), so it must be an `on_message` listener, not a registered command.

**How to apply:**
- GIF source: waifu.pics SFW API (`https://api.waifu.pics/sfw/<endpoint>`), free, no API key needed. Maps in `_WAIFUPICS` dict.
- Title line rendered via `embed.set_author(name=..., icon_url=author.avatar_url)` to show author profile pic next to text.
- Embed color: 0xFFD700 (yellow).
- To add a new keyword: add to `PAST_TENSE`, `EMOTIONS`, and `_WAIFUPICS` dicts in fun.py, and update the docstring in `cogs/zyrox/fun.py`.
