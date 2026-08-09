"""Interactive reaction-role panel builder.

The old ``/createrr`` command only supported adding one reaction to an
existing message.  This cog owns the complete setup flow for ``/setuprr`` and
the component handler for published role panels.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.emojis import e as _e, get_store


DB_PATH = "rr.db"
MAX_PANEL_BUTTONS = 25  # Discord's maximum number of buttons in one message.


def _icon(name: str) -> str:
    """Return an uploaded custom emoji, or no emoji when it is not uploaded."""
    return _e(name)


def _custom_emoji(value: str) -> Optional[discord.PartialEmoji]:
    """Parse only a custom emoji that exists in the uploaded emoji store."""
    value = value.strip()
    store = get_store()
    if value in store:
        value = store[value]
    if value not in store.values():
        return None
    try:
        return discord.PartialEmoji.from_str(value)
    except (TypeError, ValueError):
        return None


def _emoji_name(value: str) -> Optional[str]:
    value = value.strip()
    store = get_store()
    if value in store:
        return value
    for name, emoji in store.items():
        if emoji == value:
            return name
    return None


def _parse_color(value: str) -> Optional[int]:
    value = value.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return None
    return int(value, 16)


def _status(name: str, text: str) -> str:
    icon = _icon(name)
    return f"{icon} {text}" if icon else text


class ReactionRoleDB:
    """Small synchronous store; setup actions are infrequent and short."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        with sqlite3.connect(self.path) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS rr_panels (
                    guild_id INTEGER NOT NULL,
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    image TEXT NOT NULL DEFAULT '',
                    thumbnail TEXT NOT NULL DEFAULT '',
                    color INTEGER NOT NULL DEFAULT 16766720,
                    multi INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS rr_buttons (
                    message_id INTEGER NOT NULL,
                    button_key TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    emoji TEXT NOT NULL DEFAULT '',
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (message_id, button_key),
                    FOREIGN KEY (message_id) REFERENCES rr_panels(message_id)
                        ON DELETE CASCADE
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS rr_settings (
                    guild_id INTEGER PRIMARY KEY,
                    dm_enabled INTEGER NOT NULL DEFAULT 1
                )
                """
            )

    def save_panel(self, guild_id: int, channel_id: int, message: discord.Message,
                   state: dict) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                """
                INSERT OR REPLACE INTO rr_panels
                  (guild_id, message_id, channel_id, title, description, image,
                   thumbnail, color, multi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id, message.id, channel_id, state["title"],
                    state["description"], state["image"], state["thumbnail"],
                    state["color"], int(state["multi"]),
                ),
            )
            db.execute("DELETE FROM rr_buttons WHERE message_id = ?", (message.id,))
            db.executemany(
                """
                INSERT INTO rr_buttons
                  (message_id, button_key, label, emoji, role_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (message.id, button["key"], button["label"],
                     button["emoji"], button["role_id"])
                    for button in state["buttons"]
                ],
            )

    def panels(self) -> list[tuple]:
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT guild_id, message_id, channel_id, title, description, "
                "image, thumbnail, color, multi FROM rr_panels"
            ).fetchall()

    def panel_button(self, message_id: int, button_key: str) -> Optional[tuple]:
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT guild_id, channel_id, title, description, image, "
                "thumbnail, color, multi, label, emoji, role_id "
                "FROM rr_panels JOIN rr_buttons USING (message_id) "
                "WHERE rr_panels.message_id = ? AND button_key = ?",
                (message_id, button_key),
            ).fetchone()

    def panel_buttons(self, message_id: int) -> list[tuple]:
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT button_key, label, emoji, role_id FROM rr_buttons "
                "WHERE message_id = ? ORDER BY rowid",
                (message_id,),
            ).fetchall()

    def set_dm_setting(self, guild_id: int, enabled: bool) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO rr_settings (guild_id, dm_enabled) VALUES (?, ?)",
                (guild_id, int(enabled)),
            )

    def dm_enabled(self, guild_id: int) -> bool:
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT dm_enabled FROM rr_settings WHERE guild_id = ?",
                (guild_id,),
            ).fetchone()
        return row is None or bool(row[0])


def _setup_embed(state: dict) -> discord.Embed:
    embed = discord.Embed(
        title=state["title"] or "Reaction roles",
        description=state["description"] or "Configure this panel, then send it to a channel.",
        color=state["color"],
    )
    if state["thumbnail"]:
        embed.set_thumbnail(url=state["thumbnail"])
    if state["image"]:
        embed.set_image(url=state["image"])
    embed.set_footer(
        text=f"Multi-select: {'Enabled' if state['multi'] else 'Disabled'} • "
             f"{len(state['buttons'])}/{MAX_PANEL_BUTTONS} buttons"
    )
    return embed


class RRTextModal(discord.ui.Modal):
    def __init__(self, setup_view: "RRSetupView", field: str, label: str,
                 placeholder: str = ""):
        super().__init__(title=f"Set {label}"[:45])
        self.setup_view = setup_view
        self.field = field
        self.input = discord.ui.TextInput(
            label=label[:45], default=setup_view.state[field] or None,
            placeholder=placeholder[:100], required=False, max_length=4000,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        self.setup_view.state[self.field] = self.input.value.strip()
        await self.setup_view.refresh(interaction, _status("ztick", "Updated."))


class RRColorModal(discord.ui.Modal):
    def __init__(self, setup_view: "RRSetupView"):
        super().__init__(title="Set embed colour")
        self.setup_view = setup_view
        self.input = discord.ui.TextInput(
            label="Hex colour", placeholder="#FFD700", required=True,
            default=f"#{setup_view.state['color']:06X}", max_length=7,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        color = _parse_color(self.input.value)
        if color is None:
            return await interaction.response.send_message(
                _status("zcross", "Use a six-digit hex colour such as #FFD700."),
                ephemeral=True,
            )
        self.setup_view.state["color"] = color
        await self.setup_view.refresh(interaction, _status("ztick", "Colour updated."))


class RRAddButtonModal(discord.ui.Modal):
    def __init__(self, setup_view: "RRSetupView"):
        super().__init__(title="Add reaction-role button")
        self.setup_view = setup_view
        self.label_input = discord.ui.TextInput(
            label="Button text (leave empty for emoji-only)",
            required=False, max_length=80,
        )
        self.emoji_input = discord.ui.TextInput(
            label="Uploaded emoji name or emoji (leave empty for text-only)",
            required=False, max_length=100,
        )
        self.add_item(self.label_input)
        self.add_item(self.emoji_input)

    async def on_submit(self, interaction: discord.Interaction):
        label = self.label_input.value.strip()
        emoji_value = self.emoji_input.value.strip()
        if bool(label) == bool(emoji_value):
            return await interaction.response.send_message(
                _status("zcross", "Set text only or one uploaded custom emoji only."),
                ephemeral=True,
            )
        if len(self.setup_view.state["buttons"]) >= MAX_PANEL_BUTTONS:
            return await interaction.response.send_message(
                _status("zwarning", f"Discord allows at most {MAX_PANEL_BUTTONS} buttons per panel."),
                ephemeral=True,
            )
        emoji_name = ""
        if emoji_value:
            emoji_name = _emoji_name(emoji_value) or ""
            if not emoji_name:
                return await interaction.response.send_message(
                    _status(
                        "zcross",
                        "That emoji is not in the uploaded emoji database. "
                        "Upload it with `/upload emojis` first.",
                    ),
                    ephemeral=True,
                )
        self.setup_view.state["buttons"].append(
            {
                "key": f"b{len(self.setup_view.state['buttons']) + 1}",
                "label": label,
                "emoji": emoji_name,
                "role_id": None,
            }
        )
        await self.setup_view.refresh(
            interaction, _status("ztick", "Button added. Configure its role next.")
        )


class RREmbedModal(discord.ui.Modal):
    """Edit all five embed properties from one Discord modal."""

    def __init__(self, setup_view: "RRSetupView"):
        super().__init__(title="Edit reaction-role embed")
        self.setup_view = setup_view
        fields = (
            ("title", "Title", 256),
            ("description", "Description", 4000),
            ("image", "Image URL", 400),
            ("thumbnail", "Thumbnail URL", 400),
            ("color", "Hex colour", 7),
        )
        for key, label, max_length in fields:
            default = setup_view.state[key]
            if key == "color":
                default = f"#{setup_view.state['color']:06X}"
            self.add_item(
                discord.ui.TextInput(
                    label=label,
                    default=default or None,
                    required=False,
                    max_length=max_length,
                )
            )

    async def on_submit(self, interaction: discord.Interaction):
        values = [
            child.value.strip()
            for child in self.children
            if isinstance(child, discord.ui.TextInput)
        ]
        title, description, image, thumbnail, color_value = values
        color = _parse_color(color_value)
        if color is None:
            return await interaction.response.send_message(
                _status("zcross", "Use a six-digit hex colour such as #FFD700."),
                ephemeral=True,
            )
        self.setup_view.state.update(
            title=title, description=description, image=image,
            thumbnail=thumbnail, color=color,
        )
        await self.setup_view.refresh(interaction, _status("ztick", "Embed updated."))


class RRRoleAssignView(discord.ui.View):
    def __init__(self, setup_view: "RRSetupView", button_key: str):
        super().__init__(timeout=180)
        self.setup_view = setup_view
        self.button_key = button_key

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select the role for this button")
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        target = next(
            (button for button in self.setup_view.state["buttons"]
             if button["key"] == self.button_key),
            None,
        )
        if target is None:
            return await interaction.response.edit_message(
                content=_status("zcross", "That setup button no longer exists."),
                view=None,
            )
        target["role_id"] = role.id
        await interaction.response.edit_message(
            content=_status("ztick", f"Role selected: {role.mention}."),
            view=RRRoleSaveView(self.setup_view, self.button_key),
        )


class RRRoleSaveView(discord.ui.View):
    def __init__(self, setup_view: "RRSetupView", button_key: str):
        super().__init__(timeout=180)
        self.setup_view = setup_view
        self.button_key = button_key

    @discord.ui.button(label="Save role", style=discord.ButtonStyle.success)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=_status("ztick", "Role configured."), view=None)
        await self.setup_view.update_message()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=_status("zback", "Role configuration cancelled."), view=None)


class RRButtonSelect(discord.ui.Select):
    def __init__(self, setup_view: "RRSetupView"):
        self.setup_view = setup_view
        buttons = setup_view.state["buttons"]
        options = [
            discord.SelectOption(
                label=(button["label"] or button["emoji"])[:100],
                value=button["key"],
                description=(
                    f"Role: {button['role_id'] or 'not configured'}"
                )[:100],
            )
            for button in buttons
        ] or [discord.SelectOption(label="Add a button first", value="none")]
        super().__init__(
            placeholder="Choose a button to configure its role",
            options=options, disabled=not buttons, row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.defer()
        await interaction.response.send_message(
            _status("zvoice", "Select the role to assign to this button."),
            view=RRRoleAssignView(self.setup_view, self.values[0]),
            ephemeral=True,
        )


class RRDeleteSelect(discord.ui.Select):
    def __init__(self, setup_view: "RRSetupView"):
        self.setup_view = setup_view
        buttons = setup_view.state["buttons"]
        options = [
            discord.SelectOption(
                label=(button["label"] or button["emoji"])[:100],
                value=button["key"],
            )
            for button in buttons
        ] or [discord.SelectOption(label="No buttons to delete", value="none")]
        super().__init__(
            placeholder="Choose a button to delete",
            options=options, disabled=not buttons, row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        if key != "none":
            self.setup_view.state["buttons"] = [
                button for button in self.setup_view.state["buttons"]
                if button["key"] != key
            ]
        await self.setup_view.refresh(interaction, _status("ztick", "Button deleted."))


class RRSetupView(discord.ui.View):
    def __init__(self, cog: "ReactionRoles", interaction: discord.Interaction):
        super().__init__(timeout=900)
        self.cog = cog
        self.owner_id = interaction.user.id
        self.guild = interaction.guild
        self.channel_id: Optional[int] = None
        self.message: Optional[discord.Message] = None
        self.state = {
            "title": "",
            "description": "",
            "image": "",
            "thumbnail": "",
            "color": 0xFFD700,
            "multi": False,
            "buttons": [],
        }
        self._build()

    def _build(self):
        self.clear_items()
        # Discord allows five action rows.  Keep one row for each select and
        # use one modal for all embed fields so the whole builder fits.
        self.add_item(self._button("Edit embed", "edit_embed", discord.ButtonStyle.secondary, 0))
        self.add_item(self._button("Add button", "add_button", discord.ButtonStyle.primary, 0))
        self.add_item(self._button(
            f"Multi: {'On' if self.state['multi'] else 'Off'}",
            "toggle_multi", discord.ButtonStyle.success if self.state["multi"]
            else discord.ButtonStyle.secondary, 0,
        ))
        self.add_item(self._button("Send panel", "send_panel", discord.ButtonStyle.success, 0))
        self.add_item(self._button("Cancel", "cancel", discord.ButtonStyle.danger, 0))
        self.add_item(RRButtonSelect(self))
        self.add_item(RRDeleteSelect(self))
        self.add_item(RRChannelSelect(self))

    def _button(self, label: str, action: str, style: discord.ButtonStyle, row: int):
        button = discord.ui.Button(label=label, style=style, custom_id=f"rrsetup:{action}", row=row)
        button.callback = self._callback(action)
        return button

    def _callback(self, action: str):
        async def callback(interaction: discord.Interaction):
            if not await self._check_owner(interaction):
                return
            if action == "edit_embed":
                return await interaction.response.send_modal(RREmbedModal(self))
            if action == "add_button":
                return await interaction.response.send_modal(RRAddButtonModal(self))
            if action == "toggle_multi":
                self.state["multi"] = not self.state["multi"]
                return await self.refresh(interaction, _status("ztick", "Multi-select updated."))
            if action == "send_panel":
                return await self.send_panel(interaction)
            if action == "cancel":
                self.stop()
                return await interaction.response.edit_message(
                    content=_status("zback", "Reaction-role setup cancelled."), embed=None, view=None
                )
        return callback

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            _status("zcross", "Only the setup author can use this panel."),
            ephemeral=True,
        )
        return False

    async def update_message(self):
        if self.message:
            self._build()
            await self.message.edit(embed=_setup_embed(self.state), view=self)

    async def refresh(self, interaction: discord.Interaction, content: str = ""):
        self._build()
        await interaction.response.edit_message(
            content=content or None, embed=_setup_embed(self.state), view=self
        )

    async def send_panel(self, interaction: discord.Interaction):
        missing = [button for button in self.state["buttons"] if not button["role_id"]]
        if missing:
            return await interaction.response.send_message(
                _status("zwarning", "Configure a role for every button before sending."),
                ephemeral=True,
            )
        if self.channel_id is None:
            return await interaction.response.send_message(
                _status("zwarning", "Select a channel before sending the panel."),
                ephemeral=True,
            )
        channel = self.guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                _status("zcross", "That channel is no longer available."),
                ephemeral=True,
            )
        try:
            message = await channel.send(
                embed=_setup_embed(self.state),
                view=RRPublishedView(self.cog, self.state["buttons"]),
            )
            self.cog.db.save_panel(self.guild.id, channel.id, message, self.state)
            self.stop()
            await interaction.response.edit_message(
                content=_status("ztick", f"Reaction-role panel sent to {channel.mention}."),
                embed=None, view=None,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                _status("zcross", "I could not send the panel. Check my channel permissions."),
                ephemeral=True,
            )


class RRChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setup_view: RRSetupView):
        self.setup_view = setup_view
        super().__init__(
            placeholder="Select the channel where the panel will be sent",
            channel_types=[discord.ChannelType.text], row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        self.setup_view.channel_id = self.values[0].id
        await self.setup_view.refresh(
            interaction,
            _status("ztick", f"Channel selected: {self.values[0].mention}."),
        )


class RRPublishedView(discord.ui.View):
    """View used when first sending a panel; interaction handling is global."""

    def __init__(self, cog: "ReactionRoles", buttons: list[dict]):
        super().__init__(timeout=None)
        self.cog = cog
        for button in buttons:
            item = discord.ui.Button(
                label=button["label"] or None,
                emoji=_custom_emoji(button["emoji"]) if button["emoji"] else None,
                style=discord.ButtonStyle.secondary,
                custom_id=f"rr:{button['key']}",
            )
            item.callback = self._callback(button["key"])
            self.add_item(item)

    def _callback(self, button_key: str):
        async def callback(interaction: discord.Interaction):
            await self.cog.handle_role_interaction(interaction, button_key)
        return callback


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = ReactionRoleDB()

    def help_custom(self):
        return _icon("zpeople"), "Reaction Roles", "Create interactive role panels"

    async def cog_load(self):
        # Re-register published views after every restart.  The panel
        # definition is reconstructed from rr.db, so buttons remain usable
        # without storing Discord view objects.
        for _guild_id, message_id, _channel_id, _title, _description, _image, _thumbnail, _color, _multi in self.db.panels():
            buttons = [
                {"key": key, "label": label, "emoji": emoji, "role_id": role_id}
                for key, label, emoji, role_id in self.db.panel_buttons(message_id)
            ]
            if buttons:
                self.bot.add_view(RRPublishedView(self, buttons), message_id=message_id)

    @app_commands.command(name="setuprr", description="Build and publish a reaction-role panel.")
    @app_commands.default_permissions(manage_roles=True, manage_guild=True)
    async def setuprr(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message(
                _status("zcross", "This command can only be used in a server."),
                ephemeral=True,
            )
        view = RRSetupView(self, interaction)
        await interaction.response.send_message(
            _status("zmodule", "Configure your reaction-role panel below."),
            embed=_setup_embed(view.state),
            view=view,
        )
        view.message = await interaction.original_response()

    @app_commands.command(name="dmrr", description="Enable or disable reaction-role private messages.")
    @app_commands.describe(mode="Enable or disable success messages")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable"),
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def dmrr(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        self.db.set_dm_setting(interaction.guild.id, mode.value == "enable")
        await interaction.response.send_message(
            _status("ztick", f"Reaction-role private messages {mode.value}d."),
            ephemeral=True,
        )

    async def handle_role_interaction(
        self, interaction: discord.Interaction, button_key: str
    ):
        if interaction.guild is None or not interaction.message:
            return
        record = self.db.panel_button(interaction.message.id, button_key)
        if not record:
            return
        (
            guild_id, _channel_id, _title, _description, _image,
            _thumbnail, _color, multi, _label, _emoji, role_id,
        ) = record
        member = interaction.guild.get_member(interaction.user.id)
        role = interaction.guild.get_role(role_id)
        if member is None or role is None:
            return await interaction.response.send_message(
                _status("zcross", "The configured role is no longer available."),
                ephemeral=True,
            )
        try:
            buttons = self.db.panel_buttons(interaction.message.id)
            panel_role_ids = {row[3] for row in buttons}
            has_role = role in member.roles
            if has_role:
                await member.remove_roles(role, reason="Reaction-role toggle")
                result = _status("zback", f"Removed {role.mention} from you.")
            else:
                if not multi:
                    for other_role_id in panel_role_ids - {role.id}:
                        other_role = interaction.guild.get_role(other_role_id)
                        if other_role and other_role in member.roles:
                            await member.remove_roles(other_role, reason="Reaction-role single-select")
                await member.add_roles(role, reason="Reaction-role selected")
                result = _status("ztick", f"Added {role.mention} to you.")
            await interaction.response.send_message(result, ephemeral=True)
        except (discord.Forbidden, discord.HTTPException):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    _status("zcross", "I could not update that role. Check role hierarchy and permissions."),
                    ephemeral=True,
                )


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))