---
name: hybrid_group bare-command invocation pitfall
description: Why bot.get_command("name") on a discord.py hybrid_group/group only returns the parent, and how bare invocation should be handled for game-style commands.
---

`bot.get_command("some-group-name")` on a `commands.hybrid_group`/`commands.group` always returns the **parent group**, never a subcommand. If another feature (e.g. a text-trigger listener) does `ctx.invoke(bot.get_command(name))` expecting the "real" action, it will run the bare group's own callback instead.

**Why this matters:** if the bare group callback just does `ctx.send_help(...)` (a common scaffolding default), any code path that resolves the command by top-level name only ever shows help — it silently never performs the action, with no error raised.

**How to apply:** For single-purpose group commands where users reasonably expect the bare command to just work (e.g. `>country-guesser` starting the game rather than requiring `>country-guesser start`), make the bare group callback perform the primary action directly when `ctx.invoked_subcommand is None`, instead of showing help. Keep the explicit subcommand too for discoverability/back-compat.
