import discord
from discord.ext import commands
from utils.emojis import e as _e


class _antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Antinuke commands"""
  
    def help_custom(self):
		      emoji = _e('zSafe')
		      label = "Security Commands"
		      description = "Show you Commands of Antinuke"
		      return emoji, label, description

    @commands.group()
    async def __Antinuke__(self, ctx: commands.Context):
        """`antinuke` , `antinuke enable` , `antinuke disable` , `whitelist` , `whitelist @user` , `unwhitelist` , `whitelisted` , `whitelist reset` , `extraowner` , `nightmode` , `nightmode enable` , `nightmode disable`\n"""

