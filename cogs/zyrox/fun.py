import discord
from discord.ext import commands
from cogs.commands.fun import FUN_HELP_MESSAGE


class _fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Fun commands"""

    def help_custom(self):
        from utils.emojis import e as _e
        import sqlite3
        emoji = _e('zrocket')
        label = "Fun Commands"
        # Read the global fun prefix from branding DB (sync) so help reflects the current setting
        try:
            conn = sqlite3.connect("db/branding.db")
            row = conn.execute(
                "SELECT fun_prefix FROM guild_branding WHERE guild_id=0"
            ).fetchone()
            conn.close()
            fun_prefix = (row[0] or "sun") if row else "sun"
        except Exception:
            fun_prefix = "sun"
        description = f"Anime-style reaction commands triggered with the `{fun_prefix}` prefix"
        return emoji, label, description

    @commands.group(name="fun", invoke_without_command=True)
    async def __Fun__(self, ctx: commands.Context):
        """Show Fun command usage and available commands."""
        await ctx.send(FUN_HELP_MESSAGE)
