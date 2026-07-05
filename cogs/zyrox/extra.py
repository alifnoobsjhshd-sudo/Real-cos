import discord
from discord.ext import commands
from utils.emojis import e as _e


class _extra(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Utility commands"""
  
    def help_custom(self):
		      emoji = _e('zwrench')
		      label = "Utility Commands"
		      description = "Show you Commands of Utility"
		      return emoji, label, description

    @commands.group()
    async def __Utility__(self, ctx: commands.Context):
        """`botinfo` , `stats` , `invite` , `serverinfo` , `userinfo` , `roleinfo` , `ping` , `github` , `channelinfo` , `badges` , `banner user` , `banner server` , `reminder start` , `reminder clear` , `timer`\n\n__**Media Commands**__\n`media` , `media setup` , `media remove` , `media config`"""