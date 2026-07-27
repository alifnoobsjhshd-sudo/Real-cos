import os
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from core.Cog import Cog
from core.zyrox import zyrox
from utils.branding import (
    get_branding, set_branding, reset_branding,
    get_global_branding, set_global_branding,
    get_guild_profile, set_guild_profile,
    get_fun_prefix, set_fun_prefix,
    parse_color, color_to_hex,
    DEFAULT_BRANDING, DEFAULT_COLOR, DEFAULT_FUN_PREFIX,
)
from utils.Tools import ignore_check, blacklist_check


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def get_ctrl_guild_ids():
    """Read control guild IDs from secrets ctrl_guild_id_1, ctrl_guild_id_2 …"""
    guilds = []
    i = 1
    while True:
        val = os.getenv(f"ctrl_guild_id_{i}")
        if val is None:
            break
        try:
            guilds.append(int(val.strip()))
        except ValueError:
            pass
        i += 1
    return guilds


# ─────────────────────────────────────────────
#  Modals – per-guild branding
# ─────────────────────────────────────────────

class BrandingNameModal(discord.ui.Modal, title="Change Branding Name"):
    name_input = discord.ui.TextInput(
        label="Branding Name",
        placeholder="e.g. MyBot, GuardBot, ServerGuard",
        max_length=32,
        required=True,
    )

    def __init__(self, guild_id: int, appearance_view):
        super().__init__()
        self.guild_id = guild_id
        self.appearance_view = appearance_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.name_input.value.strip()
        await set_branding(self.guild_id, branding_name=value)
        self.appearance_view.branding_name = value
        embed = self.appearance_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.appearance_view)


class EmbedColorModal(discord.ui.Modal, title="Change Embed Color"):
    color_input = discord.ui.TextInput(
        label="Hex Color",
        placeholder="e.g. FFD700 or #FFD700",
        max_length=10,
        required=True,
    )

    def __init__(self, guild_id: int, appearance_view):
        super().__init__()
        self.guild_id = guild_id
        self.appearance_view = appearance_view

    async def on_submit(self, interaction: discord.Interaction):
        parsed = parse_color(self.color_input.value)
        if parsed is None:
            await interaction.response.send_message(
                "❌ Invalid hex color. Example: `FFD700` or `#FFD700`.",
                ephemeral=True,
            )
            return
        await set_branding(self.guild_id, embed_color=parsed)
        self.appearance_view.embed_color = parsed
        embed = self.appearance_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.appearance_view)


class EmbedThumbnailModal(discord.ui.Modal, title="Change Embed Thumbnail"):
    url_input = discord.ui.TextInput(
        label="Image URL (leave blank to remove)",
        placeholder="https://example.com/image.png",
        max_length=512,
        required=False,
    )

    def __init__(self, guild_id: int, appearance_view):
        super().__init__()
        self.guild_id = guild_id
        self.appearance_view = appearance_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.url_input.value.strip() or None
        await set_branding(self.guild_id, embed_thumbnail=value)
        self.appearance_view.embed_thumbnail = value
        embed = self.appearance_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.appearance_view)


