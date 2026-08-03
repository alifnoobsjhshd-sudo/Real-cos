"""
cogs/commands/invite_leaderboard.py — Invite Leaderboard system for Zyrox X.

Reads invite data from the existing Tracking cog's database (db/invite.db).
Does NOT duplicate invite tracking — that is wholly owned by cogs/commands/tracking.py.

Extra tables added to db/invite.db (never conflict with Tracking schema):
  invite_leaderboard_config  — per-guild leaderboard display settings
  invite_lb_baseline         — snapshot totals used for period-based filtering

Commands:
  /invites leaderboard — Interactive setup panel (requires Manage Guild)
  /invites stats [user] — Show invite stats for a user
  /invites reset       — Start a fresh tracking period (admin only)
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional

from core import Cog, zyrox
from utils.Tools import blacklist_check, ignore_check
from utils.emojis import e as _e

# Same DB as the Tracking cog — single source of truth
INVITE_DB = "db/invite.db"


# ── Emoji helper ──────────────────────────────────────────────────────────────
def _pe(name: str, fallback: str = "") -> Optional[discord.PartialEmoji]:
    s = _e(name)
    try:
        if s:
            return discord.PartialEmoji.from_str(s)
    except Exception:
        pass
    if fallback:
        try:
            return discord.PartialEmoji.from_str(fallback)
        except Exception:
            pass
    return None


# ════════════════════════════════════════════════════════════════════════════════
# DATABASE HELPERS  (reads Tracking schema, writes only its own tables)
# ════════════════════════════════════════════════════════════════════════════════

class InviteLBDB:
    """
    Thin data-access layer that:
    - reads  from  invites_{guild_id}  (owned by the Tracking cog)
    - writes to    invite_leaderboard_config  and  invite_lb_baseline
    Both extra tables live in db/invite.db so there is a single DB file.
    """

    @staticmethod
    def _conn() -> aiosqlite.Connection:
        return aiosqlite.connect(INVITE_DB)

    async def init(self):
        async with self._conn() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_leaderboard_config (
                    guild_id        INTEGER PRIMARY KEY,
                    title           TEXT    DEFAULT 'Invite Leaderboard',
                    embed_color     INTEGER DEFAULT 16711680,
                    top_limit       INTEGER DEFAULT 10,
                    role_filter     INTEGER DEFAULT NULL,
                    period_active   INTEGER DEFAULT 0,
                    period_reset_at TEXT    DEFAULT NULL,
                    channel_id      INTEGER DEFAULT NULL
                )
            """)
            # Stores the total-invite count at the moment a period was last reset,
            # so leaderboard can show "since reset" rather than all-time totals.
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_lb_baseline (
                    guild_id       INTEGER NOT NULL,
                    user_id        INTEGER NOT NULL,
                    baseline_total INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            await db.commit()

    # ── Config ────────────────────────────────────────────────────────────────

    async def get_config(self, guild_id: int) -> Optional[dict]:
        async with self._conn() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM invite_leaderboard_config WHERE guild_id = ?", (guild_id,)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def save_config(self, guild_id: int, **kwargs):
        async with self._conn() as db:
            async with db.execute(
                "SELECT guild_id FROM invite_leaderboard_config WHERE guild_id = ?", (guild_id,)
            ) as cur:
                exists = await cur.fetchone()
            if exists:
                if kwargs:
                    clauses = ", ".join(f"{k} = ?" for k in kwargs)
                    await db.execute(
                        f"UPDATE invite_leaderboard_config SET {clauses} WHERE guild_id = ?",
                        list(kwargs.values()) + [guild_id],
                    )
            else:
                cols = ["guild_id"] + list(kwargs.keys())
                vals = [guild_id] + list(kwargs.values())
                ph = ", ".join("?" * len(cols))
                await db.execute(
                    f"INSERT INTO invite_leaderboard_config ({', '.join(cols)}) VALUES ({ph})",
                    vals,
                )
            await db.commit()

    # ── Period baseline ───────────────────────────────────────────────────────

    async def snapshot_baseline(self, guild_id: int):
        """
        Copy current totals from invites_{guild_id} into invite_lb_baseline.
        Called when an admin resets the period.  Any subsequent leaderboard
        query subtracts these values to show only invites gained since the reset.
        """
        async with self._conn() as db:
            table = f"invites_{guild_id}"
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ) as cur:
                if not await cur.fetchone():
                    return  # no data yet

            await db.execute(
                f"""
                INSERT INTO invite_lb_baseline (guild_id, user_id, baseline_total)
                SELECT ?, user_id, total FROM {table}
                ON CONFLICT(guild_id, user_id) DO UPDATE SET baseline_total = excluded.baseline_total
                """,
                (guild_id,),
            )
            await db.commit()

    async def clear_baseline(self, guild_id: int):
        async with self._conn() as db:
            await db.execute(
                "DELETE FROM invite_lb_baseline WHERE guild_id = ?", (guild_id,)
            )
            await db.commit()

    # ── Leaderboard query ─────────────────────────────────────────────────────

    async def get_leaderboard(
        self,
        guild_id: int,
        guild: discord.Guild,
        top_limit: int = 10,
        period_active: bool = False,
        role_filter: Optional[int] = None,
    ) -> list:
        """
        Returns sorted rows of {inviter_id, invites}.
        When period_active=True, invites = current_total - baseline_total
        (only positive differences are included).
        Always reads from the Tracking cog's invites_{guild_id} table.
        """
        table = f"invites_{guild_id}"
        async with self._conn() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ) as cur:
                if not await cur.fetchone():
                    return []

            if period_active:
                async with db.execute(
                    f"""
                    SELECT t.user_id AS inviter_id,
                           (t.total - COALESCE(b.baseline_total, 0)) AS invites
                    FROM {table} t
                    LEFT JOIN invite_lb_baseline b
                           ON b.guild_id = ? AND b.user_id = t.user_id
                    WHERE (t.total - COALESCE(b.baseline_total, 0)) > 0
                    ORDER BY invites DESC
                    """,
                    (guild_id,),
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]
            else:
                async with db.execute(
                    f"SELECT user_id AS inviter_id, total AS invites "
                    f"FROM {table} WHERE total > 0 ORDER BY total DESC"
                ) as cur:
                    rows = [dict(r) for r in await cur.fetchall()]

        # Apply role filter
        if role_filter and guild:
            role = guild.get_role(role_filter)
            if role:
                member_ids = {m.id for m in role.members}
                rows = [r for r in rows if r["inviter_id"] in member_ids]

        # Apply top limit (0 = no limit)
        if top_limit > 0:
            rows = rows[:top_limit]

        return rows

    async def get_user_stats(self, guild_id: int, user_id: int) -> dict:
        """Return total/fake/left/rejoin from the Tracking cog's table."""
        table = f"invites_{guild_id}"
        async with self._conn() as db:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ) as cur:
                if not await cur.fetchone():
                    return {"total": 0, "fake": 0, "left": 0, "rejoin": 0}
            async with db.execute(
                f"SELECT total, fake, left, rejoin FROM {table} WHERE user_id = ?",
                (user_id,),
            ) as cur:
                row = await cur.fetchone()
                if row:
                    return {"total": row[0], "fake": row[1], "left": row[2], "rejoin": row[3]}
                return {"total": 0, "fake": 0, "left": 0, "rejoin": 0}


