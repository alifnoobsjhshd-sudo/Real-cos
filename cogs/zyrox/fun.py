import discord
from discord.ext import commands


class _fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Fun commands"""

    def help_custom(self):
        emoji = '<:zrocket:1448951445989888010>'
        label = "Fun Commands"
        description = "Show you Commands of Fun"
        return emoji, label, description

    @commands.group()
    async def __Fun__(self, ctx: commands.Context):
        """Fun commands coming soon!"""
        pass