class FunPrefixModal(discord.ui.Modal, title="Change Fun Prefix"):
    prefix_input = discord.ui.TextInput(
        label="Fun Prefix (1–3 letters, e.g. sun, cos, fun)",
        placeholder="sun",
        max_length=3,
        min_length=1,
        required=True,
    )

    def __init__(self, guild_id: int, appearance_view):
        super().__init__()
        self.guild_id = guild_id
        self.appearance_view = appearance_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.prefix_input.value.strip().lower()
        if len(value) > 3 or not value.isalpha():
            await interaction.response.send_message(
                "❌ Invalid prefix — must be 1–3 letters only (no numbers or symbols).",
                ephemeral=True,
            )
            return
        try:
            await set_fun_prefix(self.guild_id, value)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Could not save fun prefix: {e}", ephemeral=True
            )
            return
        self.appearance_view.fun_prefix = value
        embed = self.appearance_view.build_embed()
        # edit_message() on a modal response updates the parent component message
        await interaction.response.edit_message(embed=embed, view=self.appearance_view)
        await interaction.followup.send(
            f"✅ Fun prefix set to **`{value}`**. "
            f"Users can now type `{value} hug @user`.",
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.response.send_message(
                f"❌ Could not save fun prefix: {error}", ephemeral=True
            )
        except Exception:
            try:
                await interaction.followup.send(
                    f"❌ Could not save fun prefix: {error}", ephemeral=True
                )
            except Exception:
                pass


class EmbedBannerModal(discord.ui.Modal, title="Change Embed Banner"):
    url_input = discord.ui.TextInput(
        label="Image URL (leave blank to remove)",
        placeholder="https://example.com/banner.png",
        max_length=512,
        required=False,
    )

    def __init__(self, guild_id: int, appearance_view):
        super().__init__()
        self.guild_id = guild_id
        self.appearance_view = appearance_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.url_input.value.strip() or None
        await set_branding(self.guild_id, embed_banner=value)
        self.appearance_view.embed_banner = value
        embed = self.appearance_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.appearance_view)


# ─────────────────────────────────────────────
#  Appearance sub-page view (per-guild)
# ─────────────────────────────────────────────

