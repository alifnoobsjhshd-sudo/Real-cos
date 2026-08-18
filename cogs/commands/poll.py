import asyncio
import time
from typing import Optional

import aiosqlite
import discord
from discord.ext import commands
from discord import app_commands

from core import Cog, zyrox, Context
from utils.Tools import blacklist_check, ignore_check

POLL_DB = "db/poll.db"
MAX_OPTIONS = 10
from utils.emojis import e as _pe
OPTION_EMOJIS = [
    _pe("znum1") or "1️⃣", _pe("znum2") or "2️⃣", _pe("znum3") or "3️⃣",
    _pe("znum4") or "4️⃣", _pe("znum5") or "5️⃣", _pe("znum6") or "6️⃣",
    _pe("znum7") or "7️⃣", _pe("znum8") or "8️⃣", _pe("znum9") or "9️⃣",
    _pe("znum10") or "🔟",
]


async def _setup_poll_db():
    async with aiosqlite.connect(POLL_DB) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS polls (
                poll_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER,
                channel_id  INTEGER,
                message_id  INTEGER,
                creator_id  INTEGER,
                question    TEXT,
                description TEXT,
                multiple    INTEGER DEFAULT 0,
                ended       INTEGER DEFAULT 0,
                created_at  REAL
            )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS poll_options (
                poll_id       INTEGER,
                option_index  INTEGER,
                label         TEXT,
                PRIMARY KEY (poll_id, option_index)
            )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS poll_votes (
                poll_id       INTEGER,
                option_index  INTEGER,
                user_id       INTEGER,
                PRIMARY KEY (poll_id, option_index, user_id)
            )"""
        )
        await db.commit()


def _bar(count: int, total: int, width: int = 14) -> str:
    if total <= 0:
        filled = 0
    else:
        filled = round((count / total) * width)
    return "█" * filled + "░" * (width - filled)


class PollData:
    __slots__ = (
        "poll_id", "guild_id", "channel_id", "message_id", "creator_id",
        "question", "description", "options", "multiple", "ended",
    )

    def __init__(self, poll_id, guild_id, channel_id, creator_id, question,
                 description, options, multiple):
        self.poll_id = poll_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id: Optional[int] = None
        self.creator_id = creator_id
        self.question = question
        self.description = description
        self.options = options
        self.multiple = multiple
        self.ended = False


async def _build_results_embed(poll_id: int, poll_row, options, ended: bool) -> discord.Embed:
    _, guild_id, channel_id, message_id, creator_id, question, description, multiple, _ended, created_at = poll_row

    async with aiosqlite.connect(POLL_DB) as db:
        vote_counts = {}
        voters = set()
        async with db.execute(
            "SELECT option_index, user_id FROM poll_votes WHERE poll_id = ?", (poll_id,)
        ) as cursor:
            async for option_index, user_id in cursor:
                vote_counts[option_index] = vote_counts.get(option_index, 0) + 1
                voters.add(user_id)

    total_voters = len(voters)
    total_votes = sum(vote_counts.values())

    from utils.emojis import e as _pe
    embed = discord.Embed(
        title=f"{_pe('zpoll') or '📊'} {question}",
        description=description or None,
        color=discord.Color.gold() if not ended else discord.Color.dark_grey(),
    )

    lines = []
    for idx, label in options:
        count = vote_counts.get(idx, 0)
        pct = round((count / total_votes) * 100) if total_votes else 0
        from utils.emojis import e as _pe
        emoji = OPTION_EMOJIS[idx] if idx < len(OPTION_EMOJIS) else (_pe("zcircle") or "▪️")
        lines.append(f"{emoji} **{label}**\n`{_bar(count, total_votes)}` {count} vote{'s' if count != 1 else ''} ({pct}%)")

    embed.add_field(name="\u200b", value="\n\n".join(lines) if lines else "No options.", inline=False)

    mode = "Multiple choice" if multiple else "Single choice"
    from utils.emojis import e as _pe
    status = f"{_pe('lock') or '🔒'} Poll ended" if ended else f"{_pe('zvote') or '🗳️'} Voting open"
    embed.set_footer(text=f"{status} • {mode} • {total_voters} voter{'s' if total_voters != 1 else ''}")

    try:
        from utils.branding import get_branding
        branding = await get_branding(guild_id)
        if branding.get("embed_thumbnail"):
            embed.set_thumbnail(url=branding["embed_thumbnail"])
    except Exception:
        pass

    return embed


class PollVoteSelect(discord.ui.Select):
    def __init__(self, poll_id: int, options: list, multiple: bool):
        select_options = [
            discord.SelectOption(
                label=label[:100],
                value=str(idx),
                emoji=OPTION_EMOJIS[idx] if idx < len(OPTION_EMOJIS) else None,
            )
            for idx, label in options
        ]
        super().__init__(
            placeholder="Vote for an option..." if not multiple else "Vote for one or more options...",
            min_values=1,
            max_values=len(select_options) if multiple else 1,
            options=select_options,
            custom_id=f"poll_vote:{poll_id}",
        )
        self.poll_id = poll_id
        self.multiple = multiple

    async def callback(self, interaction: discord.Interaction):
        selected = {int(v) for v in self.values}

        async with aiosqlite.connect(POLL_DB) as db:
            async with db.execute(
                "SELECT ended FROM polls WHERE poll_id = ?", (self.poll_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("This poll no longer exists.", ephemeral=True)
                return
            if row[0]:
                await interaction.response.send_message("This poll has ended.", ephemeral=True)
                return

            # Replace this user's previous vote(s) with the new selection.
            await db.execute(
                "DELETE FROM poll_votes WHERE poll_id = ? AND user_id = ?",
                (self.poll_id, interaction.user.id),
            )
            for idx in selected:
                await db.execute(
                    "INSERT OR IGNORE INTO poll_votes (poll_id, option_index, user_id) VALUES (?, ?, ?)",
                    (self.poll_id, idx, interaction.user.id),
                )
            await db.commit()

            async with db.execute("SELECT * FROM polls WHERE poll_id = ?", (self.poll_id,)) as cursor:
                poll_row = await cursor.fetchone()
            async with db.execute(
                "SELECT option_index, label FROM poll_options WHERE poll_id = ? ORDER BY option_index",
                (self.poll_id,),
            ) as cursor:
                options = await cursor.fetchall()

        embed = await _build_results_embed(self.poll_id, poll_row, options, ended=False)
        await interaction.response.edit_message(embed=embed)


class PollEndButton(discord.ui.Button):
    def __init__(self, poll_id: int):
        from utils.emojis import e as _e
        super().__init__(
            label="End Poll",
            style=discord.ButtonStyle.danger,
            emoji=_e("lock") or "🔒",
            custom_id=f"poll_end:{poll_id}",
        )
        self.poll_id = poll_id

    async def callback(self, interaction: discord.Interaction):
        async with aiosqlite.connect(POLL_DB) as db:
            async with db.execute(
                "SELECT creator_id, ended FROM polls WHERE poll_id = ?", (self.poll_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("This poll no longer exists.", ephemeral=True)
                return

            creator_id, ended = row
            is_admin = interaction.user.guild_permissions.manage_messages if interaction.guild else False
            if interaction.user.id != creator_id and not is_admin:
                await interaction.response.send_message(
                    "Only the poll creator or a moderator can end this poll.", ephemeral=True
                )
                return
            if ended:
                await interaction.response.send_message("This poll has already ended.", ephemeral=True)
                return

            await db.execute("UPDATE polls SET ended = 1 WHERE poll_id = ?", (self.poll_id,))
            await db.commit()

            async with db.execute("SELECT * FROM polls WHERE poll_id = ?", (self.poll_id,)) as cursor:
                poll_row = await cursor.fetchone()
            async with db.execute(
                "SELECT option_index, label FROM poll_options WHERE poll_id = ? ORDER BY option_index",
                (self.poll_id,),
            ) as cursor:
                options = await cursor.fetchall()

        embed = await _build_results_embed(self.poll_id, poll_row, options, ended=True)
        view = PollVoteView(self.poll_id, options, bool(poll_row[7]), ended=True)
        await interaction.response.edit_message(embed=embed, view=view)


class PollVoteView(discord.ui.View):
    """Persistent view attached to a live poll message."""

    def __init__(self, poll_id: int, options: list, multiple: bool, ended: bool = False):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        if not ended:
            self.add_item(PollVoteSelect(poll_id, options, multiple))
            self.add_item(PollEndButton(poll_id))
        else:
            select = PollVoteSelect(poll_id, options, multiple)
            select.disabled = True
            self.add_item(select)


class PollQuestionModal(discord.ui.Modal, title="Poll Question"):
    question = discord.ui.TextInput(
        label="Question",
        placeholder="What should we build next?",
        max_length=200,
        required=True,
    )
    description = discord.ui.TextInput(
        label="Description (optional)",
        placeholder="Extra context shown under the question.",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    def __init__(self, builder_view: "PollBuilderView"):
        super().__init__()
        self.builder_view = builder_view
        if builder_view.question:
            self.question.default = builder_view.question
        if builder_view.description:
            self.description.default = builder_view.description

    async def on_submit(self, interaction: discord.Interaction):
        self.builder_view.question = str(self.question.value).strip()
        self.builder_view.description = str(self.description.value).strip() or None
        await interaction.response.edit_message(embed=self.builder_view.build_embed(), view=self.builder_view)


class PollOptionModal(discord.ui.Modal, title="Add Poll Option"):
    option_text = discord.ui.TextInput(
        label="Option text",
        placeholder="Type an answer choice for this poll...",
        max_length=100,
        required=True,
    )

    def __init__(self, builder_view: "PollBuilderView"):
        super().__init__()
        self.builder_view = builder_view

    async def on_submit(self, interaction: discord.Interaction):
        text = str(self.option_text.value).strip()
        if len(self.builder_view.options) >= MAX_OPTIONS:
            await interaction.response.send_message(
                f"You can only have up to {MAX_OPTIONS} options.", ephemeral=True
            )
            return
        self.builder_view.options.append(text)
        await interaction.response.edit_message(embed=self.builder_view.build_embed(), view=self.builder_view)


class PollChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, builder_view: "PollBuilderView"):
        super().__init__(
            placeholder="Select the channel to send the poll to...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            custom_id="poll_channel_select",
            row=0,
        )
        self.builder_view = builder_view

    async def callback(self, interaction: discord.Interaction):
        # self.values[0] is an AppCommandChannel (no .send()).  Store it for
        # .mention display but resolve to a real channel before sending.
        self.builder_view.channel = self.values[0]
        self.builder_view.channel_id = self.values[0].id
        await interaction.response.edit_message(embed=self.builder_view.build_embed(), view=self.builder_view)


class PollBuilderView(discord.ui.View):
    def __init__(self, cog: "PollCog", ctx: Context):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.question: Optional[str] = None
        self.description: Optional[str] = None
        self.options: list[str] = []
        self.multiple = False
        self.channel: Optional[discord.abc.GuildChannel] = None  # AppCommandChannel (for .mention)
        self.channel_id: Optional[int] = None                    # raw ID for actual resolution

        self.add_item(PollChannelSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the person who started this poll setup can use these controls.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{_pe('zpoll') or '📊'} Poll Builder",
            description=(
                "Configure your poll using the buttons below, then hit **Send Poll**.\n"
                "You need a question, at least 2 options, and a channel."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Question", value=self.question or "*Not set*", inline=False)
        if self.description:
            embed.add_field(name="Description", value=self.description, inline=False)

        if self.options:
            opts_text = "\n".join(
                f"{OPTION_EMOJIS[i] if i < len(OPTION_EMOJIS) else (_pe('zcircle') or '▪️')} {opt}"
                for i, opt in enumerate(self.options)
            )
        else:
            opts_text = "*No options added yet*"
        embed.add_field(name=f"Options ({len(self.options)}/{MAX_OPTIONS})", value=opts_text, inline=False)

        embed.add_field(
            name="Answer mode",
            value=f"{_pe('zcounting') or '🔢'} Multiple choice" if self.multiple else f"{_pe('zcircle2') or '🔘'} Single choice",
            inline=True,
        )
        embed.add_field(
            name="Target channel",
            value=self.channel.mention if self.channel else "*Not selected*",
            inline=True,
        )
        return embed

    @discord.ui.button(label="Set Question", emoji=_pe("zmsg") or "💬", style=discord.ButtonStyle.primary, row=1)
    async def set_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PollQuestionModal(self))

    @discord.ui.button(label="Add Option", emoji=_pe("zplus") or "➕", style=discord.ButtonStyle.secondary, row=1)
    async def add_option(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.options) >= MAX_OPTIONS:
            await interaction.response.send_message(
                f"You can only have up to {MAX_OPTIONS} options.", ephemeral=True
            )
            return
        await interaction.response.send_modal(PollOptionModal(self))

    @discord.ui.button(label="Remove Last Option", emoji=_pe("delete") or "🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def remove_option(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.options:
            await interaction.response.send_message("There are no options to remove.", ephemeral=True)
            return
        self.options.pop()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Single Choice", emoji=_pe("znum1") or "1️⃣", style=discord.ButtonStyle.secondary, row=2)
    async def toggle_multiple(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.multiple = not self.multiple
        button.label = "Multiple Choice" if self.multiple else "Single Choice"
        button.emoji = discord.PartialEmoji.from_str(_pe("zcounting") or "🔢") if self.multiple else discord.PartialEmoji.from_str(_pe("znum1") or "1️⃣")
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Send Poll", emoji=_pe("ztick") or "✅", style=discord.ButtonStyle.success, row=2)
    async def send_poll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.question:
            await interaction.response.send_message("Please set a question first.", ephemeral=True)
            return
        if len(self.options) < 2:
            await interaction.response.send_message("Please add at least 2 options.", ephemeral=True)
            return
        if not self.channel:
            await interaction.response.send_message("Please select a channel to send the poll to.", ephemeral=True)
            return

        # Resolve AppCommandChannel → real TextChannel so .send() works
        real_channel = None
        if self.channel_id:
            real_channel = interaction.guild.get_channel(self.channel_id)
        if real_channel is None and self.channel is not None:
            # Try resolve() as fallback (returns None if not in cache)
            try:
                real_channel = self.channel.resolve()
            except Exception:
                pass
        if real_channel is None:
            await interaction.response.send_message(
                "Could not find the selected channel. Please select it again.", ephemeral=True
            )
            return

        perms = real_channel.permissions_for(interaction.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await interaction.response.send_message(
                f"I don't have permission to send embeds in {self.channel.mention}.", ephemeral=True
            )
            return

        async with aiosqlite.connect(POLL_DB) as db:
            cursor = await db.execute(
                "INSERT INTO polls (guild_id, channel_id, creator_id, question, description, multiple, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    self.ctx.guild.id,
                    real_channel.id,
                    self.ctx.author.id,
                    self.question,
                    self.description,
                    int(self.multiple),
                    time.time(),
                ),
            )
            poll_id = cursor.lastrowid
            for idx, label in enumerate(self.options):
                await db.execute(
                    "INSERT INTO poll_options (poll_id, option_index, label) VALUES (?, ?, ?)",
                    (poll_id, idx, label),
                )
            await db.commit()

            async with db.execute("SELECT * FROM polls WHERE poll_id = ?", (poll_id,)) as cursor2:
                poll_row = await cursor2.fetchone()
            options = list(enumerate(self.options))

        embed = await _build_results_embed(poll_id, poll_row, options, ended=False)
        view = PollVoteView(poll_id, options, self.multiple)
        poll_message = await real_channel.send(embed=embed, view=view)

        async with aiosqlite.connect(POLL_DB) as db:
            await db.execute(
                "UPDATE polls SET message_id = ? WHERE poll_id = ?", (poll_message.id, poll_id)
            )
            await db.commit()

        self.cog.client.add_view(view, message_id=poll_message.id)

        for child in self.children:
            child.disabled = True
        from utils.emojis import e as _e
        confirm_embed = discord.Embed(
            title=f"{_e('ztick')} Poll sent!",
            description=f"Your poll was posted in {self.channel.mention}.",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=confirm_embed, view=self)
        self.stop()

    @discord.ui.button(label="Cancel", emoji=_pe("zcross") or "❌", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        from utils.emojis import e as _e
        for child in self.children:
            child.disabled = True
        embed = discord.Embed(
            title=f"{_e('zcross')} Poll setup cancelled",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass


class PollCog(Cog):
    """Interactive poll builder with real-time voting."""

    def __init__(self, client: zyrox):
        self.client = client

    def help_custom(self):
        from utils.emojis import e as _e
        return _e("zpoll"), "Poll Commands", "Create and manage interactive polls"

    async def cog_load(self):
        await _setup_poll_db()
        await self._register_persistent_views()

    async def _register_persistent_views(self):
        async with aiosqlite.connect(POLL_DB) as db:
            async with db.execute(
                "SELECT poll_id, message_id, multiple, ended FROM polls WHERE message_id IS NOT NULL"
            ) as cursor:
                polls = await cursor.fetchall()

            for poll_id, message_id, multiple, ended in polls:
                async with db.execute(
                    "SELECT option_index, label FROM poll_options WHERE poll_id = ? ORDER BY option_index",
                    (poll_id,),
                ) as opt_cursor:
                    options = await opt_cursor.fetchall()
                if not options:
                    continue
                view = PollVoteView(poll_id, options, bool(multiple), ended=bool(ended))
                self.client.add_view(view, message_id=message_id)

    @commands.hybrid_command(
        name="poll",
        help="Create an interactive poll with custom options, single/multiple choice, and a target channel.",
        usage="poll",
    )
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def poll(self, ctx: Context):
        view = PollBuilderView(self, ctx)
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message


async def setup(client: zyrox):
    await client.add_cog(PollCog(client))
