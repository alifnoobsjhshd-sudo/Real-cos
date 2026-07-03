import discord
from discord.ext import commands


class _botcustomization(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def help_custom(self):
        emoji = '<:zwrench:1448951382597177495>'
        label = "Bot Customization"
        description = "Customize the bot's appearance & profile for this server"
        return emoji, label, description

    @commands.group()
    async def __BotCustomization__(self, ctx: commands.Context):
        """`botcustomization` — Open the bot customization panel to change branding, embed colors, thumbnails, banners, and the bot's server profile."""
