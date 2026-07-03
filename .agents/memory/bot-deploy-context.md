---
name: Bot deploys on Render not Replit
description: discord.py is not installed in the Replit shell; use py_compile for syntax checks
---

**Rule:** This bot is deployed on Render. The Replit workspace is only for editing. `discord` is not installed in the Replit Python env, so `import discord` will fail in shell.

**Why:** Attempting `python -c "from cogs.x import Y"` always errors with `ModuleNotFoundError: No module named 'discord'`. This is NOT a bug in the code.

**How to apply:**
- Use `python -m py_compile <file>` for syntax checks — these work without discord installed.
- Never try to start the bot locally from Replit; it won't work.
- The `Start application` workflow (`python CodeX.py`) is not functional here; ignore it.
