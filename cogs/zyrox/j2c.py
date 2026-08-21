import discord

from discord.ext import commands
from utils.emojis import e as _e

class _J2C(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Join To Create"""

    def help_custom(self):

              emoji = _e('zyrox_system')

              label = "J2C"

              description = "Show you Commands of J2C"

              return emoji, label, description

    @commands.group()

    async def __J2C__(self, ctx: commands.Context):

        """`>j2csetup`, `>j2creset`"""