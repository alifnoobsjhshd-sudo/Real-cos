import discord

from discord.ext import commands

class _vanity(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Vanity Roles"""

    def help_custom(self):

              emoji = '<:starr:1448951307707748395>'

              label = "Vanity"

              description = "Show you Commands of Vanity Roles"

              return emoji, label, description

    @commands.group()

    async def __Vanity__(self, ctx: commands.Context):

        """`>vanityroles setup` , `>vanityroles reset `, `>vanityroles show` ,"""