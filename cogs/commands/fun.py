import discord
from discord.ext import commands
import random
from utils.Tools import blacklist_check, ignore_check

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Fun(bot))
