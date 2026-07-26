import discord
import json
import aiosqlite
from discord.ext import commands
from utils.emojis import e as _e
from utils.config import serverLink
from core import zyrox, Cog, Context
from utils.Tools import get_ignore_data


def _friendly_type_hint(param) -> str:
    """Return a plain-language description of what should be put in an argument,
    based on its type annotation. Falls back to a generic hint if unknown."""
    annotation = param.annotation
    name = getattr(annotation, "__name__", str(annotation)).lower()

    hints = {
        "member": "mention a server member or paste their user ID (example: `@username`)",
        "user": "mention a user or paste their user ID (example: `@username`)",
        "role": "mention a role or paste its role ID (example: `@RoleName`)",
        "textchannel": "mention a text channel or paste its channel ID (example: `#general`)",
        "voicechannel": "mention a voice channel or paste its channel ID (example: `#voice-chat`)",
        "categorychannel": "mention a category or paste its category ID",
        "int": "enter a whole number (example: `5`)",
        "float": "enter a number (example: `2.5`)",
        "bool": "enter `true` or `false`",
        "str": "enter some text",
    }
    return hints.get(name, "fill in a value for this")


def _slash_alternative_hint(ctx: Context) -> str:
    """If a slash command with the same name exists, return a
    'use /(command) instead' hint string, otherwise an empty string."""
    try:
        slash_cmd = ctx.bot.tree.get_command(ctx.command.qualified_name)
        if slash_cmd is None:
            return ""
        return f"\n\n💡 Use `/{slash_cmd.qualified_name}` instead."
    except Exception:
        return ""


class Errors(Cog):
  def __init__(self, client: zyrox):
    self.client = client

  @commands.Cog.listener()
  async def on_command_error(self, ctx: Context, error):
    if ctx.command is None:
      return
    

    if isinstance(error, commands.CommandNotFound):
      return

    if isinstance(error, commands.MissingRequiredArgument):
      prefix = ctx.prefix or ">"
      usage = f"`{prefix}{ctx.command.qualified_name}"
      if ctx.command.usage:
          usage += f" {ctx.command.usage}"
      else:
          usage += f" {ctx.command.signature}"
      usage += "`"
      hint = _friendly_type_hint(error.param)
      embed = discord.Embed(
          color=0xFF0000,
          description=(
              f"{_e('zcross')} **You're missing something:** `{error.param.name}`\n\n"
              f"**What to do:** {hint}.\n\n"
              f"**How to use:** {usage}"
              f"{_slash_alternative_hint(ctx)}"
          ),
      )
      embed.set_author(name="Wrong Usage", icon_url=ctx.bot.user.display_avatar.url)
      embed.set_footer(text=f"Tip: type {prefix}help {ctx.command.qualified_name} for full info")
      await ctx.reply(embed=embed, mention_author=False)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(error, commands.CheckFailure):
      data = await get_ignore_data(ctx.guild.id)
      ch = data["channel"]
      iuser = data["user"]
      cmd = data["command"]
      buser = data["bypassuser"]

      if str(ctx.author.id) in buser:
        return

      if str(ctx.channel.id) in ch:
        await ctx.reply(f"{ctx.author.mention} **This channel was in ignored list try my commands on other channel**.",
                        delete_after=8)
        return

      if str(ctx.author.id) in iuser:
        await ctx.reply(f"{ctx.author.mention} **You are set as an ignored user for this guild. Please try my commands in a different guild.**", delete_after=8)
        return

      if ctx.command.name in cmd or any(alias in cmd for alias in ctx.command.aliases):
        await ctx.reply(f"{ctx.author.mention} **This command is ignored in this guild. Please use other commands or try this command in a different guild**", delete_after=8)
        return

    if isinstance(error, commands.NoPrivateMessage):
      embed = discord.Embed(color=0xFF0000, description="You can't use my commands in DMs.")
      embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      embed.set_thumbnail(url=ctx.author.display_avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      await ctx.reply(embed=embed, delete_after=20)
      return

    if isinstance(error, commands.TooManyArguments):
      prefix = ctx.prefix or ">"
      usage = f"`{prefix}{ctx.command.qualified_name}"
      if ctx.command.usage:
          usage += f" {ctx.command.usage}"
      usage += "`"
      embed = discord.Embed(
          color=0xFF0000,
          description=f"{_e('zcross')} **Too many arguments.**\n\n**How to use:** {usage}{_slash_alternative_hint(ctx)}",
      )
      embed.set_author(name="Wrong Usage", icon_url=ctx.bot.user.display_avatar.url)
      embed.set_footer(text=f"Tip: type {prefix}help {ctx.command.qualified_name} for full info")
      await ctx.reply(embed=embed, mention_author=False)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(error, commands.CommandOnCooldown):
      embed = discord.Embed(color=0xFF0000, description=f"**{ctx.author.mention} Couldown is here Bro Tryy commands in {error.retry_after:.2f} seconds**.")
      embed.set_author(name="Cooldown", icon_url=self.client.user.display_avatar.url)
      
      embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      await ctx.reply(embed=embed, delete_after=10)
      return

    if isinstance(error, commands.MaxConcurrencyReached):
      embed = discord.Embed(color=0xFF0000, description=f"{ctx.author.mention} This command is already in progress. Please let it finish and try again afterward.")
      embed.set_author(name="Command in Progress.", icon_url=self.client.user.display_avatar.url)
      
      embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      await ctx.reply(embed=embed, delete_after=10)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(error, commands.MissingPermissions):
      missing = [perm.replace("_", " ").replace("guild", "server").title() for perm in error.missing_permissions]
      fmt = "{}, and {}".format(", ".join(missing[:-1]), missing[-1]) if len(missing) > 2 else " and ".join(missing)
      embed = discord.Embed(color=0xFF0000, description=f"**Ops! You don't have {fmt} Permission to run the {ctx.command.name} command!**")
      embed.set_author(name="Missing Permissions", icon_url=self.client.user.display_avatar.url)
      
      embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
      await ctx.reply(embed=embed, delete_after=7)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(error, commands.BadArgument):
      prefix = ctx.prefix or ">"
      usage = f"`{prefix}{ctx.command.qualified_name}"
      if ctx.command.usage:
          usage += f" {ctx.command.usage}"
      usage += "`"
      embed = discord.Embed(
          color=0xFF0000,
          description=f"{_e('zcross')} **Invalid argument:** {error}\n\n**How to use:** {usage}{_slash_alternative_hint(ctx)}",
      )
      embed.set_author(name="Wrong Usage", icon_url=ctx.bot.user.display_avatar.url)
      embed.set_footer(text=f"Tip: type {prefix}help {ctx.command.qualified_name} for full info")
      await ctx.reply(embed=embed, mention_author=False)
      ctx.command.reset_cooldown(ctx)
      return

    if isinstance(error, commands.BotMissingPermissions):
      missing = ", ".join(error.missing_permissions)
      await ctx.reply(f'** Huh! I need {missing} Permission to run the {ctx.command.qualified_name}command! Give me {missing} Permission**', delete_after=7)
      return

    if isinstance(error, discord.HTTPException):
      return

    if isinstance(error, commands.CommandInvokeError):
      return

