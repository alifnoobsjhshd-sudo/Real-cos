import discord
from discord.ext import commands


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

    @commands.group()
    async def __Fun__(self, ctx: commands.Context):
        """Send anime reaction GIFs. Usage: `<fun_prefix> <keyword> @mention`\n\nKeywords: bite, boop, bully, cuddle, greet, handholding, highfive, hold, hug, insult, kill, kiss, lick, nom, pat, poke, punch, slap, snuggle, stare, tickle, wave, blush, cry, dance, happy, smile, smug, wag, headpat, triggered, thinking, shrug, tackle, bonk, nuzzle, yeet\n\nSlash: `/fun action:<keyword> user:<@member>`"""
        pass
