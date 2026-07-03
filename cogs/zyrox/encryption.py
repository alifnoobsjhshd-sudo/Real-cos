import discord
from discord.ext import commands


class _encrypt(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Encryption commands"""
  
    def help_custom(self):
		      emoji = '<:lock:1448949549455511685>'
		      label = "Encryption Commands"
		      description = "Show you Commands of Encryption"
		      return emoji, label, description

    @commands.group()
    async def __Encryption__(self, ctx: commands.Context):
       """
       `encode base32`, `encode base64`, `encode rot13`, `encode hex`, `encode base85`, `encode ascii85`,`decode base32`, `decode base64`, `decode rot13`, `decode hex`, `decode base85`, `decode ascii85`, `password`,
       """
      

