import discord
from discord.ext import commands


class _antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Antinuke commands"""
  
    def help_custom(self):
		      emoji = '<:zSafe:1448951403434479626>'
		      label = "Security Commands"
		      description = "Show you Commands of Antinuke"
		      return emoji, label, description

    @commands.group()
    async def __Antinuke__(self, ctx: commands.Context):
        """`antinuke` , `antinuke enable` , `antinuke disable` , `whitelist` , `whitelist @user` , `unwhitelist` , `whitelisted` , `whitelist reset` , `extraowner` , `extraowner set` , `extraowner view` , `extraowner reset`, `nightmode` , `nightmode enable` , `nightmode disable`\n"""

