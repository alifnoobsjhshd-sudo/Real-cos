import discord
from discord.ext import commands


class _fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Fun commands"""

    def help_custom(self):
        emoji = '<:zrocket:1448951445989888010>'
        label = "Fun Commands"
        description = "Anime-style reaction commands triggered with the `sun` prefix"
        return emoji, label, description

    @commands.group()
    async def __Fun__(self, ctx: commands.Context):
        """`sun bite @user`, `sun boop @user`, `sun bully @user`, `sun cuddle @user`, `sun greet @user`, `sun handholding @user`, `sun highfive @user`, `sun hold @user`, `sun hug @user`, `sun insult @user`, `sun kill @user`, `sun kiss @user`, `sun lick @user`, `sun nom @user`, `sun pat @user`, `sun pats @user`, `sun poke @user`, `sun punch @user`, `sun slap @user`, `sun snuggle @user`, `sun stare @user`, `sun tickle @user`, `sun wave @user`, `sun blush @user`, `sun cry @user`, `sun dance @user`, `sun happy @user`, `sun smile @user`, `sun smug @user`, `sun wag @user`, `sun headpat @user`, `sun triggered @user`, `sun thinking @user`, `sun shrug @user` — Send an anime reaction GIF to someone. Usage: sun <keyword> @mention"""
        pass
