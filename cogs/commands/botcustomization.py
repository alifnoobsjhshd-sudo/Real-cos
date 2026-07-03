import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from core.Cog import Cog
from core.zyrox import zyrox
from utils.branding import (
    get_branding, set_branding,
    get_guild_profile, set_guild_profile,
    parse_color, color_to_hex,
    DEFAULT_BRANDING, DEFAULT_COLOR,
)
from utils.Tools import ignore_check, blacklist_check


# ─────────────────────────────────────────────
#  Modals
# ─────────────────────────────────────────────

class BrandingNameModal(discord.ui.Modal, title="Change Branding Name"):
    name_input = discord.ui.TextInput(
        label="Branding Name",
        placeholder="e.g. Sunlight",
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


class DisplayNameModal(discord.ui.Modal, title="Set Bot Display Name"):
    name_input = discord.ui.TextInput(
        label="Display Name (leave blank to reset)",
        placeholder="e.g. Sunlight",
        max_length=32,
        required=False,
    )

    def __init__(self, guild_id: int, profile_view):
        super().__init__()
        self.guild_id = guild_id
        self.profile_view = profile_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.name_input.value.strip() or None
        await set_guild_profile(self.guild_id, display_name=value)
        self.profile_view.display_name = value
        try:
            await interaction.guild.me.edit(nick=value)
        except discord.Forbidden:
            pass
        embed = self.profile_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.profile_view)


class BioModal(discord.ui.Modal, title="Set Server Bio"):
    bio_input = discord.ui.TextInput(
        label="Server Bio (leave blank to remove)",
        placeholder="A short description shown in bot info...",
        max_length=190,
        style=discord.TextStyle.paragraph,
        required=False,
    )

    def __init__(self, guild_id: int, profile_view):
        super().__init__()
        self.guild_id = guild_id
        self.profile_view = profile_view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.bio_input.value.strip() or None
        await set_guild_profile(self.guild_id, bio=value)
        self.profile_view.bio = value
        embed = self.profile_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.profile_view)


class AvatarModal(discord.ui.Modal, title="Set Bot Profile Picture"):
    url_input = discord.ui.TextInput(
        label="Image URL",
        placeholder="https://example.com/avatar.png",
        max_length=512,
        required=True,
    )

    def __init__(self, guild_id: int, profile_view):
        super().__init__()
        self.guild_id = guild_id
        self.profile_view = profile_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        url = self.url_input.value.strip()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            "❌ Could not download the image. Make sure the URL is a direct image link.",
                            ephemeral=True,
                        )
                        return
                    image_bytes = await resp.read()
            await interaction.client.user.edit(avatar=image_bytes)
            await set_guild_profile(self.guild_id, avatar_url=url)
            self.profile_view.avatar_url = url
            embed = self.profile_view.build_embed()
            await interaction.edit_original_response(content=None)
            await interaction.message.edit(embed=embed, view=self.profile_view)
            await interaction.followup.send(
                "✅ Profile picture updated! *(This applies globally to all servers.)*",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to update avatar: `{e}`. Discord allows changing the avatar a limited number of times per hour.",
                ephemeral=True,
            )


class ProfileBannerModal(discord.ui.Modal, title="Set Bot Profile Banner"):
    url_input = discord.ui.TextInput(
        label="Image URL",
        placeholder="https://example.com/banner.png",
        max_length=512,
        required=True,
    )

    def __init__(self, guild_id: int, profile_view):
        super().__init__()
        self.guild_id = guild_id
        self.profile_view = profile_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        url = self.url_input.value.strip()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            "❌ Could not download the image. Make sure the URL is a direct image link.",
                            ephemeral=True,
                        )
                        return
                    image_bytes = await resp.read()
            await interaction.client.user.edit(banner=image_bytes)
            await set_guild_profile(self.guild_id, banner_url=url)
            self.profile_view.banner_url = url
            embed = self.profile_view.build_embed()
            await interaction.edit_original_response(content=None)
            await interaction.message.edit(embed=embed, view=self.profile_view)
            await interaction.followup.send(
                "✅ Profile banner updated! *(This applies globally to all servers.)*",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to update banner: `{e}`. Discord requires a Nitro-boosted account for profile banners.",
                ephemeral=True,
            )


# ─────────────────────────────────────────────
#  Appearance sub-page view
# ─────────────────────────────────────────────

class AppearanceView(discord.ui.View):
    def __init__(self, invoker: discord.Member, guild_id: int, branding: dict, main_view):
        super().__init__(timeout=180)
        self.invoker    = invoker
        self.guild_id   = guild_id
        self.main_view  = main_view
        self.branding_name  = branding["branding_name"]
        self.embed_color    = branding["embed_color"]
        self.embed_thumbnail = branding["embed_thumbnail"]
        self.embed_banner   = branding["embed_banner"]

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

    @discord.ui.button(label="Back", emoji="▶️", style=discord.ButtonStyle.danger, row=1)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.main_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)


# ─────────────────────────────────────────────
#  Profile sub-page view
# ─────────────────────────────────────────────