class AppearanceView(discord.ui.View):
    def __init__(self, invoker: discord.Member, guild_id: int, branding: dict, main_view, fun_prefix: str = DEFAULT_FUN_PREFIX):
        super().__init__(timeout=180)
        self.invoker       = invoker
        self.guild_id      = guild_id
        self.main_view     = main_view
        self.branding_name  = branding["branding_name"]
        self.embed_color    = branding["embed_color"]
        self.embed_thumbnail = branding["embed_thumbnail"]
        self.embed_banner   = branding["embed_banner"]
        self.fun_prefix     = fun_prefix

    def build_embed(self) -> discord.Embed:
        thumb_display  = f"[View]({self.embed_thumbnail})" if self.embed_thumbnail else "Not set"
        banner_display = f"[View]({self.embed_banner})"  if self.embed_banner   else "Not set"
        embed = discord.Embed(
            title="🔧 __Bot Message Appearance__",
            description=(
                f"➡️ Use the buttons below to customize how the bot looks in this server.\n\n"
                f"➡️ **Branding Name:** `{self.branding_name}`\n"
                f"➡️ **Embed Color:** `{color_to_hex(self.embed_color)}`\n"
                f"➡️ **Embed Thumbnail:** {thumb_display}\n"
                f"➡️ **Embed Banner:** {banner_display}\n"
                f"➡️ **Fun Prefix:** `{self.fun_prefix}` — users type `{self.fun_prefix} hug @user`\n"
            ),
            color=self.embed_color,
        )
        if self.embed_thumbnail:
            embed.set_thumbnail(url=self.embed_thumbnail)
        if self.embed_banner:
            embed.set_image(url=self.embed_banner)
        embed.set_footer(text=f"• {self.branding_name} | Bot Customization")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.invoker:
            await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Branding Name", emoji="🌐", style=discord.ButtonStyle.secondary, row=0)
    async def btn_branding(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BrandingNameModal(self.guild_id, self))

    @discord.ui.button(label="Embed Color", emoji="➡️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedColorModal(self.guild_id, self))

    @discord.ui.button(label="Thumbnail", emoji="🛡️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_thumbnail(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedThumbnailModal(self.guild_id, self))

    @discord.ui.button(label="Banner", emoji="🧩", style=discord.ButtonStyle.secondary, row=0)
    async def btn_banner(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedBannerModal(self.guild_id, self))

    @discord.ui.button(label="Fun Prefix", emoji="🎮", style=discord.ButtonStyle.secondary, row=1)
    async def btn_fun_prefix(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FunPrefixModal(self.guild_id, self))

    @discord.ui.button(label="Back", emoji="▶️", style=discord.ButtonStyle.danger, row=2)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.main_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)

    @discord.ui.button(label="Reset to Default", emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
    async def btn_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset this guild's branding back to the global/default settings."""
        await reset_branding(self.guild_id)
        branding = await get_branding(self.guild_id)
        self.branding_name   = branding["branding_name"]
        self.embed_color     = branding["embed_color"]
        self.embed_thumbnail = branding["embed_thumbnail"]
        self.embed_banner    = branding["embed_banner"]
        self.fun_prefix      = await get_fun_prefix(self.guild_id)
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(
            "🔄 Bot message appearance has been reset to the default theme.",
            ephemeral=True,
        )


# ─────────────────────────────────────────────
#  Profile sub-page view (per-guild)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  Main menu view (per-guild) — BUTTONS not dropdown
# ─────────────────────────────────────────────

class MainCustomizationView(discord.ui.View):
    def __init__(self, invoker: discord.Member, guild_id: int, branding: dict):
        super().__init__(timeout=180)
        self.invoker   = invoker
        self.guild_id  = guild_id
        self.branding  = branding

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔧 __Bot Customization__",
            description=(
                f"➡️ Customize how the bot looks in this server.\n\n"
                f"🔧 **`»`** Bot Message Appearance — branding, embed color, thumbnail & banner\n"
            ),
            color=self.branding["embed_color"],
        )
        if self.branding.get("embed_thumbnail"):
            embed.set_thumbnail(url=self.branding["embed_thumbnail"])
        embed.set_footer(text=f"• {self.branding['branding_name']} | Bot Customization")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.invoker:
            await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Bot Message Appearance", emoji="🔧", style=discord.ButtonStyle.secondary, row=0)
    async def btn_appearance(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            fun_prefix = await get_fun_prefix(self.guild_id)
        except Exception:
            fun_prefix = DEFAULT_FUN_PREFIX
        view  = AppearanceView(self.invoker, self.guild_id, self.branding, self, fun_prefix=fun_prefix)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ─────────────────────────────────────────────
#  Global customization modals
# ─────────────────────────────────────────────

class GlobalFunPrefixModal(discord.ui.Modal, title="Set Global Fun Prefix"):
    prefix_input = discord.ui.TextInput(
        label="Fun Prefix (global default, 1–3 letters)",
        placeholder="sun",
        max_length=3,
        min_length=1,
        required=True,
    )

    def __init__(self, global_view):
        super().__init__()
        self.global_view = global_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.prefix_input.value.strip().lower()
        if len(value) > 3 or not value.isalpha():
            await interaction.response.send_message(
                "❌ Invalid prefix — must be 1–3 letters only (no numbers or symbols).",
                ephemeral=True,
            )
            return
        try:
            await set_fun_prefix(0, value)  # guild_id=0 = global default
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Could not save global fun prefix: {e}", ephemeral=True
            )
            return
        self.global_view.fun_prefix = value
        embed = self.global_view.build_embed()
        # edit_message() on a modal response updates the parent component message
        await interaction.response.edit_message(embed=embed, view=self.global_view)
        await interaction.followup.send(
            f"✅ Global fun prefix set to **`{value}`**. "
            f"Servers without a custom prefix will now use `{value} hug @user`.",
            ephemeral=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.response.send_message(
                f"❌ Could not save global fun prefix: {error}", ephemeral=True
            )
        except Exception:
            try:
                await interaction.followup.send(
                    f"❌ Could not save global fun prefix: {error}", ephemeral=True
                )
            except Exception:
                pass


class GlobalBrandingNameModal(discord.ui.Modal, title="Set Global Branding Name"):
    name_input = discord.ui.TextInput(
        label="Branding Name (global default)",
        placeholder="e.g. MyBot, GuardBot, ServerGuard",
        max_length=32,
        required=True,
    )

    def __init__(self, global_view):
        super().__init__()
        self.global_view = global_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.name_input.value.strip()
        await set_global_branding(branding_name=value)
        self.global_view.branding_name = value
        embed = self.global_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.global_view)


class GlobalEmbedColorModal(discord.ui.Modal, title="Set Global Embed Color"):
    color_input = discord.ui.TextInput(
        label="Hex Color (global default)",
        placeholder="e.g. FFD700 or #FFD700",
        max_length=10,
        required=True,
    )

    def __init__(self, global_view):
        super().__init__()
        self.global_view = global_view

    async def on_submit(self, interaction: discord.Interaction):
        parsed = parse_color(self.color_input.value)
        if parsed is None:
            await interaction.response.send_message(
                "❌ Invalid hex color. Example: `FFD700` or `#FFD700`.", ephemeral=True
            )
            return
        await set_global_branding(embed_color=parsed)
        self.global_view.embed_color = parsed
        embed = self.global_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.global_view)


