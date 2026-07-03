import discord

from discord.ext import commands

class _Counting(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Counting"""

    def help_custom(self):

              emoji = '<:zcounting:1448949348103749713>'

              label = "Counting"

              description = "Show you Commands of Counting"

              return emoji, label, description

    @commands.group()

    async def __Counting__(self, ctx: commands.Context):

        """`>counting`, `>counting enable/disable`, `>counting channel #channel`, `>counting stats`, `>counting config continue/reset`"""