import discord
from discord.ext import commands


class _mc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Minecraft commands"""
  
    def help_custom(self):
		      emoji = '<:zmc:1448964387426537474>'
		      label = "Minecraft Commands"
		      description = "Show you Commands of Minecraft"
		      return emoji, label, description

    @commands.group()
    async def __Minecraft__(self, ctx: commands.Context):
        """`minecraft setup` , `minecraft reset` , `minecraft status`"""
        pass