class GlobalThumbnailModal(discord.ui.Modal, title="Set Global Embed Thumbnail"):
    url_input = discord.ui.TextInput(
        label="Image URL (leave blank to remove)",
        placeholder="https://example.com/image.png",
        max_length=512,
        required=False,
    )

    def __init__(self, global_view):
        super().__init__()
        self.global_view = global_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.url_input.value.strip() or None
        await set_global_branding(embed_thumbnail=value)
        self.global_view.embed_thumbnail = value
        embed = self.global_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.global_view)


class GlobalBannerModal(discord.ui.Modal, title="Set Global Embed Banner"):
    url_input = discord.ui.TextInput(
        label="Image URL (leave blank to remove)",
        placeholder="https://example.com/banner.png",
        max_length=512,
        required=False,
    )

    def __init__(self, global_view):
        super().__init__()
        self.global_view = global_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.url_input.value.strip() or None
        await set_global_branding(embed_banner=value)
        self.global_view.embed_banner = value
        embed = self.global_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.global_view)


class GlobalUsernameModal(discord.ui.Modal, title="Set Bot Global Username"):
    name_input = discord.ui.TextInput(
        label="Bot Username (global)",
        placeholder="e.g. MyBot, GuardBot",
        max_length=32,
        required=True,
    )

    def __init__(self, profile_view):
        super().__init__()
        self.profile_view = profile_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        value = self.name_input.value.strip()
        try:
            await interaction.client.user.edit(username=value)
            self.profile_view.username = value
            embed = self.profile_view.build_embed()
            await interaction.message.edit(embed=embed, view=self.profile_view)
            await interaction.followup.send(
                f"✅ Bot username globally set to **{value}**. *(Discord allows limited username changes per hour.)*",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Failed: `{e}`", ephemeral=True)


class GlobalAvatarModal(discord.ui.Modal, title="Set Bot Global Avatar"):
    url_input = discord.ui.TextInput(
        label="Image URL",
        placeholder="https://example.com/avatar.png",
        max_length=512,
        required=True,
    )

    def __init__(self, profile_view):
        super().__init__()
        self.profile_view = profile_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        url = self.url_input.value.strip()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send("❌ Could not download image.", ephemeral=True)
                        return
                    image_bytes = await resp.read()
            await interaction.client.user.edit(avatar=image_bytes)
            self.profile_view.avatar_url = url
            embed = self.profile_view.build_embed()
            await interaction.message.edit(embed=embed, view=self.profile_view)
            await interaction.followup.send("✅ Bot avatar updated globally!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Failed: `{e}`", ephemeral=True)


class GlobalActivityModal(discord.ui.Modal, title="Set Bot Activity"):
    activity_type = discord.ui.TextInput(
        label="Activity Type",
        placeholder="playing / watching / listening / streaming",
        max_length=10,
        required=True,
    )
    activity_name = discord.ui.TextInput(
        label="Activity Name",
        placeholder="e.g. in 100 servers",
        max_length=64,
        required=True,
    )

    def __init__(self, profile_view):
        super().__init__()
        self.profile_view = profile_view

    async def on_submit(self, interaction: discord.Interaction):
        type_map = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
            "streaming": discord.ActivityType.streaming,
        }
        atype = type_map.get(self.activity_type.value.lower().strip())
        if atype is None:
            await interaction.response.send_message(
                "❌ Invalid type. Use: `playing`, `watching`, `listening`, or `streaming`.",
                ephemeral=True,
            )
            return
        name = self.activity_name.value.strip()
        activity = discord.Activity(type=atype, name=name)
        await interaction.client.change_presence(activity=activity)
        # Persist so the activity survives restarts and overrides the rotating task
        from utils.branding import set_custom_activity
        await set_custom_activity(self.activity_type.value.lower().strip(), name)
        interaction.client.use_custom_activity = True
        self.profile_view.activity_text = f"{self.activity_type.value.capitalize()} {name}"
        embed = self.profile_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.profile_view)


