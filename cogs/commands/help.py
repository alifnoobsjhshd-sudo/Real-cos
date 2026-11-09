import discord
from discord.ext import commands
from discord import app_commands, Interaction
from difflib import get_close_matches
from contextlib import suppress
from core import Context
from core.zyrox import zyrox
from core.Cog import Cog
from utils.Tools import getConfig
from itertools import chain
import json
from utils import help as vhelp
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
import asyncio
from utils.config import serverLink
from utils.Tools import *
from utils.branding import get_branding, apply_branding_thumbnail, DEFAULT_COLOR, DEFAULT_BRANDING
from utils.emojis import e as _e

color = DEFAULT_COLOR
client = zyrox()

class HelpCommand(commands.HelpCommand):

  async def send_ignore_message(self, ctx, ignore_type: str):
    if ignore_type == "channel":
      await ctx.reply(f"This channel is ignored.", mention_author=False)
    elif ignore_type == "command":
      await ctx.reply(f"{ctx.author.mention} This Command, Channel, or You have been ignored here.", delete_after=6)
    elif ignore_type == "user":
      await ctx.reply(f"You are ignored.", mention_author=False)

  async def on_help_command_error(self, ctx, error):
    errors = [
      commands.CommandOnCooldown, commands.CommandNotFound,
      discord.HTTPException, commands.CommandInvokeError
    ]
    if not type(error) in errors:
      await self.context.reply(f"Unknown Error Occurred\n{error.original}",
                               mention_author=False)
    else:
      if type(error) == commands.CommandOnCooldown:
        return
    return await super().on_help_command_error(ctx, error)

  async def command_not_found(self, string: str) -> None:
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
        return

    if not check_ignore:
        await self.send_ignore_message(ctx, "command")
        return

    cmds = (str(cmd) for cmd in self.context.bot.walk_commands())
    matches = get_close_matches(string, cmds)

    branding = await get_branding(self.context.guild.id)
    embed = discord.Embed(
        title=f"{branding['branding_name']} Helper",
        description=f">>> **Ops! Command not found with the name** `{string}`.",
        color=branding["embed_color"]
    )
    apply_branding_thumbnail(embed, branding, self.context.author)
    if branding.get("embed_banner"):
        embed.set_image(url=branding["embed_banner"])
                          
    #if matches:
        #match_list = "\n".join([f"{index}. `{match}`" for index, match in enumerate(matches, start=1)])
        #embed.add_field(name="Did you mean:", value=match_list, inline=True)

    await ctx.reply(embed=embed, mention_author=True)

  async def send_bot_help(self, mapping):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    branding = await get_branding(ctx.guild.id)
    b_name  = branding["branding_name"]
    b_color = branding["embed_color"]

    # Show loading embed
    loading_embed = discord.Embed(
      description=f"{_e('loadingred')} Loading help Menu... Please wait.",
      color=b_color
    )
    loading_msg = await ctx.reply(embed=loading_embed)

    data = await getConfig(self.context.guild.id)
    prefix = data["prefix"]
    filtered = await self.filter_commands(self.context.bot.walk_commands(), sort=True)


    embed = discord.Embed(
        description=(
            f"```Hey! I'm {b_name}, your own best companion. "
            "The only bot you need to set up your entire server!```\n"
            "• Prefix: ``>``, ``sun``\n"
            "• Total Commands: ``586``\n"
            "\n"
            "**✦ EXPLORE BOT FEATURES ✦**"
        ),
        color=b_color
    )


    
    
    apply_branding_thumbnail(embed, branding, ctx.author)
    if branding.get("embed_banner"):
        embed.set_image(url=branding["embed_banner"])

    # Field 1: Security
    embed.add_field(
        name=f"{_e('zSafe')} __Security__",
        value=(
            ">>> ★ Automod • Antinuke • Verification • Encrypting"
        ),
        inline=False
    )

    # Field 2: Moderation
    embed.add_field(
        name=f"{_e('zbot')} __Mkderation__",
        value=(
            ">>> ★ Moderation • Ticket | Welcomer • Giveaway • Logging • Voice • Ignoring"
        ),
        inline=False
    )

    # Field 3: Utility
    embed.add_field(
        name=f"{_e('zwrench')} __Utility__",
        value=(
            ">>> ★ Utility • General • Server • Vanity • Reaction Roles • Giveaway • Boost Massage"
        ),
        inline=False
    )

    # Field 4: Music & Fun
    embed.add_field(
        name=f"{_e('starr')} __Music & Fun__",
        value=(
            ">>> ★ Music • Playlist • Fun • Birthday • Minecraft"
        ),
        inline=False
    )

    # Field 5: Extra
    embed.add_field(
        name=f"{_e('zmodule')} __Extra__",
        value=(
            ">>> ★ J2C • Leveling • boost massage • Poll • Counting • Sticky • Joindm • Invite Tracker"
        ),
        inline=False
    )
    
    # Field 6: Exclusive
    embed.add_field(
        name=f"{_e('premium')} __Free Exclusive__",
        value=(
            ">>> `»` • Bot Customization"
        ),
        inline=False
    )

        
    # Footer
    embed.set_footer(text=" ")
    
    view = vhelp.View(mapping=mapping, ctx=self.context, homeembed=embed, ui=2, branding=branding)
    await loading_msg.edit(embed=embed, view=view)

  async def send_command_help(self, command):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    zyrox = f">>> {command.help}" if command.help else '>>> No Help Provided...'
    embed = discord.Embed(
        description=f"""{zyrox}""",
        color=color)
    alias = ' & '.join(command.aliases)

    embed.add_field(name="**Alt cmd**",
                      value=f"```{alias}```" if command.aliases else "No Alt cmd",
                      inline=False)
    embed.add_field(name="**Usage**",
                      value=f"```{self.context.prefix}{command.signature}```\n")
    embed.set_author(name=f"{command.qualified_name.title()} Command")
    embed.set_footer(text="<[] = optional | < > = required • Use Prefix Before Commands.")
    await self.context.reply(embed=embed, mention_author=False)

  def get_command_signature(self, command: commands.Command) -> str:
    parent = command.full_parent_name
    if len(command.aliases) > 0:
      aliases = ' | '.join(command.aliases)
      fmt = f'[{command.name} | {aliases}]'
      if parent:
        fmt = f'{parent}'
      alias = f'[{command.name} | {aliases}]'
    else:
      alias = command.name if not parent else f'{parent} {command.name}'
    return f'{alias} {command.signature}'

  def common_command_formatting(self, embed_like, command):
    embed_like.title = self.get_command_signature(command)
    if command.description:
      embed_like.description = f'{command.description}\n\n{command.help}'
    else:
      embed_like.description = command.help or 'No help found...'

  async def send_group_help(self, group):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    entries = [
        (
            f"`{self.context.prefix}{cmd.qualified_name}`\n",
            f"{cmd.short_doc if cmd.short_doc else ''}\n\u200b"
        )
        for cmd in group.commands
      ]

    count = len(group.commands)

    embeds = FieldPagePaginator(
      entries=entries,
      title=f"{group.qualified_name.title()} [{count}]",
      description="< > Duty | [ ] Optional\n",
      per_page=4
    ).get_pages()   
    
    paginator = Paginator(ctx, embeds)
    await paginator.paginate()

  async def send_cog_help(self, cog):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    branding = await get_branding(ctx.guild.id)
    entries = [(
      f"`{self.context.prefix}{cmd.qualified_name}`",
      f"-# Description : {cmd.short_doc if cmd.short_doc else ''}"
      f"\n\u200b",
    ) for cmd in cog.get_commands()]
    paginator = Paginator(source=FieldPagePaginator(
      entries=entries,
      title=f"{branding['branding_name']} — {cog.qualified_name.title()} ({len(cog.get_commands())})",
      description="`<..> Required | [..] Optional`\n\n",
      color=branding["embed_color"],
      per_page=4),
                          ctx=self.context)
    await paginator.paginate()


