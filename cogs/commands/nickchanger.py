import logging
import os
import sqlite3

import discord
from discord.ext import commands

from utils.emojis import e as _e

logger = logging.getLogger(__name__)
DB_PATH = "db/nickchanger.db"


class NickchangerSetupView(discord.ui.View):
    def __init__(self, ctx: commands.Context, cog):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.cog = cog
        self.channel: discord.TextChannel | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the user who started this setup can use these controls.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Choose the channel where messages change nicknames",
        min_values=1,
        max_values=1,
        row=0,
    )
    async def select_channel(
        self,
        interaction: discord.Interaction,
        select: discord.ui.ChannelSelect,
    ):
        channel = select.values[0]
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.ctx.guild.id:
            await interaction.response.send_message(
                "Please select a text channel from this server.", ephemeral=True
            )
            return
        self.channel = channel
        await interaction.response.edit_message(
            content=f"Selected {channel.mention}. Click **Enable** to activate nickname changing there.",
            view=self,
        )

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.success, row=1)
    async def enable(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if self.channel is None:
            await interaction.response.send_message(
                "Choose a text channel before enabling nickname changing.",
                ephemeral=True,
            )
            return

        bot_member = interaction.guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_nicknames:
            await interaction.response.send_message(
                "I need the **Manage Nicknames** permission to change member nicknames.",
                ephemeral=True,
            )
            return

        try:
            self.cog.db.execute(
                "INSERT INTO nickchanger_settings (guild_id, channel_id) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id",
                (interaction.guild.id, self.channel.id),
            )
            self.cog.db.commit()
        except sqlite3.Error:
            logger.exception("Could not save nickname changer channel for guild %s", interaction.guild.id)
            await interaction.response.send_message(
                "Could not save the nickname changer settings. Please try again later.",
                ephemeral=True,
            )
            return

        self.stop()
        await interaction.response.edit_message(
            content=f"{_e('ztick') or '✅'} Nickname changing is enabled in {self.channel.mention}. "
            "Members' messages there will be used as their server nickname.",
            view=None,
        )

class NicknameChanger(commands.Cog, name="Nickname Changer"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        os.makedirs("db", exist_ok=True)
        self.db = sqlite3.connect(DB_PATH)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS nickchanger_settings ("
            "guild_id INTEGER PRIMARY KEY, "
            "channel_id INTEGER NOT NULL"
            ")"
        )
        self.db.commit()

    def help_custom(self):
        return _e("zsettings") or _e("zbot"), "Nickname Changer", "Set nicknames from messages in a chosen channel"

    @commands.group(name="nickchanger", invoke_without_command=True)
    @commands.guild_only()
    async def nickchanger(self, ctx: commands.Context):
        """Use `>nickchanger enabl`, `>nickchanger enable`, or `>nickchanger disable`."""
        await ctx.send_help(ctx.command)

    @nickchanger.command(name="enable", aliases=["enabl"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def enable(self, ctx: commands.Context):
        """Enable nickname changing with `>nickchanger enabl` or `>nickchanger enable`."""
        bot_member = ctx.guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_nicknames:
            await ctx.send(
                f"{_e('zcross') or '❌'} I need the **Manage Nicknames** permission."
            )
            return

        view = NickchangerSetupView(ctx, self)
        message = await ctx.send(
            "Choose a text channel, then click **Enable** to turn on nickname changing.",
            view=view,
        )
        view.message = message

    @nickchanger.command(name="disable")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def disable(self, ctx: commands.Context):
        """Disable nickname changing with `>nickchanger disable`."""
        try:
            self.db.execute(
                "DELETE FROM nickchanger_settings WHERE guild_id=?",
                (ctx.guild.id,),
            )
            self.db.commit()
        except sqlite3.Error:
            logger.exception("Could not disable nickname changer for guild %s", ctx.guild.id)
            await ctx.send(
                f"{_e('zcross') or '❌'} Could not disable nickname changing. Please try again."
            )
            return

        await ctx.send(f"{_e('ztick') or '✅'} Nickname changing is disabled in this server.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        try:
            row = self.db.execute(
                "SELECT channel_id FROM nickchanger_settings WHERE guild_id=?",
                (message.guild.id,),
            ).fetchone()
        except sqlite3.Error:
            logger.exception("Could not read nickname changer settings for guild %s", message.guild.id)
            return

        if row is None or message.channel.id != row[0]:
            return

        context = await self.bot.get_context(message)
        if context.valid or not message.content.strip():
            return

        nickname = message.content.strip()
        if len(nickname) > 32:
            await self._react(message, "zcross", "❌")
            return

        try:
            await message.author.edit(nick=nickname, reason="Nickname changer channel")
        except (discord.Forbidden, discord.HTTPException) as error:
            logger.info(
                "Failed to set nickname for member %s in guild %s: %s",
                message.author.id,
                message.guild.id,
                error,
            )
            await self._react(message, "zcross", "❌")
            return

        await self._react(message, "ztick", "✅")

    async def _react(self, message: discord.Message, emoji_name: str, fallback: str):
        try:
            await message.add_reaction(_e(emoji_name) or fallback)
        except discord.HTTPException:
            logger.exception(
                "Could not add nickname changer result reaction to message %s",
                message.id,
            )

    def cog_unload(self):
        self.db.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(NicknameChanger(bot))