# ─────────────────────────────────────────────
#  Global Appearance View (saves global defaults)
# ─────────────────────────────────────────────

class GlobalAppearanceView(discord.ui.View):
    def __init__(self, invoker: discord.Member, branding: dict, main_view, fun_prefix: str = DEFAULT_FUN_PREFIX):
        super().__init__(timeout=300)
        self.invoker        = invoker
        self.main_view      = main_view
        self.branding_name  = branding["branding_name"]
        self.embed_color    = branding["embed_color"]
        self.embed_thumbnail = branding["embed_thumbnail"]
        self.embed_banner   = branding["embed_banner"]
        self.fun_prefix     = fun_prefix

    def build_embed(self) -> discord.Embed:
        thumb_display  = f"[View]({self.embed_thumbnail})" if self.embed_thumbnail else "Not set"
        banner_display = f"[View]({self.embed_banner})"  if self.embed_banner   else "Not set"
        embed = discord.Embed(
            title="🌐 __Global Bot Message Appearance__",
            description=(
                f"➡️ These settings become the **default** for all servers that have not customized their branding.\n\n"
                f"➡️ **Branding Name:** `{self.branding_name}`\n"
                f"➡️ **Embed Color:** `{color_to_hex(self.embed_color)}`\n"
                f"➡️ **Embed Thumbnail:** {thumb_display}\n"
                f"➡️ **Embed Banner:** {banner_display}\n"
                f"➡️ **Fun Prefix (global default):** `{self.fun_prefix}`\n"
            ),
            color=self.embed_color,
        )
        if self.embed_thumbnail:
            embed.set_thumbnail(url=self.embed_thumbnail)
        if self.embed_banner:
            embed.set_image(url=self.embed_banner)
        embed.set_footer(text=f"• {self.branding_name} | Global Customization Control")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.invoker:
            await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Branding Name", emoji="🌐", style=discord.ButtonStyle.secondary, row=0)
    async def btn_branding(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GlobalBrandingNameModal(self))

    @discord.ui.button(label="Embed Color", emoji="➡️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GlobalEmbedColorModal(self))

    @discord.ui.button(label="Thumbnail", emoji="🛡️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_thumbnail(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GlobalThumbnailModal(self))

    @discord.ui.button(label="Banner", emoji="🧩", style=discord.ButtonStyle.secondary, row=0)
    async def btn_banner(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GlobalBannerModal(self))

    @discord.ui.button(label="Fun Prefix", emoji="🎮", style=discord.ButtonStyle.secondary, row=1)
    async def btn_fun_prefix(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GlobalFunPrefixModal(self))

    @discord.ui.button(label="Back", emoji="▶️", style=discord.ButtonStyle.danger, row=2)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.main_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)


# ─────────────────────────────────────────────
#  Global Bot Profile View
# ─────────────────────────────────────────────

class GlobalBotProfileView(discord.ui.View):
    def __init__(self, invoker: discord.Member, bot, main_view):
        super().__init__(timeout=300)
        self.invoker      = invoker
        self.bot          = bot
        self.main_view    = main_view
        self.username     = bot.user.name if bot.user else "Unknown"
        self.avatar_url   = str(bot.user.display_avatar.url) if bot.user else None
        self.activity_text = "Not set"
        self.status_text  = "Not set"

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🤖 __Global Bot Appearance__",
            description=(
                f"➡️ Edit the bot's global Discord profile.\n\n"
                f"➡️ **Username:** `{self.username}`\n"
                f"➡️ **Avatar:** {'[View](' + self.avatar_url + ')' if self.avatar_url else 'Not set'}\n"
                f"➡️ **Activity:** `{self.activity_text}`\n"
                f"➡️ **Status:** `{self.status_text}`\n\n"
                f"-# ⚠️ Username/avatar changes are globally rate-limited by Discord."
            ),
            color=DEFAULT_COLOR,
        )
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        embed.set_footer(text="• Global Customization Control | Bot Appearance")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.invoker:
            await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Username", emoji="📛", style=discord.ButtonStyle.secondary, row=0)
    async def btn_username(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GlobalUsernameModal(self))

    @discord.ui.button(label="Avatar", emoji="🌱", style=discord.ButtonStyle.secondary, row=0)
    async def btn_avatar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GlobalAvatarModal(self))

    @discord.ui.button(label="Activity", emoji="🎮", style=discord.ButtonStyle.secondary, row=0)
    async def btn_activity(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GlobalActivityModal(self))

    @discord.ui.select(
        placeholder="Set Bot Status…",
        options=[
            discord.SelectOption(label="🟢 Online",           value="online"),
            discord.SelectOption(label="🟡 Idle",             value="idle"),
            discord.SelectOption(label="🔴 Do Not Disturb",   value="dnd"),
            discord.SelectOption(label="⚫ Invisible",        value="invisible"),
        ],
        row=1,
    )
    async def select_status(self, interaction: discord.Interaction, select: discord.ui.Select):
        status_map = {
            "online":    discord.Status.online,
            "idle":      discord.Status.idle,
            "dnd":       discord.Status.do_not_disturb,
            "invisible": discord.Status.invisible,
        }
        chosen = select.values[0]
        status = status_map[chosen]
        await interaction.client.change_presence(status=status)
        self.status_text = chosen.capitalize()
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Reset Activity", emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
    async def btn_reset_activity(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear the custom activity and resume the rotating status task."""
        from utils.branding import clear_custom_activity
        await clear_custom_activity()
        interaction.client.use_custom_activity = False
        self.activity_text = "Not set (rotating status resumed)"
        await interaction.client.change_presence(activity=None)
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", emoji="▶️", style=discord.ButtonStyle.danger, row=2)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.main_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)


# ─────────────────────────────────────────────
#  Global main menu dropdown
# ─────────────────────────────────────────────

class GlobalCustomizationDropdown(discord.ui.Select):
    def __init__(self, invoker, bot, branding):
        self.invoker = invoker
        self.bot     = bot
        self.branding = branding
        options = [
            discord.SelectOption(
                label="Customize Bot Message Appearance",
                description="Set the global default branding for all servers",
                emoji="🌐",
                value="appearance",
            ),
            discord.SelectOption(
                label="Customize Bot Appearance",
                description="Edit the bot's username, avatar, status & activity globally",
                emoji="🤖",
                value="profile",
            ),
        ]
        super().__init__(
            placeholder="Select a global option…",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.invoker:
            await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )
            return
        if self.values[0] == "appearance":
            try:
                from utils.branding import get_fun_prefix as _gfp
                fun_prefix = await _gfp(0)  # global prefix (guild_id=0)
            except Exception:
                fun_prefix = DEFAULT_FUN_PREFIX
            view  = GlobalAppearanceView(self.invoker, self.branding, self.view, fun_prefix=fun_prefix)
            embed = view.build_embed()
        else:
            view  = GlobalBotProfileView(self.invoker, self.bot, self.view)
            embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class GlobalMainView(discord.ui.View):
    def __init__(self, invoker: discord.Member, bot, branding: dict):
        super().__init__(timeout=300)
        self.invoker  = invoker
        self.bot      = bot
        self.branding = branding
        self.add_item(GlobalCustomizationDropdown(invoker, bot, branding))

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚙️ __Global Customization Control__",
            description=(
                f"➡️ You are in the **control server** — changes here affect **all servers** globally.\n\n"
                f"🌐 **`»`** Customize Bot Message Appearance — set global default branding\n"
                f"🤖 **`»`** Customize Bot Appearance — username, avatar, status & activity\n"
            ),
            color=self.branding["embed_color"],
        )
        if self.branding.get("embed_thumbnail"):
            embed.set_thumbnail(url=self.branding["embed_thumbnail"])
        embed.set_footer(text=f"• {self.branding['branding_name']} | Global Customization Control")
        return embed


# ─────────────────────────────────────────────
#  Cog
# ─────────────────────────────────────────────

class BotCustomization(Cog, name="botcustomization"):
    def __init__(self, client: zyrox):
        self.client = client

    # ── Prefix command ────────────────────────────────────────────────────────

    @commands.command(
        name="botcustomization",
        aliases=["botcustom", "customize", "customizebot"],
        help="Open the bot customization panel to change branding, embed colors, thumbnails and banners.",
    )
    @commands.has_permissions(manage_guild=True)
    @ignore_check()
    @blacklist_check()
    async def botcustomization(self, ctx):
        branding = await get_branding(ctx.guild.id)
        view     = MainCustomizationView(ctx.author, ctx.guild.id, branding)
        embed    = view.build_embed()
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @botcustomization.error
    async def botcustomization_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="⛔ Access Denied",
                description="You need the **Manage Server** permission to use this command.",
                color=0x000000,
            )
            await ctx.reply(embed=embed, mention_author=False)

    # ── Slash command /botcustomization ───────────────────────────────────────

    @app_commands.command(
        name="botcustomization",
        description="Customize the bot's message appearance for this server (branding, colors, thumbnails, banners).",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def slash_botcustomization(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        branding = await get_branding(interaction.guild.id)
        view     = MainCustomizationView(interaction.user, interaction.guild.id, branding)
        embed    = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    # ── Slash command /global_customization ───────────────────────────────────

    @app_commands.command(
        name="global_customization",
        description="[Control Server Only] Global bot customization — affects all servers.",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def global_customization(self, interaction: discord.Interaction):
        # Guild-null guard
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        # Must be a designated control guild
        ctrl_guilds = get_ctrl_guild_ids()
        if not ctrl_guilds:
            await interaction.response.send_message(
                "❌ No control servers have been configured. Set the `ctrl_guild_id_1` secret to enable this command.",
                ephemeral=True,
            )
            return
        if interaction.guild_id not in ctrl_guilds:
            await interaction.response.send_message(
                "❌ This command can only be used from a designated control server.",
                ephemeral=True,
            )
            return

        # Must have Administrator permission or be the server owner
        member = interaction.guild.get_member(interaction.user.id)
        is_owner = interaction.guild.owner_id == interaction.user.id
        is_admin = member and member.guild_permissions.administrator if member else False
        if not (is_owner or is_admin):
            await interaction.response.send_message(
                "❌ You need the **Administrator** permission to use this command.",
                ephemeral=True,
            )
            return

        branding = await get_global_branding()
        view     = GlobalMainView(interaction.user, interaction.client, branding)
        embed    = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