_idb = InviteLBDB()


# ════════════════════════════════════════════════════════════════════════════════
# MODALS
# ════════════════════════════════════════════════════════════════════════════════

class SetTitleModal(discord.ui.Modal, title="Set Leaderboard Title"):
    title_input = discord.ui.TextInput(
        label="Title",
        placeholder="e.g. Top Inviters of the Month",
        min_length=1,
        max_length=100,
        required=True,
    )

    def __init__(self, config: dict, parent_view):
        super().__init__()
        self.config = config
        self.parent_view = parent_view
        self.title_input.default = config.get("title", "Invite Leaderboard")

    async def on_submit(self, interaction: discord.Interaction):
        self.config["title"] = self.title_input.value.strip()
        await _idb.save_config(interaction.guild.id, title=self.config["title"])
        await interaction.response.edit_message(
            embed=self.parent_view.build_embed(), view=self.parent_view
        )


class SetColorModal(discord.ui.Modal, title="Set Embed Color"):
    color_input = discord.ui.TextInput(
        label="Hex color (e.g. FF0000 for red)",
        placeholder="#FF0000 or FF0000",
        min_length=6,
        max_length=7,
        required=True,
    )

    def __init__(self, config: dict, parent_view):
        super().__init__()
        self.config = config
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.color_input.value.strip().lstrip("#")
        try:
            color = int(raw, 16)
        except ValueError:
            await interaction.response.send_message(
                "Invalid hex color. Example: `FF0000`", ephemeral=True
            )
            return
        self.config["embed_color"] = color
        await _idb.save_config(interaction.guild.id, embed_color=color)
        await interaction.response.edit_message(
            embed=self.parent_view.build_embed(), view=self.parent_view
        )


