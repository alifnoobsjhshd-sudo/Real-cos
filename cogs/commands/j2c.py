import re
import discord
from discord.ext import commands
from discord import ui, SelectOption
import aiosqlite
import asyncio
from typing import Dict, List, Optional
from utils.emojis import e


def _make_emoji(key: str, fallback: str) -> discord.PartialEmoji:
    """Return a PartialEmoji from an e() key, falling back to unicode."""
    raw = e(key) or fallback
    m = re.match(r'<(a?):(\w+):(\d+)>', raw)
    if m:
        return discord.PartialEmoji(
            animated=bool(m.group(1)), name=m.group(2), id=int(m.group(3))
        )
    return discord.PartialEmoji(name=raw)


# Map button custom_id → (emoji_key, unicode_fallback)
_CTRL_EMOJI: dict[str, tuple[str, str]] = {
    "j2c:limit":    ("ztimer",       "⏳"),
    "j2c:privacy":  ("lock",         "🔒"),
    "j2c:thread":   ("zmsg",         "💬"),
    "j2c:untrust":  ("zcross",       "❌"),
    "j2c:invite":   ("zplus",        "✉️"),
    "j2c:kick":     ("zban",         "👢"),
    "j2c:region":   ("zyrox_global", "🌍"),
    "j2c:unblock":  ("unlock",       "🔓"),
    "j2c:claim":    ("BlackCrown",   "⭐"),
    "j2c:transfer": ("zArrow",       "🔄"),
    "j2c:delete":   ("delete",       "🗑️"),
    "j2c:rename":   ("zsettings",    "✏️"),
    "j2c:block":    ("Denied",       "🚫"),
}


class JoinToCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.private_channels: Dict[int, Dict] = {}
        self.category_name = "J2C"
        self.setup_data: Dict[int, Dict] = {}
        self.db_path = "j2c_data.db"
        self.blocked_users: Dict[int, List[int]] = {}

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_setup (
                    guild_id INTEGER PRIMARY KEY,
                    join_channel_id INTEGER,
                    control_channel_id INTEGER,
                    control_message_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS private_channels (
                    vc_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    owner_id INTEGER,
                    member_limit INTEGER DEFAULT 99,
                    region TEXT DEFAULT '',
                    is_locked BOOLEAN DEFAULT FALSE,
                    has_waiting_room BOOLEAN DEFAULT FALSE,
                    has_thread BOOLEAN DEFAULT FALSE,
                    ctrl_msg_id INTEGER DEFAULT NULL
                )
            """)
            try:
                await db.execute("ALTER TABLE private_channels ADD COLUMN ctrl_msg_id INTEGER DEFAULT NULL")
            except Exception:
                pass
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    vc_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (vc_id, user_id)
                )
            """)
            await db.commit()

    async def load_data(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM guild_setup") as cursor:
                async for row in cursor:
                    guild_id, join_channel_id, control_channel_id, control_message_id = row
                    self.setup_data[guild_id] = {
                        "join_channel_id": join_channel_id,
                        "control_channel_id": control_channel_id,
                        "control_message_id": control_message_id
                    }

            async with db.execute(
                "SELECT vc_id, guild_id, owner_id, member_limit, region, "
                "is_locked, has_waiting_room, has_thread, ctrl_msg_id FROM private_channels"
            ) as cursor:
                async for row in cursor:
                    vc_id, guild_id, owner_id, member_limit, region, \
                        is_locked, has_waiting_room, has_thread, ctrl_msg_id = row
                    self.private_channels[vc_id] = {
                        "owner": owner_id,
                        "limit": member_limit,
                        "region": region,
                        "is_locked": bool(is_locked),
                        "has_waiting_room": bool(has_waiting_room),
                        "has_thread": bool(has_thread),
                        "guild_id": guild_id,
                        "ctrl_msg_id": ctrl_msg_id
                    }

            async with db.execute("SELECT * FROM blocked_users") as cursor:
                async for row in cursor:
                    vc_id, user_id = row
                    if vc_id not in self.blocked_users:
                        self.blocked_users[vc_id] = []
                    self.blocked_users[vc_id].append(user_id)

    async def save_guild_setup(self, guild_id: int, data: Dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO guild_setup
                (guild_id, join_channel_id, control_channel_id, control_message_id)
                VALUES (?, ?, ?, ?)
            """, (guild_id, data["join_channel_id"], data["control_channel_id"], data["control_message_id"]))
            await db.commit()

    async def save_private_channel(self, vc_id: int, guild_id: int, data: Dict):
        try:
            if vc_id not in self.private_channels:
                self.private_channels[vc_id] = data
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO private_channels
                    (vc_id, guild_id, owner_id, member_limit, region,
                     is_locked, has_waiting_room, has_thread, ctrl_msg_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vc_id, guild_id,
                    data["owner"],
                    data.get("limit", 99),
                    data.get("region", ""),
                    data.get("is_locked", False),
                    data.get("has_waiting_room", False),
                    data.get("has_thread", False),
                    data.get("ctrl_msg_id", None)
                ))
                await db.commit()
        except Exception as err:
            print(f"Error saving private channel: {err}")

    async def delete_private_channel(self, vc_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM private_channels WHERE vc_id = ?", (vc_id,))
            await db.execute("DELETE FROM blocked_users WHERE vc_id = ?", (vc_id,))
            await db.commit()

    async def delete_guild_setup(self, guild_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM guild_setup WHERE guild_id = ?", (guild_id,))
            await db.execute("DELETE FROM private_channels WHERE guild_id = ?", (guild_id,))
            await db.execute(
                "DELETE FROM blocked_users WHERE vc_id IN "
                "(SELECT vc_id FROM private_channels WHERE guild_id = ?)", (guild_id,)
            )
            await db.commit()

    async def block_user(self, vc_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO blocked_users (vc_id, user_id) VALUES (?, ?)", (vc_id, user_id)
            )
            await db.commit()
        if vc_id not in self.blocked_users:
            self.blocked_users[vc_id] = []
        if user_id not in self.blocked_users[vc_id]:
            self.blocked_users[vc_id].append(user_id)

    async def unblock_user(self, vc_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM blocked_users WHERE vc_id = ? AND user_id = ?", (vc_id, user_id)
            )
            await db.commit()
        if vc_id in self.blocked_users and user_id in self.blocked_users[vc_id]:
            self.blocked_users[vc_id].remove(user_id)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.init_db()
        await self.load_data()

    # ── Embeds ────────────────────────────────────────────────────────────────

    def _em(self, key: str, fallback: str) -> str:
        """Return the emoji string for a key, falling back to unicode."""
        val = e(key)
        return val if val else fallback

    async def create_vc_control_embed(
        self, vc: discord.VoiceChannel, owner: discord.Member
    ) -> discord.Embed:
        """
        Async embed for the control panel posted inside the private VC.
        Shows owner/status info + the same button guide as the interface channel,
        with the branding banner at the bottom.
        """
        from utils.branding import get_branding, DEFAULT_BRANDING
        branding = await get_branding(vc.guild.id)

        vc_data = self.private_channels.get(vc.id, {})
        is_locked = vc_data.get("is_locked", False)
        has_wr    = vc_data.get("has_waiting_room", False)
        has_th    = vc_data.get("has_thread", False)
        limit     = vc_data.get("limit", 99)

        em = self._em  # shortcut

        # Status line
        status_parts = [
            f"{em('lock','🔒') if is_locked else em('unlock','🔓')} {'Locked' if is_locked else 'Unlocked'}",
            f"{'💬 Thread: On' if has_th else ''}",
            f"{em('ztimer','⏳')} Limit: {limit if limit else '∞'}",
        ]
        status_line = " │ ".join(p for p in status_parts if p)

        # Button guide lines (matches interface embed)
        guide_lines = [
            f"{em('zsettings','⚙️')} **(Rename)** — rename your channel",
            f"{em('ztimer','⏳')} **(Limit)** — change member limit",
            f"{em('lock','🔒')} **(Privacy)** — lock / unlock your VC",
            f"{em('zmsg','💬')} **(Thread)** — create a discussion thread",
            f"{em('zcross','❌')} **(Untrust)** — remove a member's access",
            f"{em('zplus','✉️')} **(Invite)** — send a DM invite",
            f"{em('zban','👢')} **(Kick)** — disconnect a member",
            f"{em('zyrox_global','🌍')} **(Region)** — change voice region",
            f"{em('Denied','🚫')} **(Block)** — block a member from joining",
            f"{em('unlock','🔓')} **(Unblock)** — unblock a member",
            f"{em('BlackCrown','⭐')} **(Claim)** — claim an abandoned VC",
            f"{em('zArrow','🔄')} **(Transfer)** — transfer ownership",
            f"{em('delete','🗑️')} **(Delete)** — permanently delete the VC",
        ]

        embed = discord.Embed(
            description=(
                f"👑 **Owner:** {owner.mention} │ 🔊 **Channel:** {vc.mention}\n"
                f"{status_line}\n\n"
                f"**__Ctrl Panel__**\n"
                + "\n".join(guide_lines)
            ),
            color=branding.get("embed_color", 0xFF0000)
        )

        banner = branding.get("embed_banner")
        if banner:
            embed.set_image(url=banner)

        branding_name = branding.get("branding_name", DEFAULT_BRANDING)
        embed.set_footer(text=f"{branding_name} • J2C Control Panel")
        return embed

    async def create_interface_embed(
        self, guild: discord.Guild, join_channel: discord.VoiceChannel
    ) -> discord.Embed:
        """Branded static embed for the #interface channel — no buttons."""
        from utils.branding import get_branding
        branding = await get_branding(guild.id)

        em = self._em

        lines = [
            f"{em('zsettings','⚙️')} **— (Rename)** your channel",
            f"{em('ztimer','⏳')} **— (Limit)** your channel members",
            f"{em('lock','🔒')} **— (Lock)** your channel",
            f"{em('zmsg','💬')} **— (Thread)** create a discussion thread",
            f"{em('zcross','❌')} **— (Untrust)** remove a member's access",
            f"{em('zplus','✉️')} **— (Invite)** a member to your channel",
            f"{em('zban','👢')} **— (Kick)** a member from your vc",
            f"{em('zyrox_global','🌍')} **— (Region)** change your vc region",
            f"{em('Denied','🚫')} **— (Block)** a member from joining",
            f"{em('unlock','🔓')} **— (Unblock)** a blocked member",
            f"{em('BlackCrown','⭐')} **— (Claim)** an abandoned vc",
            f"{em('zArrow','🔄')} **— (Transfer)** ownership to someone",
            f"{em('delete','🗑️')} **— (Delete)** your channel",
        ]

        embed = discord.Embed(
            description=(
                f"Go on {join_channel.mention} to create a vc channel.\n\n"
                f"**__Ctrl Panel__**\n"
                + "\n".join(lines)
            ),
            color=branding.get("embed_color", 0xFFD700)
        )

        banner = branding.get("embed_banner")
        if banner:
            embed.set_image(url=banner)

        branding_name = branding.get("branding_name", "CodeX")
        embed.set_footer(text=f"{branding_name} • J2C System")
        return embed

    def create_info_embed(self, guild: discord.Guild) -> discord.Embed:
        """Legacy fallback embed — kept for backward compatibility."""
        embed = discord.Embed(
            title="⚙️ J2C System",
            description=(
                "Join the **➕ Join to Create** voice channel to get your own private VC.\n"
                "A control panel will appear inside your new channel."
            ),
            color=0xFFD700
        )
        return embed

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(name='j2csetup')
    @commands.has_permissions(administrator=True)
    async def setup_private_channels(self, ctx):
        if ctx.guild.id in self.setup_data:
            await ctx.send("J2C system is already setup in this server!")
            return

        category = discord.utils.get(ctx.guild.categories, name=self.category_name)
        if not category:
            category = await ctx.guild.create_category(self.category_name)

        join_channel = await ctx.guild.create_voice_channel(
            "➕ Join to Create",
            category=category,
            reason="J2C System Setup"
        )

        # Interface channel — read-only for members, shows the button guide
        interface_channel = await ctx.guild.create_text_channel(
            "interface",
            category=category,
            reason="J2C System Setup"
        )
        try:
            await interface_channel.set_permissions(
                ctx.guild.default_role,
                send_messages=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
                reason="J2C interface is read-only"
            )
        except Exception:
            pass

        embed = await self.create_interface_embed(ctx.guild, join_channel)
        info_message = await interface_channel.send(embed=embed)

        self.setup_data[ctx.guild.id] = {
            "join_channel_id": join_channel.id,
            "control_channel_id": interface_channel.id,
            "control_message_id": info_message.id
        }
        await self.save_guild_setup(ctx.guild.id, self.setup_data[ctx.guild.id])

        from utils.emojis import e as _e
        await ctx.send(
            f"{_e('zsettings')} J2C system setup complete! Join {join_channel.mention} to create a private VC."
        )

    @commands.command(name='j2creset')
    @commands.has_permissions(administrator=True)
    async def reset_private_channels(self, ctx):
        if ctx.guild.id not in self.setup_data:
            await ctx.send("J2C system is not setup in this server!")
            return

        category = discord.utils.get(ctx.guild.categories, name=self.category_name)
        if category:
            for channel in category.channels:
                try:
                    await channel.delete(reason="J2C System Reset")
                except Exception:
                    continue
            try:
                await category.delete(reason="J2C System Reset")
            except Exception:
                pass

        vc_ids = [
            vc_id for vc_id, data in self.private_channels.items()
            if data.get("guild_id") == ctx.guild.id
        ]
        for vc_id in vc_ids:
            del self.private_channels[vc_id]

        del self.setup_data[ctx.guild.id]
        await self.delete_guild_setup(ctx.guild.id)

        await ctx.send("J2C system has been completely reset in this server!")

    # ── Voice events ──────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.guild.id not in self.setup_data:
            return

        guild_data = self.setup_data[member.guild.id]

        # Member joins the trigger VC → create a private VC
        if after.channel and after.channel.id == guild_data["join_channel_id"]:
            category = discord.utils.get(member.guild.categories, name=self.category_name)
            if not category:
                return

            vc = await member.guild.create_voice_channel(
                f"{member.name}'s VC",
                category=category,
                reason="Private VC Creation",
                user_limit=99
            )
            await member.move_to(vc)

            self.private_channels[vc.id] = {
                "owner": member.id,
                "limit": 99,
                "region": "",
                "is_locked": False,
                "has_waiting_room": False,
                "has_thread": False,
                "guild_id": member.guild.id,
                "ctrl_msg_id": None
            }
            await self.save_private_channel(vc.id, member.guild.id, self.private_channels[vc.id])

            try:
                embed = await self.create_vc_control_embed(vc, member)
                view = ControlPanelView(self)
                ctrl_msg = await vc.send(embed=embed, view=view)
                self.private_channels[vc.id]["ctrl_msg_id"] = ctrl_msg.id
                await self.save_private_channel(vc.id, member.guild.id, self.private_channels[vc.id])
            except Exception as err:
                print(f"Could not send J2C control panel to VC: {err}")

            await self.update_info_panel(member.guild)

        # Member leaves a private VC
        if before.channel and before.channel.id in self.private_channels:
            if (
                before.channel.id in self.blocked_users
                and member.id in self.blocked_users[before.channel.id]
            ):
                await member.move_to(None)
                return

            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                except Exception:
                    pass

                if before.channel.id in self.private_channels:
                    del self.private_channels[before.channel.id]
                    await self.delete_private_channel(before.channel.id)

                await self.update_info_panel(member.guild)

    async def update_info_panel(self, guild: discord.Guild):
        """Refresh the static interface embed (e.g. after branding changes)."""
        if guild.id not in self.setup_data:
            return
        guild_data = self.setup_data[guild.id]
        interface_channel = guild.get_channel(guild_data["control_channel_id"])
        if not interface_channel or not guild_data["control_message_id"]:
            return
        join_channel = guild.get_channel(guild_data["join_channel_id"])
        if not join_channel:
            return
        try:
            msg = await interface_channel.fetch_message(guild_data["control_message_id"])
            embed = await self.create_interface_embed(guild, join_channel)
            await msg.edit(embed=embed)
        except Exception:
            pass

    async def update_vc_panel(self, vc: discord.VoiceChannel, guild: discord.Guild):
        """Refresh the control panel inside the private VC."""
        vc_data = self.private_channels.get(vc.id)
        if not vc_data:
            return
        ctrl_msg_id = vc_data.get("ctrl_msg_id")
        if not ctrl_msg_id:
            return
        owner = guild.get_member(vc_data["owner"])
        if not owner:
            return
        try:
            msg = await vc.fetch_message(ctrl_msg_id)
            embed = await self.create_vc_control_embed(vc, owner)
            view = ControlPanelView(self)
            await msg.edit(embed=embed, view=view)
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
# CONTROL PANEL VIEW
# ═════════════════════════════════════════════════════════════════════════════

class ControlPanelView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        # Apply custom emojis to all buttons at runtime
        for child in self.children:
            cid = getattr(child, "custom_id", None)
            if cid and cid in _CTRL_EMOJI:
                key, fallback = _CTRL_EMOJI[cid]
                child.emoji = _make_emoji(key, fallback)

    async def get_owned_vc(self, interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        for vc_id, data in self.cog.private_channels.items():
            if data["owner"] == interaction.user.id:
                vc = interaction.guild.get_channel(vc_id)
                if vc:
                    return vc
        return None

    @ui.button(label="LIMIT", style=discord.ButtonStyle.secondary, row=0, custom_id="j2c:limit", emoji="⏳")
    async def set_limit(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        modal = SetLimitModal(vc)
        await interaction.response.send_modal(modal)

    @ui.button(label="PRIVACY", style=discord.ButtonStyle.secondary, row=0, custom_id="j2c:privacy", emoji="🔒")
    async def toggle_privacy(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        is_locked = not self.cog.private_channels[vc.id]["is_locked"]
        await vc.set_permissions(interaction.guild.default_role, connect=not is_locked)
        self.cog.private_channels[vc.id]["is_locked"] = is_locked
        await self.cog.save_private_channel(vc.id, interaction.guild.id, self.cog.private_channels[vc.id])
        from utils.emojis import e as _e
        await interaction.response.send_message(
            f"VC is now {(_e('lock') + ' locked') if is_locked else (_e('unlock') + ' unlocked')}!", ephemeral=True
        )
        await self.cog.update_vc_panel(vc, interaction.guild)

    @ui.button(label="THREAD", style=discord.ButtonStyle.secondary, row=0, custom_id="j2c:thread", emoji="💬")
    async def create_thread(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        has_thread = not self.cog.private_channels[vc.id]["has_thread"]
        self.cog.private_channels[vc.id]["has_thread"] = has_thread
        await self.cog.save_private_channel(vc.id, interaction.guild.id, self.cog.private_channels[vc.id])
        if has_thread:
            try:
                thread = await interaction.channel.create_thread(
                    name=f"{vc.name} Discussion", auto_archive_duration=60
                )
                await interaction.response.send_message(
                    f"Created thread: {thread.mention}", ephemeral=True
                )
            except Exception:
                await interaction.response.send_message("Thread feature enabled!", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Thread feature disabled for your VC", ephemeral=True
            )
        await self.cog.update_vc_panel(vc, interaction.guild)

    @ui.button(label="UNTRUST", style=discord.ButtonStyle.secondary, row=1, custom_id="j2c:untrust", emoji="❌")
    async def untrust(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        options = [
            SelectOption(label=member.name, value=str(member.id))
            for member in vc.members
            if member.id != interaction.user.id
        ]
        if not options:
            await interaction.response.send_message("No trusted users to remove!", ephemeral=True)
            return
        dropdown = UserSelectDropdown(options, "Select members to untrust", self.untrust_selected)
        view = ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message("Select members to untrust:", view=view, ephemeral=True)

    async def untrust_selected(self, interaction: discord.Interaction, selected: List[str]):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            return
        for user_id in selected:
            member = interaction.guild.get_member(int(user_id))
            if member:
                try:
                    await vc.set_permissions(member, overwrite=None)
                except Exception:
                    pass
        await interaction.response.send_message("Selected members untrusted!", ephemeral=True)

    @ui.button(label="INVITE", style=discord.ButtonStyle.secondary, row=1, custom_id="j2c:invite", emoji="✉️")
    async def invite_user(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        options = [
            SelectOption(label=member.name, value=str(member.id))
            for member in interaction.guild.members
            if member not in vc.members and not member.bot and member != interaction.user
        ]
        if not options:
            await interaction.response.send_message("No members available to invite!", ephemeral=True)
            return
        dropdown = UserSelectDropdown(options, "Select members to invite", self.invite_selected)
        view = ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message("Select members to invite:", view=view, ephemeral=True)

    async def invite_selected(self, interaction: discord.Interaction, selected: List[str]):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            return
        for user_id in selected:
            member = interaction.guild.get_member(int(user_id))
            if member:
                try:
                    await member.send(
                        f"You've been invited to join {vc.mention} by {interaction.user.mention}!"
                    )
                except Exception:
                    pass
        await interaction.response.send_message("Invites sent!", ephemeral=True)

    @ui.button(label="KICK", style=discord.ButtonStyle.secondary, row=1, custom_id="j2c:kick", emoji="👢")
    async def kick_user(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        options = [
            SelectOption(label=member.name, value=str(member.id))
            for member in vc.members
            if member.id != interaction.user.id
        ]
        if not options:
            await interaction.response.send_message("No users to kick in your VC!", ephemeral=True)
            return
        dropdown = UserSelectDropdown(options, "Select members to kick", self.kick_selected)
        view = ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message("Select members to kick:", view=view, ephemeral=True)

    async def kick_selected(self, interaction: discord.Interaction, selected: List[str]):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            return
        for user_id in selected:
            member = interaction.guild.get_member(int(user_id))
            if member and member in vc.members:
                try:
                    await member.move_to(None)
                except Exception:
                    pass
        await interaction.response.send_message("Selected members kicked!", ephemeral=True)

    @ui.button(label="REGION", style=discord.ButtonStyle.secondary, row=1, custom_id="j2c:region", emoji="🌍")
    async def set_region(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        regions = [
            SelectOption(label="Automatic", value="auto"),
            SelectOption(label="US West",   value="us-west"),
            SelectOption(label="US East",   value="us-east"),
            SelectOption(label="Europe",    value="europe"),
            SelectOption(label="Singapore", value="singapore"),
            SelectOption(label="Japan",     value="japan"),
            SelectOption(label="Brazil",    value="brazil"),
            SelectOption(label="Australia", value="australia")
        ]
        dropdown = RegionSelectDropdown(regions, vc)
        view = ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message("Select a region:", view=view, ephemeral=True)

    @ui.button(label="UNBLOCK", style=discord.ButtonStyle.secondary, row=2, custom_id="j2c:unblock", emoji="🔓")
    async def unblock(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        if vc.id not in self.cog.blocked_users or not self.cog.blocked_users[vc.id]:
            await interaction.response.send_message("No blocked users!", ephemeral=True)
            return
        options = []
        for user_id in self.cog.blocked_users[vc.id]:
            member = interaction.guild.get_member(user_id)
            if member:
                options.append(SelectOption(label=member.name, value=str(user_id)))
        if not options:
            await interaction.response.send_message("No blocked users found in server!", ephemeral=True)
            return
        dropdown = UserSelectDropdown(options, "Select users to unblock", self.unblock_selected)
        view = ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message("Select users to unblock:", view=view, ephemeral=True)

    async def unblock_selected(self, interaction: discord.Interaction, selected: List[str]):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            return
        for user_id in selected:
            await self.cog.unblock_user(vc.id, int(user_id))
        await interaction.response.send_message("Selected users unblocked!", ephemeral=True)
        await self.cog.update_vc_panel(vc, interaction.guild)

    @ui.button(label="CLAIM", style=discord.ButtonStyle.secondary, row=2, custom_id="j2c:claim", emoji="⭐")
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
        available_vcs = []
        for vc_id, data in self.cog.private_channels.items():
            if data["guild_id"] == interaction.guild.id:
                vc = interaction.guild.get_channel(vc_id)
                if vc:
                    owner = interaction.guild.get_member(data["owner"])
                    if not owner or owner not in vc.members:
                        available_vcs.append((vc, data))
        if not available_vcs:
            await interaction.response.send_message("No VCs available to claim!", ephemeral=True)
            return
        options = [
            SelectOption(label=vc.name, value=str(vc.id))
            for vc, data in available_vcs
        ]
        dropdown = VCSelectDropdown(options, "Select VC to claim", self.claim_selected)
        view = ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message("Select VC to claim:", view=view, ephemeral=True)

    async def claim_selected(self, interaction: discord.Interaction, selected: List[str]):
        vc_id = int(selected[0])
        vc = interaction.guild.get_channel(vc_id)
        if not vc:
            await interaction.response.send_message("VC no longer exists!", ephemeral=True)
            return
        self.cog.private_channels[vc.id]["owner"] = interaction.user.id
        await self.cog.save_private_channel(vc.id, interaction.guild.id, self.cog.private_channels[vc.id])
        await interaction.response.send_message(f"You've claimed {vc.mention}!", ephemeral=True)
        await self.cog.update_vc_panel(vc, interaction.guild)

    @ui.button(label="TRANSFER", style=discord.ButtonStyle.secondary, row=2, custom_id="j2c:transfer", emoji="🔄")
    async def transfer(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        options = [
            SelectOption(label=member.name, value=str(member.id))
            for member in vc.members
            if member.id != interaction.user.id
        ]
        if not options:
            await interaction.response.send_message("No users to transfer to!", ephemeral=True)
            return
        dropdown = UserSelectDropdown(options, "Select new owner", self.transfer_selected)
        view = ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message("Select new owner:", view=view, ephemeral=True)

    async def transfer_selected(self, interaction: discord.Interaction, selected: List[str]):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            return
        new_owner_id = int(selected[0])
        new_owner = interaction.guild.get_member(new_owner_id)
        if not new_owner:
            await interaction.response.send_message("User not found!", ephemeral=True)
            return
        self.cog.private_channels[vc.id]["owner"] = new_owner_id
        await self.cog.save_private_channel(vc.id, interaction.guild.id, self.cog.private_channels[vc.id])
        await interaction.response.send_message(
            f"Transferred ownership of {vc.mention} to {new_owner.mention}!", ephemeral=True
        )
        await self.cog.update_vc_panel(vc, interaction.guild)

    @ui.button(label="DELETE", style=discord.ButtonStyle.secondary, row=2, custom_id="j2c:delete", emoji="🗑️")
    async def delete_vc(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        for member in vc.members:
            try:
                await member.move_to(None)
            except Exception:
                pass
        await vc.delete()
        if vc.id in self.cog.private_channels:
            del self.cog.private_channels[vc.id]
            await self.cog.delete_private_channel(vc.id)
        await interaction.response.send_message("Your private VC has been deleted!", ephemeral=True)

    @ui.button(label="RENAME", style=discord.ButtonStyle.secondary, row=3, custom_id="j2c:rename", emoji="✏️")
    async def rename_vc(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        modal = RenameVCModal(vc, self.cog)
        await interaction.response.send_modal(modal)

    @ui.button(label="BLOCK", style=discord.ButtonStyle.secondary, row=3, custom_id="j2c:block", emoji="🚫")
    async def block(self, interaction: discord.Interaction, button: ui.Button):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            await interaction.response.send_message("You don't own any private VC!", ephemeral=True)
            return
        options = [
            SelectOption(label=member.name, value=str(member.id))
            for member in interaction.guild.members
            if member not in vc.members and not member.bot and member != interaction.user
        ]
        if not options:
            await interaction.response.send_message("No members available to block!", ephemeral=True)
            return
        dropdown = UserSelectDropdown(options, "Select members to block", self.block_selected)
        view = ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message("Select members to block:", view=view, ephemeral=True)

    async def block_selected(self, interaction: discord.Interaction, selected: List[str]):
        vc = await self.get_owned_vc(interaction)
        if not vc:
            return
        for user_id in selected:
            await self.cog.block_user(vc.id, int(user_id))
        await interaction.response.send_message(
            "Selected members blocked from joining!", ephemeral=True
        )
        await self.cog.update_vc_panel(vc, interaction.guild)


# ═════════════════════════════════════════════════════════════════════════════
# SELECT / MODAL HELPERS
# ═════════════════════════════════════════════════════════════════════════════

class UserSelectDropdown(ui.Select):
    def __init__(self, options: List[SelectOption], placeholder: str, callback):
        super().__init__(
            placeholder=placeholder,
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=min(len(options), 25)
        )
        self.callback_func = callback

    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(interaction, self.values)


class RegionSelectDropdown(ui.Select):
    def __init__(self, options: List[SelectOption], vc: discord.VoiceChannel):
        super().__init__(placeholder="Select a region", options=options)
        self.vc = vc

    async def callback(self, interaction: discord.Interaction):
        region = self.values[0]
        try:
            await self.vc.edit(rtc_region=region if region != "auto" else None)
            await interaction.response.send_message(f"Region set to **{self.values[0]}**!", ephemeral=True)
        except Exception as err:
            await interaction.response.send_message(f"Failed to set region: {err}", ephemeral=True)


class VCSelectDropdown(ui.Select):
    def __init__(self, options: List[SelectOption], placeholder: str, callback):
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)
        self.callback_func = callback

    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(interaction, self.values)


class SetLimitModal(ui.Modal, title="Set VC User Limit"):
    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc
        self.limit = ui.TextInput(
            label="User Limit (0 for no limit)",
            placeholder="Enter a number between 0 and 99",
            default=str(vc.user_limit) if vc.user_limit else "0",
            max_length=2
        )
        self.add_item(self.limit)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit.value)
            if limit < 0 or limit > 99:
                raise ValueError
            await self.vc.edit(user_limit=limit if limit != 0 else None)
            cog = interaction.client.get_cog("JoinToCreate")
            if cog and self.vc.id in cog.private_channels:
                cog.private_channels[self.vc.id]["limit"] = limit
                await cog.save_private_channel(
                    self.vc.id, interaction.guild.id, cog.private_channels[self.vc.id]
                )
                await cog.update_vc_panel(self.vc, interaction.guild)
            await interaction.response.send_message(
                f"User limit set to **{limit if limit != 0 else 'no limit'}**!", ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                "Invalid limit! Please enter a number between 0 and 99.", ephemeral=True
            )


class RenameVCModal(ui.Modal, title="Rename Your VC"):
    def __init__(self, vc: discord.VoiceChannel, cog):
        super().__init__()
        self.vc = vc
        self.cog = cog
        self.new_name = ui.TextInput(
            label="New Channel Name",
            placeholder="Enter a new name for your VC",
            default=vc.name,
            max_length=100,
            min_length=1
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_name = self.new_name.value.strip()
            await self.vc.edit(name=new_name)
            await interaction.response.send_message(
                f"✏️ Channel renamed to **{new_name}**!", ephemeral=True
            )
            await self.cog.update_vc_panel(self.vc, interaction.guild)
        except Exception as err:
            await interaction.response.send_message(
                f"Failed to rename channel: {err}", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(JoinToCreate(bot))
