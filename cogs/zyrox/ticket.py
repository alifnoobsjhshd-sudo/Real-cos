import discord

from discord.ext import commands

class _ticket(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Ticket"""

    def help_custom(self):

              emoji = '<:zticket:1448951318713470987>'

              label = "Ticket"

              description = "Show you Commands of Ticket"

              return emoji, label, description

    @commands.group()

    async def __Ticket__(self, ctx: commands.Context):

        """`/ticket setup`, `/ticket close`, `/ticket lock`, `/ticket claim`, `/ticket unlock`, `/ticket transcript`"""