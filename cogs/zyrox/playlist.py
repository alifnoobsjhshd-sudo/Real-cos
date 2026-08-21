import discord
from discord.ext import commands


class _playlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Playlist commands"""

    def help_custom(self):
        from utils.emojis import e as _e
        emoji       = _e("zmusic")
        label       = "Playlist Commands"
        description = "Create, manage and play personal playlists"
        return emoji, label, description

    @commands.group()
    async def __Playlist__(self, ctx: commands.Context):
        """`playlist list` , `playlist create` , `playlist delete` , `song add` , `song remove`"""
