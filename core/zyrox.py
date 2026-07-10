from __future__ import annotations
from discord.ext import commands, tasks
import discord
import aiohttp
import json
import jishaku
import asyncio
import typing
from typing import List
import aiosqlite
from utils.config import OWNER_IDS
from utils import getConfig, updateConfig
from .Context import Context
from colorama import Fore, Style, init
import importlib
import inspect

init(autoreset=True)

# Corrected the extensions list
extensions: List[str] = [
    "cogs"
]

class zyrox(commands.AutoShardedBot):
    def __init__(self, *arg, **kwargs):
        intents = discord.Intents.all()
        intents.presences = True
        intents.members = True
        super().__init__(command_prefix=self.get_prefix,
                         case_insensitive=True,
                         intents=intents,
                         status=discord.Status.do_not_disturb,
                         strip_after_prefix=True,
                         owner_ids=OWNER_IDS,
                         allowed_mentions=discord.AllowedMentions(
                             everyone=False, replied_user=False, roles=False),
                         sync_commands_debug=True,
                         sync_commands=True,
                         shard_count=1)
        self.status_index = 0
        self.status_list = []
        # When True the rotating status task will not override the custom activity
        self.use_custom_activity = False

    # Default bot customization (used to seed fresh installs; admins can still
    # override any of these later via /global_customization, and their choice
    # will be preserved across restarts).
    DEFAULT_EMBED_THUMBNAIL = "https://cdn.discordapp.com/attachments/1475147783437811901/1522602829947343119/file_0000000023a87207a3bdcfadd18c59bc.png"
    DEFAULT_EMBED_BANNER = "https://cdn.discordapp.com/attachments/1475147783437811901/1522486762318860298/yellow-header-gif-yellow-header.gif"
    DEFAULT_ACTIVITY_TYPE = "watching"
    DEFAULT_ACTIVITY_NAME = "/help | .gg/thesunlight"

    async def _seed_default_customization(self):
        """Seed hardcoded defaults on first run without clobbering admin changes."""
        from utils.branding import (
            get_global_branding,
            set_global_branding,
            get_custom_activity,
            set_custom_activity,
        )

        global_branding = await get_global_branding()
        updates = {}
        if not global_branding.get("embed_thumbnail"):
            updates["embed_thumbnail"] = self.DEFAULT_EMBED_THUMBNAIL
        if not global_branding.get("embed_banner"):
            updates["embed_banner"] = self.DEFAULT_EMBED_BANNER
        if updates:
            await set_global_branding(**updates)

        if not await get_custom_activity():
            await set_custom_activity(self.DEFAULT_ACTIVITY_TYPE, self.DEFAULT_ACTIVITY_NAME)

    async def setup_hook(self):
        await self.load_extensions()
        await self._seed_default_customization()

        # Load any persisted custom activity before the rotating task starts
        from utils.branding import get_custom_activity
        saved = await get_custom_activity()
        if saved:
            self.use_custom_activity = True
            await self.change_presence(
                activity=discord.Activity(type=saved["type"], name=saved["name"])
            )
        self.status_task.start()
        self.tree.on_error = self.on_app_command_error

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Global fallback for slash command errors.

        Without this, an unhandled exception raised after `interaction.response.defer()`
        leaves the interaction stuck on "thinking..." forever, since discord.py's default
        behaviour is just to log the error without ever responding to the user.
        """
        print(f"{Fore.RED}{Style.BRIGHT}App command error in /{interaction.command.qualified_name if interaction.command else '?'}: {error}")
        message = "❌ Something went wrong while running this command. Please try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass

    async def load_extensions(self):
        for extension in extensions:
            try:
                await self.load_extension(extension)
                print(Fore.GREEN + Style.BRIGHT + f"Loaded extension: {extension}")
            except Exception as e:
                print(f"{Fore.RED}{Style.BRIGHT}Failed to load extension {extension}. {e}")
        print(Fore.GREEN + Style.BRIGHT + "*" * 20)

    @tasks.loop(seconds=30)
    async def status_task(self):
        await self.wait_until_ready()
        if not self.guilds:
            return
        # Don't override a custom activity set via /global_customization
        if self.use_custom_activity:
            return

        user_count = sum(g.member_count or 0 for g in self.guilds)
        guild_count = len(self.guilds)

        self.status_list = [
            (discord.ActivityType.playing, ">help | Protecting your Server"),
            (discord.ActivityType.watching, f"{user_count} users"),
            (discord.ActivityType.watching, f"{guild_count} servers"),
            (discord.ActivityType.listening, "Killing Nukers"),
        ]

        current = self.status_list[self.status_index % len(self.status_list)]
        await self.change_presence(activity=discord.Activity(type=current[0], name=current[1]))
        self.status_index += 1

    async def send_raw(self, channel_id: int, content: str, **kwargs) -> typing.Optional[discord.Message]:
        await self.http.send_message(channel_id, content, **kwargs)

    async def invoke_help_command(self, ctx: Context) -> None:
        return await ctx.send_help(ctx.command)

    async def fetch_message_by_channel(self, channel: discord.TextChannel, messageID: int) -> typing.Optional[discord.Message]:
        async for msg in channel.history(limit=1, before=discord.Object(messageID + 1), after=discord.Object(messageID - 1)):
            return msg

    async def get_prefix(self, message: discord.Message):
        # Prefix is locked to ">" — cannot be changed per-guild
        prefix = ">"
        async with aiosqlite.connect('db/np.db') as db:
            async with db.execute("SELECT id FROM np WHERE id = ?", (message.author.id,)) as cursor:
                row = await cursor.fetchone()
        if row:
            # Noprefix users can omit the prefix entirely
            return commands.when_mentioned_or(prefix, '')(self, message)
        return commands.when_mentioned_or(prefix)(self, message)

    async def on_message_edit(self, before, after):
        ctx: Context = await self.get_context(after, cls=Context)
        if before.content != after.content:
            if after.guild is None or after.author.bot:
                return
            if ctx.command is None:
                return
            if type(ctx.channel) == "public_thread":
                return
            await self.invoke(ctx)

def setup_bot():
    intents = discord.Intents.all()
    bot = zyrox(intents=intents)
    return bot