# ════════════════════════════════════════════════════════════════════════════════
# SETUP VIEW
# ════════════════════════════════════════════════════════════════════════════════

LIMIT_OPTIONS = [
    discord.SelectOption(label="Top 5",   value="5"),
    discord.SelectOption(label="Top 10",  value="10"),
    discord.SelectOption(label="Top 15",  value="15"),
    discord.SelectOption(label="Top 25",  value="25"),
    discord.SelectOption(label="No Limit (show all)", value="0"),
]


class InviteLeaderboardSetupView(discord.ui.View):
    """Interactive panel to configure and send an invite leaderboard."""

    def __init__(self, author: discord.Member, config: dict):
        super().__init__(timeout=300)
        self.author = author
        self.config = config
        self.message: Optional[discord.Message] = None

        # Mark current limit as default in select options
        cur_limit = str(config.get("top_limit", 10))
        for opt in LIMIT_OPTIONS:
            opt.default = (opt.value == cur_limit)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Only the command author can use this panel.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except Exception:
                pass

    # ── Embed builder ─────────────────────────────────────────────────────────

    def build_embed(self) -> discord.Embed:
        cfg = self.config
        color    = cfg.get("embed_color", 0xFF0000)
        title    = cfg.get("title", "Invite Leaderboard")
        limit    = cfg.get("top_limit", 10)
        role_id  = cfg.get("role_filter")
        period   = bool(cfg.get("period_active", 0))
        reset_at = cfg.get("period_reset_at")
        ch_id    = cfg.get("channel_id")

        role_text    = f"<@&{role_id}>" if role_id else "None (all members)"
        period_text  = (
            f"Since {discord.utils.format_dt(datetime.fromisoformat(reset_at), 'R')}"
            if period and reset_at
            else "All time"
        )
        limit_text   = f"Top **{limit}**" if limit else "No limit (all)"
        channel_text = f"<#{ch_id}>" if ch_id else "*(not set — select below)*"

        embed = discord.Embed(
            title=f"{_e('zpeople') or '👥'}  Invite Leaderboard Setup",
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name="⚙️ Current Settings",
            value=(
                f"**Title:** {title}\n"
                f"**Color:** `#{color:06X}`\n"
                f"**Limit:** {limit_text}\n"
                f"**Role filter:** {role_text}\n"
                f"**Period:** {period_text}\n"
                f"**Send channel:** {channel_text}"
            ),
            inline=False,
        )
        embed.set_footer(text="Use the buttons below to configure, then send.")
        return embed

    # ── Buttons ───────────────────────────────────────────────────────────────

    @discord.ui.button(label="📝 Set Title", style=discord.ButtonStyle.secondary, row=0)
    async def btn_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetTitleModal(self.config, self))

    @discord.ui.button(label="🎨 Set Color", style=discord.ButtonStyle.secondary, row=0)
    async def btn_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetColorModal(self.config, self))

    @discord.ui.button(label="🔄 Start New Period", style=discord.ButtonStyle.danger, row=0)
    async def btn_reset_period(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Snapshot current totals so the leaderboard counts from this point forward."""
        await _idb.snapshot_baseline(interaction.guild.id)
        now = datetime.utcnow().isoformat()
        self.config["period_active"] = 1
        self.config["period_reset_at"] = now
        await _idb.save_config(
            interaction.guild.id, period_active=1, period_reset_at=now
        )
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🕓 Use All-Time Totals", style=discord.ButtonStyle.secondary, row=0)
    async def btn_alltime(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Switch back to showing all-time invite counts."""
        self.config["period_active"] = 0
        await _idb.save_config(interaction.guild.id, period_active=0)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    # ── Limit select ──────────────────────────────────────────────────────────

    @discord.ui.select(placeholder="🏆 Set top limit…", options=LIMIT_OPTIONS, row=1)
    async def sel_limit(self, interaction: discord.Interaction, select: discord.ui.Select):
        val = int(select.values[0])
        self.config["top_limit"] = val
        await _idb.save_config(interaction.guild.id, top_limit=val)
        for opt in select.options:
            opt.default = (opt.value == str(val))
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    # ── Role filter ───────────────────────────────────────────────────────────

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="👥 Filter by role (optional)…",
        min_values=0,
        max_values=1,
        row=2,
    )
    async def sel_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        if select.values:
            self.config["role_filter"] = select.values[0].id
            await _idb.save_config(interaction.guild.id, role_filter=select.values[0].id)
        else:
            self.config["role_filter"] = None
            await _idb.save_config(interaction.guild.id, role_filter=None)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    # ── Channel select + Send ─────────────────────────────────────────────────

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="📢 Select channel to send leaderboard…",
        channel_types=[discord.ChannelType.text],
        min_values=1,
        max_values=1,
        row=3,
    )
    async def sel_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        ch = select.values[0]
        self.config["channel_id"] = ch.id
        await _idb.save_config(interaction.guild.id, channel_id=ch.id)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="📤 Send Leaderboard", style=discord.ButtonStyle.success, row=4)
    async def btn_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cfg = self.config
        ch_id = cfg.get("channel_id")
        if not ch_id:
            await interaction.followup.send(
                f"{_e('zwarning') or '⚠️'} Please select a channel first.", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(ch_id)
        if not channel:
            await interaction.followup.send("Channel not found.", ephemeral=True)
            return

        rows = await _idb.get_leaderboard(
            guild_id=interaction.guild.id,
            guild=interaction.guild,
            top_limit=cfg.get("top_limit", 10),
            period_active=bool(cfg.get("period_active", 0)),
            role_filter=cfg.get("role_filter"),
        )

        color    = cfg.get("embed_color", 0xFF0000)
        title    = cfg.get("title", "Invite Leaderboard")
        period   = bool(cfg.get("period_active", 0))
        reset_at = cfg.get("period_reset_at")

        embed = discord.Embed(title=f"🏆  {title}", color=color, timestamp=datetime.utcnow())

        if not rows:
            embed.description = "No invite data found for the selected filters."
        else:
            lines = []
            for i, row in enumerate(rows, 1):
                uid     = row["inviter_id"]
                invites = row["invites"]
                member  = interaction.guild.get_member(uid)
                mention = member.mention if member else f"<@{uid}>"
                lines.append(
                    f"**{i}.** {mention} — **{invites}** invite{'s' if invites != 1 else ''}"
                )
            embed.description = "\n".join(lines)

        period_label = "All time"
        if period and reset_at:
            try:
                dt = datetime.fromisoformat(reset_at)
                period_label = f"Since {discord.utils.format_dt(dt, 'R')}"
            except Exception:
                pass

        role_id = cfg.get("role_filter")
        role_obj = interaction.guild.get_role(role_id) if role_id else None
        footer = period_label
        if role_obj:
            footer += f"  ·  Role: {role_obj.name}"
        embed.set_footer(text=footer)

        try:
            await channel.send(embed=embed)
            await interaction.followup.send(
                f"{_e('ztick') or '✅'} Invite leaderboard sent to {channel.mention}!",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"{_e('zcross') or '❌'} I don't have permission to send in {channel.mention}.",
                ephemeral=True,
            )


# ════════════════════════════════════════════════════════════════════════════════
# COG
# ════════════════════════════════════════════════════════════════════════════════

class InviteLeaderboardCog(commands.Cog):
    """
    Invite leaderboard setup and stats commands.

    This cog does NOT track invites itself — that is handled by the Tracking cog
    (cogs/commands/tracking.py) which maintains db/invite.db.  This cog only
    reads those tables and adds two thin config/baseline tables to the same file.
    """

    def __init__(self, bot: zyrox):
        self.bot = bot
        asyncio.get_event_loop().create_task(self._init())

    def help_custom(self):
        emoji = _e("zpeople") or "👥"
        label = "Invite Leaderboard"
        description = "Invite tracking and leaderboard commands."
        return emoji, label, description

    async def _init(self):
        await self.bot.wait_until_ready()
        await _idb.init()

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.hybrid_group(name="invitelb", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def invite_group(self, ctx: commands.Context):
        """Invite leaderboard commands."""
        await ctx.send_help(ctx.command)

    @invite_group.command(name="leaderboard", description="Open the invite leaderboard setup panel.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def invite_leaderboard(self, ctx: commands.Context):
        """Open the interactive invite leaderboard setup panel."""
        config = await _idb.get_config(ctx.guild.id)
        if config is None:
            await _idb.save_config(
                ctx.guild.id,
                title="Invite Leaderboard",
                embed_color=0xFF0000,
                top_limit=10,
                period_active=0,
            )
            config = await _idb.get_config(ctx.guild.id)
        if config is None:
            config = {
                "title": "Invite Leaderboard",
                "embed_color": 0xFF0000,
                "top_limit": 10,
                "role_filter": None,
                "period_active": 0,
                "period_reset_at": None,
                "channel_id": None,
            }

        view = InviteLeaderboardSetupView(ctx.author, config)
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg

    @invite_group.command(name="stats", description="Show invite stats for a user.")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def invites_stats(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show invite count breakdown (total/fake/left/rejoin) for yourself or another member."""
        target = member or ctx.author
        stats  = await _idb.get_user_stats(ctx.guild.id, target.id)

        total  = stats["total"]
        fake   = stats["fake"]
        left   = stats["left"]
        rejoin = stats["rejoin"]
        real   = max(0, total - fake - left - rejoin)

        embed = discord.Embed(
            title=f"{_e('zpeople') or '👥'}  Invite Stats",
            description=(
                f"**{target.mention}** has **{total}** total invite{'s' if total != 1 else ''}.\n\n"
                f"✅ **Real:** `{real}`\n"
                f"👻 **Fake:** `{fake}`\n"
                f"🚪 **Left:** `{left}`\n"
                f"🔄 **Rejoins:** `{rejoin}`"
            ),
            color=0xFF0000,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"User ID: {target.id}")
        await ctx.send(embed=embed)

    @invite_group.command(name="reset", description="Start a fresh tracking period for the leaderboard.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def invites_reset(self, ctx: commands.Context):
        """
        Snapshot current invite totals so the next leaderboard only counts
        invites gained after this point.
        """
        await _idb.snapshot_baseline(ctx.guild.id)
        now = datetime.utcnow().isoformat()
        await _idb.save_config(ctx.guild.id, period_active=1, period_reset_at=now)
        embed = discord.Embed(
            description=(
                f"{_e('ztick') or '✅'} Invite period reset. "
                f"The leaderboard now counts only invites from this moment forward."
            ),
            color=0xFF0000,
        )
        await ctx.send(embed=embed)


async def setup(bot: zyrox):
    await bot.add_cog(InviteLeaderboardCog(bot))
