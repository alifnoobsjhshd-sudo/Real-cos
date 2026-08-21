import discord 
from discord.ext import commands 


class _leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Leveling commands"""

    def help_custom(self):
        from utils.emojis import e as _e
        emoji = _e('zlevelup')
        label = "Leveling Commands"
        description = "Shows you the commands of leveling"
        return emoji, label, description

    @commands.group()
    async def __Leveling__(self, ctx: commands.Context):
        """`level status`, `level enable`, `level disable`, `level channel #channel`, `level settings`, `level message <text>`, `level image <url>`, `level clearimage`, `level color <hex>`, `level thumbnail on/off`, `level xprange <min> <max>`, `level setxp <amount>`, `level cooldown <seconds>`, `level preview [level]`, `level rank [@user]`, `level stats [@user]`, `level leaderboard`, `level placeholders`, `level rewards add <level> @role`, `level rewards remove <level>`, `level rewards list`, `level addreward <level> @role`, `level removereward <level>`, `level multiplier add <role/channel> <id> <multiplier>`, `level multiplier remove <role/channel> <id>`, `level multiplier list`, `level blacklist add <role/channel> <id>`, `level blacklist channel #channel`, `level blacklist role @role`, `level blacklist list`, `level unblacklist channel #channel`, `level unblacklist role @role`, `level reset user @member`, `level reset all`"""
