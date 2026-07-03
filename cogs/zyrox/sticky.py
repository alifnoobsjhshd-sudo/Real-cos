import discord
from discord.ext import commands


class _sticky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Sticky commands"""
  
    def help_custom(self):
		      emoji = '<:zpin:1448949810462855249>'
		      label = "Sticky Commands"
		      description = "Show you Commands of Sticky"
		      return emoji, label, description

    @commands.group()
    async def __Sticky__(self, ctx: commands.Context):
        """`sticky setup` , `sticky edit` , `sticky list` , `sticky remove`"""
        pass

