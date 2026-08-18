# cogs/commands/ticket.py  —  Ticket system (rewritten)

import discord
from utils.emojis import e as _e
from discord import app_commands
from discord.ext import commands
import sqlite3
from datetime import datetime
import asyncio
import io
import os
import re

# ── Constants ─────────────────────────────────────────────────────────────────
EMBED_COLOR = 0xFF0000

if not os.path.exists('db'):
    os.makedirs('db')
DB_PATH = 'db/ticket.db'
MAX_BUTTONS = 15


# ── Emoji helper ──────────────────────────────────────────────────────────────
def _parse_emoji(s):
    if not s:
        return None
    m = re.match(r'<(a?):(\w+):(\d+)>', str(s))
    if m:
        return discord.PartialEmoji(
            animated=bool(m.group(1)), name=m.group(2), id=int(m.group(3))
        )
    return str(s)


# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════

class TicketDatabase:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        with self.conn:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS guild_configs ("
                "guild_id INTEGER PRIMARY KEY, "
                "panel_channel_id INTEGER, "
                "logging_channel_id INTEGER, "
                "panel_message_id INTEGER, "
                "panel_type TEXT DEFAULT 'button', "
                "embed_title TEXT, "
                "embed_description TEXT, "
                "embed_color INTEGER, "
                "embed_image_url TEXT, "
                "embed_thumbnail_url TEXT, "
                "closed_category_id INTEGER, "
                "staff_role_id INTEGER, "
                "ticket_embed_title TEXT, "
                "ticket_embed_description TEXT, "
                "ticket_embed_banner_url TEXT, "
                "ticket_embed_thumbnail_url TEXT"
                ")"
            )
            for col, coltype in [
                ("ticket_embed_title", "TEXT"),
                ("ticket_embed_description", "TEXT"),
                ("ticket_embed_banner_url", "TEXT"),
                ("ticket_embed_thumbnail_url", "TEXT"),
                ("staff_role_id", "INTEGER"),
            ]:
                try:
                    self.conn.execute(f"ALTER TABLE guild_configs ADD COLUMN {col} {coltype}")
                except Exception:
                    pass

            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS ticket_categories ("
                "category_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER, "
                "name TEXT NOT NULL, "
                "emoji TEXT, "
                "notified_roles TEXT, "
                "button_style INTEGER, "
                "discord_category_id INTEGER, "
                "cat_embed_title TEXT, "
                "cat_embed_description TEXT, "
                "cat_embed_banner TEXT, "
                "cat_embed_thumbnail TEXT, "
                "FOREIGN KEY (guild_id) REFERENCES guild_configs(guild_id) ON DELETE CASCADE"
                ")"
            )
            for col, coltype in [
                ("cat_embed_title", "TEXT"),
                ("cat_embed_description", "TEXT"),
                ("cat_embed_banner", "TEXT"),
                ("cat_embed_thumbnail", "TEXT"),
            ]:
                try:
                    self.conn.execute(f"ALTER TABLE ticket_categories ADD COLUMN {col} {coltype}")
                except Exception:
                    pass

            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS open_tickets ("
                "channel_id INTEGER PRIMARY KEY, "
                "ticket_number INTEGER, "
                "guild_id INTEGER, "
                "creator_id INTEGER NOT NULL, "
                "category_db_id INTEGER, "
                "created_at TEXT NOT NULL, "
                "closed_by_id INTEGER, "
                "closed_at TEXT, "
                "is_locked BOOLEAN DEFAULT FALSE, "
                "is_claimed BOOLEAN DEFAULT FALSE, "
                "claimed_by_id INTEGER"
                ")"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS user_ticket_counts ("
                "guild_id INTEGER, "
                "user_id INTEGER, "
                "ticket_count INTEGER DEFAULT 0, "
                "PRIMARY KEY (guild_id, user_id)"
                ")"
            )

    def execute(self, q, p=()):
        with self.conn: return self.conn.execute(q, p)

    def fetchone(self, q, p=()):
        cur = self.conn.cursor(); cur.execute(q, p); return cur.fetchone()

    def fetchall(self, q, p=()):
        cur = self.conn.cursor(); cur.execute(q, p); return cur.fetchall()

    def close(self):
        if self.conn: self.conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# SHARED UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

async def _get_or_create_log_channel(db, guild):
    cfg = db.fetchone("SELECT logging_channel_id FROM guild_configs WHERE guild_id=?", (guild.id,))
    if cfg and cfg["logging_channel_id"]:
        ch = guild.get_channel(cfg["logging_channel_id"])
        if ch:
            return ch
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    try:
        from utils.branding import get_branding, DEFAULT_BRANDING
        branding = await get_branding(guild.id)
        branding_name = branding.get("branding_name", DEFAULT_BRANDING)
        channel_name = re.sub(r"[^a-z0-9-]", "", branding_name.lower().replace(" ", "-")) or DEFAULT_BRANDING.lower()
        channel_name = channel_name[:80]
        ch = await guild.create_text_channel(f"{channel_name}-ticket-logs", overwrites=overwrites)
        db.execute(
            "INSERT INTO guild_configs (guild_id, logging_channel_id) VALUES (?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET logging_channel_id=excluded.logging_channel_id",
            (guild.id, ch.id)
        )
        return ch
    except Exception:
        return None


async def _log_action(db, guild, user, action, details):
    ch = await _get_or_create_log_channel(db, guild)
    if not ch:
        return
    embed = discord.Embed(
        title=f"Ticket Action: {action}", color=EMBED_COLOR, timestamp=datetime.now()
    )
    embed.add_field(name="Action By", value=user.mention)
    embed.add_field(name="Details", value=details, inline=False)
    try:
        await ch.send(embed=embed)
    except Exception:
        pass


async def _get_or_create_closed_cat(db, guild):
    cfg = db.fetchone("SELECT closed_category_id FROM guild_configs WHERE guild_id=?", (guild.id,))
    if cfg and cfg["closed_category_id"]:
        cat = guild.get_channel(cfg["closed_category_id"])
        if cat:
            return cat
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    try:
        cat = await guild.create_category("Closed Tickets", overwrites=overwrites)
        db.execute("UPDATE guild_configs SET closed_category_id=? WHERE guild_id=?", (cat.id, guild.id))
        return cat
    except Exception:
        return None


def _is_staff(db, inter: discord.Interaction) -> bool:
    """True if the user has the configured staff role or manage_channels."""
    if inter.user.guild_permissions.manage_channels:
        return True
    cfg = db.fetchone("SELECT staff_role_id FROM guild_configs WHERE guild_id=?", (inter.guild.id,))
    if cfg and cfg["staff_role_id"]:
        role_id = cfg["staff_role_id"]
        return any(r.id == role_id for r in inter.user.roles)
    return False


# ═════════════════════════════════════════════════════════════════════════════
# SETUP VIEWS
# ═════════════════════════════════════════════════════════════════════════════

class SetupLandingView(discord.ui.View):
    """Always-shown first step: two buttons — Create New or Edit Existing."""

    def __init__(self, cog, ctx, panel_channel):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.panel_channel = panel_channel
        self.message = None

    def _embed(self):
        return discord.Embed(
            title=f"{_e('zticket')} Ticket Panel Setup",
            description=(
                f"**{_e('New')} Create New Panel** — Start fresh. Any existing panel config will be replaced.\n\n"
                f"**{_e('zmsg')} Edit Existing Panel** — Modify your current panel without losing category data."
            ),
            color=EMBED_COLOR
        )

    async def start_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self._embed(), view=self, ephemeral=True)
        self.message = await interaction.original_response()

    async def start_prefix(self, ctx):
        self.message = await ctx.send(embed=self._embed(), view=self)

    async def interaction_check(self, inter: discord.Interaction) -> bool:
        if inter.user.id != self.ctx.author.id:
            await inter.response.send_message("This setup is not for you.", ephemeral=True)
            return False
        return True

    def _disable_all(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Create New Panel", style=discord.ButtonStyle.success, emoji=_e("New") or "🆕", row=0)
    async def create_new(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.defer()
        self._disable_all()
        try:
            await self.message.edit(view=self)
        except Exception:
            pass
        view = PanelEmbedSetupView(self.cog, self.ctx, self.panel_channel, is_new=True)
        self.message = await inter.followup.send(
            content="**Step 1 — Panel Embed & Staff Role**",
            embed=view._preview_embed(),
            view=view,
            ephemeral=True,
            wait=True
        )
        view.message = self.message
        self.stop()

    @discord.ui.button(label="Edit Existing Panel", style=discord.ButtonStyle.primary, emoji=_e("zmsg") or "✏️", row=0)
    async def edit_existing(self, inter: discord.Interaction, btn: discord.ui.Button):
        existing = self.cog.db.fetchone("SELECT * FROM guild_configs WHERE guild_id=?", (inter.guild.id,))
        if not existing or not existing["panel_channel_id"]:
            await inter.response.send_message(
                f"{_e('zcross')} No existing panel found. Please **Create New Panel** instead.", ephemeral=True
            )
            return
        await inter.response.defer()
        self._disable_all()
        try:
            await self.message.edit(view=self)
        except Exception:
            pass
        view = PanelEmbedSetupView(
            self.cog, self.ctx, self.panel_channel, is_new=False, existing=existing
        )
        self.message = await inter.followup.send(
            content="**Step 1 — Panel Embed & Staff Role** *(editing existing)*",
            embed=view._preview_embed(),
            view=view,
            ephemeral=True,
            wait=True
        )
        view.message = self.message
        self.stop()


# ── Step 1: Panel embed + staff role ─────────────────────────────────────────

class PanelEmbedSetupView(discord.ui.View):
    def __init__(self, cog, ctx, panel_channel, is_new=True, existing=None):
        super().__init__(timeout=600)
        self.cog = cog
        self.ctx = ctx
        self.panel_channel = panel_channel
        self.is_new = is_new
        self.message = None

        self.embed_title       = "Support Tickets"
        self.embed_description = "Click a button below to open a ticket."
        self.embed_banner      = None
        self.embed_thumbnail   = None
        self.staff_role_id     = None

        if existing:
            self.embed_title       = existing["embed_title"]       or self.embed_title
            self.embed_description = existing["embed_description"] or self.embed_description
            self.embed_banner      = existing["embed_image_url"]
            self.embed_thumbnail   = existing["embed_thumbnail_url"]
            self.staff_role_id     = existing["staff_role_id"]

    def _preview_embed(self):
        embed = discord.Embed(
            title=self.embed_title,
            description=self.embed_description,
            color=EMBED_COLOR
        )
        if self.embed_banner:
            embed.set_image(url=self.embed_banner)
        if self.embed_thumbnail:
            embed.set_thumbnail(url=self.embed_thumbnail)
        staff_val = f"<@&{self.staff_role_id}>" if self.staff_role_id else "*Not set — any `manage_channels` user can manage tickets*"
        embed.add_field(name=f"{_e('headmod')} Staff Role", value=staff_val, inline=False)
        embed.set_footer(text="Use the buttons below to configure, then click Next Step.")
        return embed

    async def _prompt(self, inter: discord.Interaction, prompt: str):
        await inter.response.send_message(prompt, ephemeral=True)
        try:
            msg = await self.cog.bot.wait_for(
                "message",
                check=lambda m: m.author.id == self.ctx.author.id
                    and m.channel.id == self.ctx.channel.id,
                timeout=120
            )
            try:
                await msg.delete()
            except Exception:
                pass
            return msg.content
        except asyncio.TimeoutError:
            return None

    async def interaction_check(self, inter: discord.Interaction) -> bool:
        if inter.user.id != self.ctx.author.id:
            await inter.response.send_message("This setup is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Title", style=discord.ButtonStyle.green, row=0)
    async def btn_title(self, inter: discord.Interaction, btn: discord.ui.Button):
        if val := await self._prompt(inter, f"{_e('zmsg')} Type the **title** for your panel embed:"):
            self.embed_title = val
            await self.message.edit(embed=self._preview_embed())

    @discord.ui.button(label="Description", style=discord.ButtonStyle.green, row=0)
    async def btn_desc(self, inter: discord.Interaction, btn: discord.ui.Button):
        if val := await self._prompt(inter, f"{_e('zmsg')} Type the **description** for your panel embed:"):
            self.embed_description = val
            await self.message.edit(embed=self._preview_embed())

    @discord.ui.button(label="Banner URL", style=discord.ButtonStyle.blurple, row=1)
    async def btn_banner(self, inter: discord.Interaction, btn: discord.ui.Button):
        if val := await self._prompt(inter, f"{_e('zimage')} Paste the **banner image URL** (type `none` to remove):"):
            self.embed_banner = None if val.lower() == "none" else val
            await self.message.edit(embed=self._preview_embed())

    @discord.ui.button(label="Thumbnail URL", style=discord.ButtonStyle.blurple, row=1)
    async def btn_thumb(self, inter: discord.Interaction, btn: discord.ui.Button):
        if val := await self._prompt(inter, f"{_e('zimage')} Paste the **thumbnail URL** (type `none` to remove):"):
            self.embed_thumbnail = None if val.lower() == "none" else val
            await self.message.edit(embed=self._preview_embed())

    @discord.ui.button(label="Staff Role", style=discord.ButtonStyle.secondary, emoji=_e("headmod") or "👮", row=2)
    async def btn_role(self, inter: discord.Interaction, btn: discord.ui.Button):
        val = await self._prompt(
            inter,
            f"{_e('headmod')} **Mention the staff role** that can close/delete tickets (e.g. `@Support`).\n"
            "Only members with this role (or `Manage Channels`) will see the Close/Delete buttons."
        )
        if val:
            ids = re.findall(r"<@&(\d+)>", val)
            if ids:
                self.staff_role_id = int(ids[0])
                await self.message.edit(embed=self._preview_embed())
            else:
                try:
                    await inter.channel.send(f"{_e('zcross')} No role mention found. Try again.", delete_after=5)
                except Exception:
                    pass

    @discord.ui.button(label="Next Step ➜", style=discord.ButtonStyle.success, emoji=_e("zArrow") or "➡️", row=3)
    async def btn_next(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.defer()
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

        # Persist panel embed config
        self.cog.db.execute(
            "INSERT INTO guild_configs "
            "(guild_id, panel_channel_id, panel_type, embed_title, embed_description, embed_color, "
            "embed_image_url, embed_thumbnail_url, staff_role_id) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET "
            "panel_channel_id=excluded.panel_channel_id, panel_type=excluded.panel_type, "
            "embed_title=excluded.embed_title, embed_description=excluded.embed_description, "
            "embed_color=excluded.embed_color, embed_image_url=excluded.embed_image_url, "
            "embed_thumbnail_url=excluded.embed_thumbnail_url, staff_role_id=excluded.staff_role_id",
            (
                self.ctx.guild.id, self.panel_channel.id, "button",
                self.embed_title, self.embed_description, EMBED_COLOR,
                self.embed_banner, self.embed_thumbnail, self.staff_role_id
            )
        )

        # Pre-load existing categories if editing
        preloaded = []
        if not self.is_new:
            rows = self.cog.db.fetchall(
                "SELECT * FROM ticket_categories WHERE guild_id=?", (self.ctx.guild.id,)
            )
            for r in rows:
                preloaded.append({
                    "name": r["name"],
                    "emoji": r["emoji"],
                    "discord_category_id": r["discord_category_id"],
                    "cat_embed_title": r["cat_embed_title"],
                    "cat_embed_description": r["cat_embed_description"],
                    "cat_embed_banner": r["cat_embed_banner"],
                    "cat_embed_thumbnail": r["cat_embed_thumbnail"],
                })

        btn_view = ButtonManagerView(self.cog, self.ctx, preloaded_buttons=preloaded)
        new_msg = await inter.followup.send(
            embed=btn_view._build_embed(), view=btn_view, ephemeral=True, wait=True
        )
        btn_view.message = new_msg
        self.stop()


# ── Step 2: Button manager ────────────────────────────────────────────────────

class ButtonManagerView(discord.ui.View):
    """Manage panel buttons and configure per-button ticket embeds."""

    def __init__(self, cog, ctx, preloaded_buttons=None):
        super().__init__(timeout=900)
        self.cog = cog
        self.ctx = ctx
        self.message = None
        # Each dict: name, emoji, discord_category_id,
        #            cat_embed_title, cat_embed_description, cat_embed_banner, cat_embed_thumbnail
        self.buttons: list[dict] = preloaded_buttons or []
        self._rebuild_components()

    def _rebuild_components(self):
        self.clear_items()

        # Row 0 — Add Button
        self.add_item(discord.ui.Button(
            label=f"Add Button {_e('zplus') or '➕'}",
            style=discord.ButtonStyle.success,
            custom_id="bmv:add",
            row=0
        ))

        # Row 1 — "Configure Ticket" dropdown
        if self.buttons:
            opts = [
                discord.SelectOption(
                    label=b["name"][:100],
                    value=str(i),
                    emoji=_parse_emoji(b.get("emoji")),
                    description="Click to configure this button's ticket embed"
                )
                for i, b in enumerate(self.buttons)
            ]
            disabled = False
        else:
            opts = [discord.SelectOption(label="No buttons yet — add one first", value="__none__")]
            disabled = True

        self.add_item(discord.ui.Select(
            placeholder="🔧 Configure Ticket — pick a button to set its ticket embed",  # placeholder: keep Unicode (Discord renders custom emojis poorly in placeholders)
            custom_id="bmv:configure",
            options=opts,
            row=1,
            disabled=disabled
        ))

        # Row 2 — "Delete Category" dropdown
        if self.buttons:
            del_opts = [
                discord.SelectOption(
                    label=b["name"][:100],
                    value=str(i),
                    emoji=_parse_emoji(b.get("emoji")),
                    description="Click to delete this category"
                )
                for i, b in enumerate(self.buttons)
            ]
            del_disabled = False
        else:
            del_opts = [discord.SelectOption(label="No categories yet", value="__none__")]
            del_disabled = True

        self.add_item(discord.ui.Select(
            placeholder="🗑️ Delete Category — pick a category to remove",  # placeholder: keep Unicode (Discord renders custom emojis poorly in placeholders)
            custom_id="bmv:delete",
            options=del_opts,
            row=2,
            disabled=del_disabled
        ))

        # Row 3 — Send Panel
        self.add_item(discord.ui.Button(
            label=f"Send Panel {_e('ztick') or '✅'}",
            style=discord.ButtonStyle.primary,
            custom_id="bmv:send",
            row=3
        ))

    def _build_embed(self):
        embed = discord.Embed(
            title="Step 2 — Panel Buttons",
            description=(
                "Add ticket category buttons for your panel.\n"
                f"Use **{_e('zwrench')} Configure Ticket** to set the embed shown inside each ticket type.\n"
                f"Hit **Send Panel {_e('ztick')}** when finished."
            ),
            color=EMBED_COLOR
        )
        if self.buttons:
            lines = []
            for b in self.buttons:
                emoji_part = (b.get("emoji") or "") + " " if b.get("emoji") else ""
                has_config = _e("ztick") if b.get("cat_embed_title") else _e("zcircle2") or "⬜"
                lines.append(f"{has_config} {emoji_part}**{b['name']}**")
            embed.add_field(
                name=f"Buttons ({len(self.buttons)}/{MAX_BUTTONS})  {_e('ztick')} = ticket embed configured",
                value="\n".join(lines),
                inline=False
            )
        else:
            embed.add_field(
                name="Buttons (0)",
                value=f"*No buttons yet. Click **Add Button {_e('zplus')}** to start.*",
                inline=False
            )
        return embed

    async def _prompt(self, inter: discord.Interaction, prompt: str, followup: bool = False):
        if followup:
            await inter.followup.send(prompt, ephemeral=True)
        else:
            await inter.response.send_message(prompt, ephemeral=True)
        try:
            msg = await self.cog.bot.wait_for(
                "message",
                check=lambda m: m.author.id == self.ctx.author.id
                    and m.channel.id == inter.channel.id,
                timeout=120
            )
            try:
                await msg.delete()
            except Exception:
                pass
            return msg.content
        except asyncio.TimeoutError:
            return None

    async def interaction_check(self, inter: discord.Interaction) -> bool:
        if inter.user.id != self.ctx.author.id:
            await inter.response.send_message("This setup is not for you.", ephemeral=True)
            return False
        cid = inter.data.get("custom_id", "")
        if cid == "bmv:add":
            await self._add_button(inter)
        elif cid == "bmv:configure":
            val = (inter.data.get("values") or ["__none__"])[0]
            if val != "__none__":
                await self._configure_ticket(inter, int(val))
            else:
                await inter.response.defer()
        elif cid == "bmv:delete":
            val = (inter.data.get("values") or ["__none__"])[0]
            if val != "__none__":
                await self._delete_category(inter, int(val))
            else:
                await inter.response.defer()
        elif cid == "bmv:send":
            await self._send_panel(inter)
        return True

    async def _add_button(self, inter: discord.Interaction):
        await inter.response.defer()
        if len(self.buttons) >= MAX_BUTTONS:
            return await inter.followup.send(
                f"{_e('zcross')} Maximum {MAX_BUTTONS} buttons reached.", ephemeral=True
            )

        name = await self._prompt(
            inter,
            f"{_e('zmsg')} Type the **name** for this ticket button (e.g. `General Support`):",
            followup=True
        )
        if not name:
            return await inter.followup.send(f"{_e('ztimer')} Timed out.", ephemeral=True)

        emoji = await self._prompt(
            inter,
            f"{_e('ztada')} Send the **emoji** for this button (e.g. `🎫` or a custom emoji), or type `skip`:",
            followup=True
        )
        if not emoji:
            return await inter.followup.send(f"{_e('ztimer')} Timed out.", ephemeral=True)
        if emoji.lower() == "skip":
            emoji = None

        self.buttons.append({
            "name": name,
            "emoji": emoji,
            "discord_category_id": None,
            "cat_embed_title": None,
            "cat_embed_description": None,
            "cat_embed_banner": None,
            "cat_embed_thumbnail": None,
        })
        self._rebuild_components()
        await self.message.edit(embed=self._build_embed(), view=self)
        await inter.followup.send(f"{_e('ztick')} Button **{name}** added!", ephemeral=True)

    async def _delete_category(self, inter: discord.Interaction, idx: int):
        if idx >= len(self.buttons):
            await inter.response.defer()
            return
        removed = self.buttons.pop(idx)
        self._rebuild_components()
        await inter.response.edit_message(embed=self._build_embed(), view=self)
        await inter.followup.send(
            f"{_e('delete')} Removed category **{removed['name']}** from the panel.", ephemeral=True
        )

    async def _configure_ticket(self, inter: discord.Interaction, idx: int):
        if idx >= len(self.buttons):
            await inter.response.defer()
            return
        btn_data = self.buttons[idx]
        config_view = TicketEmbedConfigView(self.cog, self.ctx, btn_data, idx, self)
        # Edit the current message to show the ticket embed config
        await inter.response.edit_message(
            embed=config_view._build_preview(),
            view=config_view
        )

    async def _send_panel(self, inter: discord.Interaction):
        if not self.buttons:
            return await inter.response.send_message(
                f"{_e('zcross')} Add at least one button before sending the panel.", ephemeral=True
            )
        await inter.response.defer()
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

        guild_id = self.ctx.guild.id
        config = self.cog.db.fetchone("SELECT * FROM guild_configs WHERE guild_id=?", (guild_id,))
        if not config:
            return await inter.followup.send(
                f"{_e('zcross')} Configuration lost. Please run `/ticket setup` again.", ephemeral=True
            )

        panel_ch = self.ctx.guild.get_channel(config["panel_channel_id"])
        if not panel_ch:
            return await inter.followup.send(
                f"{_e('zcross')} The panel channel no longer exists.", ephemeral=True
            )

        # Rebuild ticket_categories in DB
        self.cog.db.execute("DELETE FROM ticket_categories WHERE guild_id=?", (guild_id,))
        staff_role_id = config["staff_role_id"]

        # ── Shared "Tickets" category — one category at the top for all ticket types ──
        # Look for an existing category already stored in any row for this guild,
        # or fall back to any Discord category literally named "Tickets".
        shared_cat = None

        existing_cat_id = self.cog.db.fetchone(
            "SELECT discord_category_id FROM ticket_categories WHERE guild_id=? LIMIT 1",
            (guild_id,)
        )
        if existing_cat_id and existing_cat_id["discord_category_id"]:
            shared_cat = self.ctx.guild.get_channel(existing_cat_id["discord_category_id"])

        if not shared_cat:
            # Try to find an existing "Tickets" category in Discord
            shared_cat = discord.utils.find(
                lambda c: isinstance(c, discord.CategoryChannel) and c.name.lower() == "tickets",
                self.ctx.guild.channels
            )

        if not shared_cat:
            try:
                shared_cat = await self.ctx.guild.create_category(
                    "Tickets",
                    overwrites={
                        self.ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False)
                    }
                )
            except Exception:
                await inter.followup.send(
                    f"{_e('zcross')} Couldn't create the **Tickets** category. "
                    "Check my permissions and try again.",
                    ephemeral=True
                )
                return

        # Move the Tickets category to position 0 (top of all channels)
        try:
            await shared_cat.edit(position=0)
        except Exception:
            pass  # Non-fatal — category still works even if repositioning fails

        for btn in self.buttons:
            self.cog.db.execute(
                "INSERT INTO ticket_categories "
                "(guild_id, name, emoji, notified_roles, button_style, discord_category_id, "
                "cat_embed_title, cat_embed_description, cat_embed_banner, cat_embed_thumbnail) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    guild_id, btn["name"], btn["emoji"],
                    str(staff_role_id) if staff_role_id else None,
                    discord.ButtonStyle.secondary.value,
                    shared_cat.id,
                    btn.get("cat_embed_title"),
                    btn.get("cat_embed_description"),
                    btn.get("cat_embed_banner"),
                    btn.get("cat_embed_thumbnail"),
                )
            )

        # Delete old panel message if it exists
        if config["panel_message_id"]:
            try:
                old_msg = await panel_ch.fetch_message(config["panel_message_id"])
                await old_msg.delete()
            except Exception:
                pass

        # Build panel embed
        panel_embed = discord.Embed(
            title=config["embed_title"] or "Support Tickets",
            description=config["embed_description"] or "Click a button below to open a ticket.",
            color=config["embed_color"] or EMBED_COLOR
        )
        if config["embed_image_url"]:
            panel_embed.set_image(url=config["embed_image_url"])
        if config["embed_thumbnail_url"]:
            panel_embed.set_thumbnail(url=config["embed_thumbnail_url"])

        final_view = self.cog.create_panel_view(guild_id)
        if not final_view:
            return await inter.followup.send(f"{_e('zcross')} Failed to build panel view.", ephemeral=True)

        msg = await panel_ch.send(embed=panel_embed, view=final_view)
        self.cog.db.execute(
            "UPDATE guild_configs SET panel_message_id=? WHERE guild_id=?", (msg.id, guild_id)
        )
        await inter.followup.send(
            f"{_e('ztick')} Ticket panel sent to {panel_ch.mention}!", ephemeral=True
        )
        self.stop()


# ── Step 2b: Per-button ticket embed configurator ─────────────────────────────

class TicketEmbedConfigView(discord.ui.View):
    """Configure the embed shown inside ticket channels for a specific button.
    Renders in-place within the ButtonManagerView message — Done returns to it."""

    def __init__(self, cog, ctx, btn_data: dict, btn_idx: int, manager: ButtonManagerView):
        super().__init__(timeout=600)
        self.cog = cog
        self.ctx = ctx
        self.btn_data = btn_data
        self.btn_idx = btn_idx
        self.manager = manager

        self.t_title  = btn_data.get("cat_embed_title")       or "Welcome to your Ticket!"
        self.t_desc   = btn_data.get("cat_embed_description") or (
            "Thank you for reaching out. Our staff team has been notified and will be with you shortly.\n\n"
            "Please describe your issue in detail while you wait."
        )
        self.t_banner = btn_data.get("cat_embed_banner")      or ""
        self.t_thumb  = btn_data.get("cat_embed_thumbnail")   or ""

    def _build_preview(self):
        embed = discord.Embed(
            title=self.t_title,
            description=self.t_desc,
            color=EMBED_COLOR
        )
        embed.set_author(
            name=f"Configuring: {self.btn_data['name']} tickets",
            icon_url=self.ctx.author.display_avatar.url
        )
        if self.t_banner:
            embed.set_image(url=self.t_banner)
        if self.t_thumb:
            embed.set_thumbnail(url=self.t_thumb)
        embed.set_footer(
            text="This is a preview of the ticket channel embed. Click Done to return."
        )
        return embed

    async def _prompt(self, inter: discord.Interaction, prompt: str):
        await inter.response.send_message(prompt, ephemeral=True)
        try:
            msg = await self.cog.bot.wait_for(
                "message",
                check=lambda m: m.author.id == self.ctx.author.id
                    and m.channel.id == self.ctx.channel.id,
                timeout=120
            )
            try:
                await msg.delete()
            except Exception:
                pass
            return msg.content
        except asyncio.TimeoutError:
            return None

    async def interaction_check(self, inter: discord.Interaction) -> bool:
        if inter.user.id != self.ctx.author.id:
            await inter.response.send_message("This setup is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Title", style=discord.ButtonStyle.green, row=0)
    async def btn_title(self, inter: discord.Interaction, btn: discord.ui.Button):
        if val := await self._prompt(inter, f"{_e('zmsg')} Enter the **title** for this ticket's channel embed:"):
            self.t_title = val
            await inter.message.edit(embed=self._build_preview(), view=self)

    @discord.ui.button(label="Description", style=discord.ButtonStyle.green, row=0)
    async def btn_desc(self, inter: discord.Interaction, btn: discord.ui.Button):
        if val := await self._prompt(inter, f"{_e('zmsg')} Enter the **description** for this ticket's channel embed:"):
            self.t_desc = val
            await inter.message.edit(embed=self._build_preview(), view=self)

    @discord.ui.button(label="Banner URL", style=discord.ButtonStyle.blurple, row=1)
    async def btn_banner(self, inter: discord.Interaction, btn: discord.ui.Button):
        if val := await self._prompt(inter, f"{_e('zimage')} Paste the **banner URL** (type `none` to remove):"):
            self.t_banner = "" if val.lower() == "none" else val
            await inter.message.edit(embed=self._build_preview(), view=self)

    @discord.ui.button(label="Thumbnail URL", style=discord.ButtonStyle.blurple, row=1)
    async def btn_thumb(self, inter: discord.Interaction, btn: discord.ui.Button):
        if val := await self._prompt(inter, f"{_e('zimage')} Paste the **thumbnail URL** (type `none` to remove):"):
            self.t_thumb = "" if val.lower() == "none" else val
            await inter.message.edit(embed=self._build_preview(), view=self)

    @discord.ui.button(label="Done", emoji=_e("ztick") or "✅", style=discord.ButtonStyle.success, row=2)
    async def btn_done(self, inter: discord.Interaction, btn: discord.ui.Button):
        # Flush values back into the shared dict
        self.btn_data["cat_embed_title"]       = self.t_title
        self.btn_data["cat_embed_description"] = self.t_desc
        self.btn_data["cat_embed_banner"]      = self.t_banner or None
        self.btn_data["cat_embed_thumbnail"]   = self.t_thumb  or None
        # The dict is a reference to self.manager.buttons[idx], so it's already updated.
        # Rebuild the manager components so the ✅ indicator refreshes.
        self.manager._rebuild_components()
        await inter.response.edit_message(
            embed=self.manager._build_embed(), view=self.manager
        )
        self.stop()


# ═════════════════════════════════════════════════════════════════════════════
# PANEL VIEW — public, persistent
# ═════════════════════════════════════════════════════════════════════════════

class TicketPanelButtons(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog


# ═════════════════════════════════════════════════════════════════════════════
# TICKET ACTION VIEWS — inside ticket channels
# ═════════════════════════════════════════════════════════════════════════════

class TicketActionsView(discord.ui.View):
    """Shown inside an open ticket — Close and Delete. Staff-only."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def interaction_check(self, inter: discord.Interaction) -> bool:
        if _is_staff(self.cog.db, inter):
            return True
        await inter.response.send_message(
            f"{_e('zcross')} Only staff members can manage tickets.", ephemeral=True
        )
        return False

    @discord.ui.button(
        label="Close", emoji=_e('lock') or '🔒',
        style=discord.ButtonStyle.danger, custom_id="t_close"
    )
    async def b_close(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.defer(ephemeral=True)

        ticket = self.cog.db.fetchone(
            "SELECT * FROM open_tickets WHERE channel_id=?", (inter.channel.id,)
        )
        if not ticket:
            return await inter.followup.send(f"{_e('zcross')} No ticket record for this channel.", ephemeral=True)

        creator = inter.guild.get_member(ticket["creator_id"])
        if creator:
            # Remove send permission — keep them visible so they can read
            await inter.channel.set_permissions(creator, send_messages=False)
            self.cog.db.execute(
                "UPDATE user_ticket_counts SET ticket_count=MAX(0,ticket_count-1) "
                "WHERE guild_id=? AND user_id=?",
                (inter.guild.id, creator.id)
            )

        self.cog.db.execute(
            "UPDATE open_tickets SET closed_by_id=?, closed_at=?, is_locked=1 WHERE channel_id=?",
            (inter.user.id, datetime.now().isoformat(), inter.channel.id)
        )

        # Disable this view
        for item in self.children:
            item.disabled = True
        try:
            await inter.message.edit(view=self)
        except Exception:
            pass

        close_embed = discord.Embed(
            title=f"{_e('lock')} Ticket Closed",
            description=(
                f"This ticket was closed by {inter.user.mention}.\n"
                f"The ticket opener can no longer send messages here.\n\n"
                f"Use the buttons below to delete or reopen the ticket."
            ),
            color=EMBED_COLOR,
            timestamp=datetime.now()
        )
        if creator:
            close_embed.add_field(name="Ticket Opener", value=creator.mention, inline=True)
        close_embed.add_field(name="Closed By", value=inter.user.mention, inline=True)

        await inter.channel.send(
            embed=close_embed,
            view=ClosedTicketView(self.cog)
        )
        await inter.followup.send(f"{_e('lock')} Ticket closed successfully.", ephemeral=True)

        # DM the staff member
        try:
            await inter.user.send(
                f"{_e('ztick')} You closed ticket **#{inter.channel.name}** in **{inter.guild.name}**."
            )
        except Exception:
            pass

        await _log_action(
            self.cog.db, inter.guild, inter.user, "Closed", inter.channel.mention
        )
        self.stop()

    @discord.ui.button(
        label="Delete", emoji=_e("delete") or "🗑️",
        style=discord.ButtonStyle.danger, custom_id="t_delete"
    )
    async def b_delete(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.defer(ephemeral=True)
        channel_name = inter.channel.name
        await inter.followup.send(
            f"{_e('delete')} This ticket channel will be **permanently deleted** in 5 seconds...",
            ephemeral=True
        )

        # DM the staff member
        try:
            await inter.user.send(
                f"{_e('delete')} You deleted ticket **#{channel_name}** in **{inter.guild.name}**."
            )
        except Exception:
            pass

        await _log_action(
            self.cog.db, inter.guild, inter.user, "Deleted", f"#{channel_name}"
        )
        await asyncio.sleep(5)
        self.cog.db.execute(
            "DELETE FROM open_tickets WHERE channel_id=?", (inter.channel.id,)
        )
        try:
            await inter.channel.delete(reason=f"Ticket deleted by {inter.user}")
        except Exception:
            pass
        self.stop()


class ClosedTicketView(discord.ui.View):
    """Shown after a ticket is closed — Reopen and Delete. Staff-only."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def interaction_check(self, inter: discord.Interaction) -> bool:
        if _is_staff(self.cog.db, inter):
            return True
        await inter.response.send_message(
            f"{_e('zcross')} Only staff members can manage tickets.", ephemeral=True
        )
        return False

    @discord.ui.button(
        label="Reopen", emoji=_e("zwrench") or "🔧",
        style=discord.ButtonStyle.success, custom_id="tc_reopen"
    )
    async def b_reopen(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.defer(ephemeral=True)

        ticket = self.cog.db.fetchone(
            "SELECT * FROM open_tickets WHERE channel_id=?", (inter.channel.id,)
        )
        if not ticket:
            return await inter.followup.send(f"{_e('zcross')} No ticket record found.", ephemeral=True)

        creator = inter.guild.get_member(ticket["creator_id"])
        if creator:
            await inter.channel.set_permissions(creator, send_messages=True, view_channel=True)
            self.cog.db.execute(
                "INSERT INTO user_ticket_counts VALUES (?,?,1) "
                "ON CONFLICT(guild_id,user_id) DO UPDATE SET ticket_count=ticket_count+1",
                (inter.guild.id, creator.id)
            )

        self.cog.db.execute(
            "UPDATE open_tickets SET closed_by_id=NULL, closed_at=NULL, is_locked=0 "
            "WHERE channel_id=?",
            (inter.channel.id,)
        )

        # Disable closed view
        for item in self.children:
            item.disabled = True
        try:
            await inter.message.edit(view=self)
        except Exception:
            pass

        reopen_embed = discord.Embed(
            title=f"{_e('zwrench')} Ticket Reopened",
            description=f"This ticket was reopened by {inter.user.mention}.",
            color=EMBED_COLOR,
            timestamp=datetime.now()
        )
        await inter.channel.send(
            embed=reopen_embed,
            view=TicketActionsView(self.cog)
        )
        await inter.followup.send(f"{_e('zwrench')} Ticket reopened.", ephemeral=True)
        await _log_action(
            self.cog.db, inter.guild, inter.user, "Reopened", inter.channel.mention
        )
        self.stop()

    @discord.ui.button(
        label="Delete Channel", emoji=_e("delete") or "🗑️",
        style=discord.ButtonStyle.danger, custom_id="tc_delete"
    )
    async def b_delete(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.defer(ephemeral=True)
        channel_name = inter.channel.name
        await inter.followup.send(
            f"{_e('delete')} Deleting this ticket channel in **5 seconds**...", ephemeral=True
        )

        try:
            await inter.user.send(
                f"{_e('delete')} You deleted ticket **#{channel_name}** in **{inter.guild.name}**."
            )
        except Exception:
            pass

        await _log_action(
            self.cog.db, inter.guild, inter.user, "Deleted", f"#{channel_name}"
        )
        await asyncio.sleep(5)
        self.cog.db.execute(
            "DELETE FROM open_tickets WHERE channel_id=?", (inter.channel.id,)
        )
        try:
            await inter.channel.delete(reason=f"Ticket deleted by {inter.user}")
        except Exception:
            pass
        self.stop()


# ═════════════════════════════════════════════════════════════════════════════
# MAIN COG
# ═════════════════════════════════════════════════════════════════════════════

class TicketCog(commands.Cog, name="Ticket System"):
    def __init__(self, bot):
        self.bot = bot
        self.db = TicketDatabase(DB_PATH)
        self.bot.loop.create_task(self._load_persistent_views())

    async def _load_persistent_views(self):
        await self.bot.wait_until_ready()

        # Panel views
        for cfg in self.db.fetchall(
            "SELECT guild_id, panel_message_id FROM guild_configs WHERE panel_message_id IS NOT NULL"
        ):
            if view := self.create_panel_view(cfg["guild_id"]):
                self.bot.add_view(view, message_id=cfg["panel_message_id"])

        # Persistent ticket action views — one instance handles ALL tickets
        # (Discord routes by custom_id; ch_id is resolved from inter.channel.id in callbacks)
        self.bot.add_view(TicketActionsView(self))
        self.bot.add_view(ClosedTicketView(self))

    def create_panel_view(self, guild_id: int):
        cats = self.db.fetchall("SELECT * FROM ticket_categories WHERE guild_id=?", (guild_id,))
        if not cats:
            return None
        view = TicketPanelButtons(self)
        for cat in cats:
            view.add_item(discord.ui.Button(
                label=cat["name"],
                style=discord.ButtonStyle.secondary,
                # Ticket panel controls use the bot's uploaded custom emoji
                # store rather than arbitrary Unicode/server emojis.
                emoji=_parse_emoji(_e("zticket")),
                custom_id=f"create_ticket_{cat['category_id']}"
            ))
        return view

    def cog_unload(self):
        self.db.close()

    # ── Ticket creation listener ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_interaction(self, inter: discord.Interaction):
        if (
            inter.type == discord.InteractionType.component
            and (cid := inter.data.get("custom_id", "")).startswith("create_ticket_")
        ):
            try:
                cat_id = int(cid.removeprefix("create_ticket_"))
                await self._create_ticket_flow(inter, cat_id)
            except Exception as exc:
                print(f"[Ticket] create_ticket_flow error: {exc}")

    async def _create_ticket_flow(self, inter: discord.Interaction, cat_id: int):
        await inter.response.defer(ephemeral=True)
        guild, user = inter.guild, inter.user

        cat_info = self.db.fetchone(
            "SELECT * FROM ticket_categories WHERE category_id=?", (cat_id,)
        )
        if not cat_info:
            return await inter.followup.send(
                f"{_e('zcross')} This ticket category no longer exists.", ephemeral=True
            )

        disc_cat = guild.get_channel(cat_info["discord_category_id"])
        if not disc_cat:
            return await inter.followup.send(
                f"{_e('zcross')} The Discord category for this ticket type is missing or was deleted.",
                ephemeral=True
            )

        config = self.db.fetchone("SELECT * FROM guild_configs WHERE guild_id=?", (guild.id,))
        staff_role_id = config["staff_role_id"] if config else None
        staff_role = guild.get_role(staff_role_id) if staff_role_id else None

        t_num = (
            self.db.fetchone(
                "SELECT MAX(ticket_number) as n FROM open_tickets WHERE guild_id=?", (guild.id,)
            )["n"] or 0
        ) + 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, manage_channels=True, manage_messages=True
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )

        try:
            ch = await disc_cat.create_text_channel(
                name=f"ticket-{t_num:04d}-{user.name.lower()[:15]}",
                overwrites=overwrites
            )
        except Exception:
            return await inter.followup.send(
                f"{_e('zcross')} I don't have permission to create ticket channels.", ephemeral=True
            )

        self.db.execute(
            "INSERT INTO open_tickets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ch.id, t_num, guild.id, user.id, cat_id,
             datetime.now().isoformat(), None, None, False, False, None)
        )
        self.db.execute(
            "INSERT INTO user_ticket_counts VALUES (?,?,1) "
            "ON CONFLICT(guild_id,user_id) DO UPDATE SET ticket_count=ticket_count+1",
            (guild.id, user.id)
        )

        # Build ticket channel embed from per-button config (with fallbacks)
        embed_title  = cat_info["cat_embed_title"]       or f"Ticket #{t_num:04d} — {cat_info['name']}"
        embed_desc   = cat_info["cat_embed_description"] or (
            "Thank you for reaching out. Our staff team has been notified and will be with you shortly.\n\n"
            "Please describe your issue in detail while you wait."
        )
        embed_banner = cat_info["cat_embed_banner"]
        embed_thumb  = cat_info["cat_embed_thumbnail"]

        ticket_embed = discord.Embed(
            title=embed_title, description=embed_desc, color=EMBED_COLOR
        )
        ticket_embed.set_author(
            name=user.display_name, icon_url=user.display_avatar.url
        )
        if embed_banner:
            ticket_embed.set_image(url=embed_banner)
        if embed_thumb:
            ticket_embed.set_thumbnail(url=embed_thumb)

        pings = [user.mention]
        if staff_role:
            pings.append(staff_role.mention)

        await ch.send(
            content=" ".join(pings),
            embed=ticket_embed,
            view=TicketActionsView(self)
        )
        await inter.followup.send(
            f"{_e('ztick')} Your ticket has been created: {ch.mention}", ephemeral=True
        )
        await _log_action(
            self.db, guild, user, "Opened",
            f"{ch.mention} (category: {cat_info['name']})"
        )

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.hybrid_group(name="ticket", description="Ticket system commands.")
    @commands.guild_only()
    async def ticket(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @ticket.command(name="setup", description="Set up the ticket panel for this server.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel where the ticket panel embed will be posted.")
    async def setup(self, ctx, channel: discord.TextChannel):
        view = SetupLandingView(self, ctx, channel)
        if ctx.interaction:
            await view.start_slash(ctx.interaction)
        else:
            await view.start_prefix(ctx)


async def setup(bot):
    cog = TicketCog(bot)
    await bot.add_cog(cog)
    # Register persistent views so ticket buttons survive bot restarts
    bot.add_view(TicketActionsView(cog))
    bot.add_view(ClosedTicketView(cog))
