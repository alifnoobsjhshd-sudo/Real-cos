---
name: Branding global defaults
description: How guild_id=0 stores global default branding; fallback chain in get_branding()
---

guild_id = 0 in the `guild_branding` table is the global default slot.

**Rule:** `get_branding(guild_id)` first looks for a guild-specific row, then falls back to `get_global_branding()` (guild_id=0), then falls back to hardcoded defaults (`DEFAULT_BRANDING = "Sunlight"`, `DEFAULT_COLOR = 0xFFD700`).

**Why:** Allows a control-server operator to set global defaults without affecting guilds that have customized their own branding.

**How to apply:** 
- Use `set_global_branding(**kwargs)` to write to guild_id=0.
- Use `reset_branding(guild_id)` to DELETE a guild's row (reverts it to global/default).
- The `/global_customization` command (restricted to ctrl_guild_id_* secrets + admin permission) is the only way to write global defaults.
