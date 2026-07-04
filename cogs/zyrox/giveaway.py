import discord
from discord.ext import commands
from utils.emojis import e as _e


class _giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Giveaway commands"""
  
    def help_custom(self):
		      emoji = _e('ztada')
		      label = "Giveaway Commands"
		      description = "Show you Commands of Giveaway"
		      return emoji, label, description

    @commands.group()
    async def __Giveaway__(self, ctx: commands.Context):
        """`gstart`, `gend`, `greroll` , `glist`"""