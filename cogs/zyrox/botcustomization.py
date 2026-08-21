import discord
from discord.ext import commands


class _botcustomization(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # help_custom() intentionally removed so this cog does NOT appear
    # in the help dropdown. The /botcustomization slash command is the
    # primary entry point for this feature.

    @commands.group()
    async def __BotCustomization__(self, ctx: commands.Context):
        """`botcustomization` — Open the bot customization panel to change branding, embed colors, thumbnails, banners, and the bot's server profile."""
