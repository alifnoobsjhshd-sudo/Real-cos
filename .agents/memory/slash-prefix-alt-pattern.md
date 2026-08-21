---
name: Slash command prefix alternatives pattern
description: How to add prefix-command alternatives for slash-only commands, and the pitfall of accidentally nesting methods inside module-level helper functions.
---

## Pattern

For slash-only commands in a `commands.Cog`, add `@commands.command` methods inside the **class body** (not after it):

```python
class MyCog(commands.Cog):
    @app_commands.command(name="foo", ...)
    async def foo_slash(self, interaction: discord.Interaction, arg: str):
        ...  # slash version uses interaction

    @commands.command(name="foo", help="Same as /foo")
    async def foo_prefix(self, ctx: commands.Context, *, arg: str):
        ...  # prefix version uses ctx
```

## Critical pitfall — accidental nesting

If module-level helper functions follow the class in the file, methods placed *after* those helpers with 4-space indentation are NOT class methods — Python sees them as local functions nested inside the last helper. This is valid syntax (py_compile passes) but the `@commands.command` decorator does nothing on a local function.

**Symptom:** Commands don't appear in `>help` and `bot.get_command()` returns `None`.

**Fix:** Ensure prefix-command methods are placed *inside* the class body, before any module-level helpers.

## Interaction vs Context incompatibility

Slash (`@app_commands.command`) functions use `interaction: discord.Interaction` and `interaction.response.send_message()`. Prefix functions use `ctx: commands.Context` and `ctx.reply()`. They cannot share the same function signature. Write separate methods that share a common async helper, or simply duplicate the core logic in the prefix version.

## Emoji upload commands in this bot

`cogs/commands/emoji_upload.py` has three prefix commands registered as `EmojiUpload` class methods:
- `>emoji_export` — exports the emoji store JSON
- `>emoji_status` — shows per-branch upload state for the current server
- `>upload_emojis <branch>` — uploads an emoji branch directly (no modal)
