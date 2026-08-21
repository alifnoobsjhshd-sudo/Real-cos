---
name: Prefix locked to > and activity persistence
description: Documents the prefix-lock decision and the custom activity persistence system added in this session.
---

## Prefix lock

`core/zyrox.py:get_prefix` no longer reads from the guild config DB — it always returns `">"` (plus empty string for noprefix users). The `_prefix` command in `cogs/moderation/moderation.py` was converted to an info-only command that displays this fact.

All user-facing strings that showed the per-guild prefix (e.g. `mention.py`, `help.py`) must use `">"` directly rather than calling `getConfig(guild_id)["prefix"]`.

**Why:** The prefix-change feature was removed at the owner's request. Single locked prefix simplifies the codebase and avoids stale config data causing confusing behavior.

## Custom activity persistence

`utils/branding.py` has a `bot_activity` table (in `db/branding.db`) with three functions:
- `get_custom_activity()` → returns `{type, name}` dict or `None`
- `set_custom_activity(type_str, name)` → saves activity
- `clear_custom_activity()` → deletes the row

`core/zyrox.py`:
- `self.use_custom_activity = False` on the bot instance
- `setup_hook` loads any persisted activity and sets the flag to `True` before starting `status_task`
- `status_task` returns early when `self.use_custom_activity` is `True`

`cogs/commands/botcustomization.py`:
- `GlobalActivityModal.on_submit` calls `set_custom_activity()` and sets `interaction.client.use_custom_activity = True`
- `GlobalBotProfileView` has a "Reset Activity" button that calls `clear_custom_activity()` and sets `use_custom_activity = False`, then calls `change_presence(activity=None)` to resume the rotating task on the next 30s tick.

**Why:** Previously any manually set activity was overwritten every 30 seconds by the `status_task` loop.
