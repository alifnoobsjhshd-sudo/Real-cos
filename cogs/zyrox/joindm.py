import discord
from discord.ext import commands

class _joindm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    """__Join Dm__"""
    def help_custom(self):
              emoji = '<:zmsg:1448964399166394483>'
              label = "Joindm"
              description = "Show you Commands of Joindm"
              return emoji, label, description
    @commands.group()
    async def __Joindm__(self, ctx: commands.Context):
        """`joindm enable` , `joindm disable` , `joindm message` , `joindm test`"""