class _SlashCtx:
    """Minimal context-like wrapper so the help View works from a slash command."""
    def __init__(self, interaction: Interaction):
        self.author = interaction.user
        self.bot = interaction.client
        self.guild = interaction.guild


class Help(Cog, name="help"):

  def __init__(self, client: zyrox):
    self._original_help_command = client.help_command
    attributes = {
      'name': "help",
      'aliases': ['h'],
      'cooldown': commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user),
      'help': 'Shows help about bot, a command, or a category'
    }
    client.help_command = HelpCommand(command_attrs=attributes)
    client.help_command.cog = self

  async def cog_unload(self):
    self.help_command = self._original_help_command

  @app_commands.command(name="help", description="Shows the help menu")
  @app_commands.guild_only()
  async def slash_help(self, interaction: Interaction):
    await interaction.response.defer(ephemeral=False)

    try:
      await asyncio.wait_for(self._build_and_send_help(interaction), timeout=10)
    except asyncio.TimeoutError:
      with suppress(discord.HTTPException):
        from utils.emojis import e as _e
        await interaction.followup.send(
          f"{_e('zcross')} The help menu took too long to load. Please try again.",
          ephemeral=True,
        )
    except Exception as e:
      print(f"slash_help failed: {e}")
      with suppress(discord.HTTPException):
        from utils.emojis import e as _e
        await interaction.followup.send(
          f"{_e('zcross')} Something went wrong while loading the help menu. Please try again.",
          ephemeral=True,
        )

  async def _build_and_send_help(self, interaction: Interaction):
    ctx = _SlashCtx(interaction)
    bot = interaction.client
    mapping = {cog: cog.get_commands() for cog in bot.cogs.values()}

    data = await getConfig(interaction.guild.id)
    prefix = data["prefix"]
    branding = await get_branding(interaction.guild.id)
    b_name  = branding["branding_name"]
    b_color = branding["embed_color"]

    
    embed = discord.Embed(
        description=(
            f"```Hey! I'm {b_name}, your own best companion. "
            "The only bot you need to set up your entire server!```\n"
            "• Prefix: ``>``, ``sun``\n"
            "• Total Commands: ``586``\n"
            "\n"
            "**✦ EXPLORE BOT FEATURES ✦**"
        ),
        color=b_color
    )

    
    apply_branding_thumbnail(embed, branding, interaction.user)
    if branding.get("embed_banner"):
        embed.set_image(url=branding["embed_banner"])

    # Field 1: Security
    embed.add_field(
        name=f"{_e('zSafe')} __Security__",
        value=(
            ">>> ★ Automod • Antinuke • Verification • Encrypting"
        ),
        inline=False
    )

    # Field 2: Moderation
    embed.add_field(
        name=f"{_e('zbot')} __Mkderation__",
        value=(
            ">>> ★ Moderation • Ticket | Welcomer • Giveaway • Logging • Voice • Ignoring"
        ),
        inline=False
    )

    # Field 3: Utility
    embed.add_field(
        name=f"{_e('zwrench')} __Utility__",
        value=(
            ">>> ★ Utility • General • Server • Vanity • Reaction Roles • Giveaway • Boost Massage"
        ),
        inline=False
    )

    # Field 4: Music & Fun
    embed.add_field(
        name=f"{_e('starr')} __Music & Fun__",
        value=(
            ">>> ★ Music • Playlist • Fun • Birthday • Minecraft"
        ),
        inline=False
    )

    # Field 5: Extra
    embed.add_field(
        name=f"{_e('zmodule')} __Extra__",
        value=(
            ">>> ★ J2C • Leveling • boost massage • Poll • Counting • Sticky • Joindm • Invite Tracker"
        ),
        inline=False
    )
    
    # Field 6: Exclusive
    embed.add_field(
        name=f"{_e('premium')} __Free Exclusive__",
        value=(
            ">>> `»` • Bot Customization"
        ),
        inline=False
    )
    
    # Footer
    embed.set_footer(text=" ")

    view = vhelp.View(mapping=mapping, ctx=ctx, homeembed=embed, ui=2, branding=branding)
    await interaction.followup.send(embed=embed, view=view)
