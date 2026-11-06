import os
import sqlite3

import discord
from discord.ext import commands

from utils.emojis import e as _e


DB_PATH = "db/nickchanger.db"


class NickChangerSetupView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.channel = None

        channel_select = discord.ui.ChannelSelect(
            placeholder="Select the nickname channel",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=0,
        )
        channel_select.callback = self.select_channel
        self.add_item(channel_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )
            return False
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You need Manage Server permission to configure Nickchanger.",
                ephemeral=True,
            )
            return False
        return True

    async def select_channel(self, interaction: discord.Interaction):
        self.channel = self.children[0].values[0]
        await interaction.response.edit_message(
            content=f"Selected {self.channel.mention}. Click Enable to activate Nickchanger.",
            view=self,
        )

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, row=1)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.channel is None:
            await interaction.response.send_message(
                "Select a text channel first.", ephemeral=True
            )
            return
        await self.cog.enable_channel(interaction.guild.id, self.channel.id)
        await interaction.response.edit_message(
            content=f"Nickchanger enabled in {self.channel.mention}.", view=None
        )


class NickChanger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("db", exist_ok=True)
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS nickchanger_settings ("
            "guild_id INTEGER PRIMARY KEY, "
            "channel_id INTEGER NOT NULL, "
            "enabled INTEGER NOT NULL DEFAULT 0"
            ")"
        )
        self.db.commit()
        self.enabled_channels = {
            guild_id: channel_id
            for guild_id, channel_id in self.db.execute(
                "SELECT guild_id, channel_id FROM nickchanger_settings WHERE enabled=1"
            )
        }

    def help_custom(self):
        return _e("zpeople") or "👤", "Nickchanger Commands", "Nickchanger settings and commands"

    async def enable_channel(self, guild_id: int, channel_id: int):
        with self.db:
            self.db.execute(
                "INSERT INTO nickchanger_settings (guild_id, channel_id, enabled) "
                "VALUES (?, ?, 1) ON CONFLICT(guild_id) DO UPDATE SET "
                "channel_id=excluded.channel_id, enabled=1",
                (guild_id, channel_id),
            )
        self.enabled_channels[guild_id] = channel_id

    @commands.group(
        name="nickchanger",
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def nickchanger(self, ctx: commands.Context):
        """`>nickchanger enable` or `>nickchanger enabl` — choose a channel and enable nickname changes.
        `>nickchanger disable` — disable nickname changes for this server."""
        await ctx.send_help(ctx.command)

    @nickchanger.command(name="enable", aliases=["enabl"])
    @commands.has_guild_permissions(manage_guild=True)
    async def enable(self, ctx: commands.Context):
        view = NickChangerSetupView(self, ctx)
        await ctx.send("Select a text channel, then click Enable:", view=view)

    @nickchanger.command(name="disable")
    @commands.has_guild_permissions(manage_guild=True)
    async def disable(self, ctx: commands.Context):
        with self.db:
            self.db.execute(
                "UPDATE nickchanger_settings SET enabled=0 WHERE guild_id=?",
                (ctx.guild.id,),
            )
        self.enabled_channels.pop(ctx.guild.id, None)
        await ctx.send(f"{_e('ztick') or '✅'} Nickchanger is disabled for this server.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if self.enabled_channels.get(message.guild.id) != message.channel.id:
            return

        nickname = message.content.strip()[:32]
        if not nickname:
            await self._react(message, _e("zcross") or "❌")
            return

        try:
            await message.author.edit(
                nick=nickname,
                reason="Nickchanger channel message",
            )
        except (discord.Forbidden, discord.HTTPException):
            await self._react(message, _e("zcross") or "❌")
        else:
            await self._react(message, _e("ztick") or "✅")

    @staticmethod
    async def _react(message: discord.Message, emoji: str):
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            pass

    def cog_unload(self):
        self.db.close()


async def setup(bot):
    await bot.add_cog(NickChanger(bot))