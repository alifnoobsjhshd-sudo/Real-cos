import discord

from discord.ext import commands
from utils.emojis import e as _e

class inviteTracker(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Invite Tracker"""

    def help_custom(self):

              emoji = _e('zpeople')

              label = "Invite Tracker"

              description = "Show you Commands of Invite Tracker"

              return emoji, label, description

    @commands.group()

    async def __InviteTracker__(self, ctx: commands.Context):

        """`>invites`, `>addinvites`, `>inviteleaderboard`, `>invitelogging`, `>i`"""