class ProfileView(discord.ui.View):
    def __init__(self, invoker: discord.Member, guild_id: int, profile: dict, branding: dict, main_view):
        super().__init__(timeout=180)
        self.invoker    = invoker
        self.guild_id   = guild_id
        self.main_view  = main_view
        self.embed_color = branding["embed_color"]
        self.branding_name = branding["branding_name"]
        self.display_name = profile["display_name"]
        self.bio          = profile["bio"]
        self.avatar_url   = profile["avatar_url"]
        self.banner_url   = profile["banner_url"]

    def build_embed(self) -> discord.Embed:
        dn = self.display_name or "Not set (using default)"
        bio = self.bio or "Not set"
        av  = f"[View]({self.avatar_url})" if self.avatar_url else "Not set"
        bn  = f"[View]({self.banner_url})"  if self.banner_url  else "Not set"
        embed = discord.Embed(
            title="📣 __Bot Server Profile__",
            description=(
                f"➡️ Customize the bot's profile settings.\n\n"
                f"➡️ **Display Name:** `{dn}`\n"
                f"➡️ **Server Bio:** {bio}\n"
                f"➡️ **Profile Picture:** {av}\n"
                f"➡️ **Profile Banner:** {bn}\n\n"
                f"-# ⚠️ Profile picture & banner changes apply **globally** to all servers and have Discord rate limits."
            ),
            color=self.embed_color,
        )
        embed.set_footer(text=f"• {self.branding_name} | Bot Customization")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.invoker:
            await interaction.response.send_message(
                "You must run this command to interact with it.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Display Name", emoji="📣", style=discord.ButtonStyle.secondary, row=0)
    async def btn_displayname(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DisplayNameModal(self.guild_id, self))

    @discord.ui.button(label="Server Bio", emoji="🌐", style=discord.ButtonStyle.secondary, row=0)
    async def btn_bio(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BioModal(self.guild_id, self))

    @discord.ui.button(label="Profile Picture", emoji="🌱", style=discord.ButtonStyle.secondary, row=0)
    async def btn_avatar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AvatarModal(self.guild_id, self))

    @discord.ui.button(label="Profile Banner", emoji="🧩", style=discord.ButtonStyle.secondary, row=0)
    async def btn_banner(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ProfileBannerModal(self.guild_id, self))

    @discord.ui.button(label="Back", emoji="▶️", style=discord.ButtonStyle.danger, row=1)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.main_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.main_view)


# ─────────────────────────────────────────────
#  Main dropdown
# ─────────────────────────────────────────────

class CustomizationDropdown(discord.ui.Select):
    def __init__(self, invoker: discord.Member, guild_id: int, branding: dict, profile: dict, main_view):
        self.invoker    = invoker
        self.guild_id   = guild_id
        self.branding   = branding
        self.profile    = profile
        self.main_view  = main_view
        options = [
            discord.SelectOption(
                label="Customize Bot Message Appearance",
                description="Change branding, embed color, thumbnail & banner",
                emoji="🔧",
                value="appearance",
            ),
            discord.SelectOption(
                label="Bot Server Profile Customization",
                description="Change display name, bio, avatar & banner",
                emoji="📣",
                value="profile",
            ),
        ]
        super().__init__(
            placeholder="Select an option to customize...",
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
            view  = AppearanceView(self.invoker, self.guild_id, self.branding, self.main_view)
            embed = view.build_embed()
        else:
            view  = ProfileView(self.invoker, self.guild_id, self.profile, self.branding, self.main_view)
            embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# ─────────────────────────────────────────────
#  Main menu view
# ─────────────────────────────────────────────

class MainCustomizationView(discord.ui.View):
    def __init__(self, invoker: discord.Member, guild_id: int, branding: dict, profile: dict):
        super().__init__(timeout=180)
        self.invoker   = invoker
        self.guild_id  = guild_id
        self.branding  = branding
        self.profile   = profile
        self.add_item(CustomizationDropdown(invoker, guild_id, branding, profile, self))

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔧 __Bot Customization__",
            description=(
                f"➡️ Select an option from the dropdown below to customize the bot for this server.\n\n"
                f"🛡️ **`»`** Customize Bot Message Appearance\n"
                f"📣 **`»`** Bot Server Profile Customization\n"
            ),
            color=self.branding["embed_color"],
        )
        if self.branding.get("embed_thumbnail"):
            embed.set_thumbnail(url=self.branding["embed_thumbnail"])
        embed.set_footer(text=f"• {self.branding['branding_name']} | Bot Customization")
        return embed


# ─────────────────────────────────────────────
#  Cog
# ─────────────────────────────────────────────

class BotCustomization(Cog, name="botcustomization"):
    def __init__(self, client: zyrox):
        self.client = client

    @commands.command(
        name="botcustomization",
        aliases=["botcustom", "customize", "customizebot"],
        help="Open the bot customization panel to change branding, embed colors, thumbnails, banners, and the bot's server profile.",
    )
    @commands.has_permissions(manage_guild=True)
    @ignore_check()
    @blacklist_check()
    async def botcustomization(self, ctx):
        branding = await get_branding(ctx.guild.id)
        profile  = await get_guild_profile(ctx.guild.id)
        view     = MainCustomizationView(ctx.author, ctx.guild.id, branding, profile)
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
