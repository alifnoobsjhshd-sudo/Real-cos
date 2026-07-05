from utils import getConfig
import discord
from discord.ext import commands
from utils.Tools import get_ignore_data
import aiosqlite
from utils import help as vhelp
from utils.branding import DEFAULT_BRANDING, get_branding


class _MentionCtx:
    """Minimal context-like object so the help View works from a mention interaction."""
    def __init__(self, interaction: discord.Interaction, prefix: str):
        self.author = interaction.user
        self.bot = interaction.client
        self.guild = interaction.guild
        self.prefix = prefix


def build_serverinfo_embed(guild: discord.Guild, user: discord.Member) -> discord.Embed:
    """Build a serverinfo embed identical in style to the >serverinfo command."""
    embed = discord.Embed(color=0xFF0000)
    embed.set_author(
        name=f"{guild.name}'s Information",
        icon_url=guild.me.display_avatar.url if guild.icon is None else guild.icon.url,
    )
    embed.set_footer(
        text=f"Requested By {user}",
        icon_url=user.display_avatar.url if user.avatar else user.default_avatar.url,
    )
    if guild.icon is not None:
        embed.set_thumbnail(url=guild.icon.url)
        embed.timestamp = discord.utils.utcnow()

    c_at = guild.created_at.strftime("%Y-%m-%d %H:%M:%S")
    embed.add_field(
        name="**__About__**",
        value=(
            f"**Name : ** {guild.name}\n"
            f"**ID :** {guild.id}\n"
            f"**Owner 👑 :** {guild.owner} (<@{guild.owner_id}>)\n"
            f"**Created At : ** {c_at}\n"
            f"**Members :** {len(guild.members)}"
        ),
        inline=False,
    )
    if guild.description:
        embed.add_field(name="**__Description__**", value=guild.description, inline=False)

    embed.add_field(
        name="**__General Stats__**",
        value=(
            f"**Verification Level :** {guild.verification_level}\n"
            f"**Channels :** {len(guild.channels)}\n"
            f"**Roles :** {len(guild.roles)}\n"
            f"**Emojis :** {len(guild.emojis)}\n"
            f"**Boost Status :** Level {guild.premium_tier} (Boosts: {guild.premium_subscription_count})"
        ),
        inline=False,
    )
    if guild.features:
        features = "\n".join(
            [f"✅: {f[:1].upper() + f[1:].lower().replace('_', ' ')}"
             for f in guild.features]
        )
        embed.add_field(
            name="**__Features__**",
            value=features if len(features) <= 1024 else features[:1000] + "...and more",
            inline=False,
        )
    embed.add_field(
        name="**__Channels__**",
        value=(
            f"**Total:** {len(guild.channels)}\n"
            f"Channels: {len(guild.text_channels)} text, {len(guild.voice_channels)} voice"
        ),
        inline=False,
    )
    regular_emojis = [e for e in guild.emojis if not e.animated]
    animated_emojis = [e for e in guild.emojis if e.animated]
    embed.add_field(
        name="**__Emoji Info__**",
        value=(
            f"Regular: {len(regular_emojis)}/100\n"
            f"Animated: {len(animated_emojis)}/100\n"
            f"Total Emoji: {len(guild.emojis)}/200"
        ),
        inline=False,
    )
    embed.add_field(
        name="**__Boost Status__**",
        value=f"Level: {guild.premium_tier} [🚀{guild.premium_subscription_count} boosts]",
        inline=False,
    )
    roles = guild.roles
    roles_list = [role.mention for role in roles]
    roles_count = len(roles_list)
    roles_display = "\n".join(roles_list[:10])
    if roles_count > 10:
        roles_display += f"\n...and {roles_count - 10} more"
    embed.add_field(
        name=f"**__Server Roles__ [ {roles_count} ]**",
        value=roles_display or "None",
        inline=False,
    )
    if guild.banner:
        embed.set_image(url=guild.banner)
    return embed


def build_help_embed(bot: commands.Bot, user: discord.Member, prefix: str) -> discord.Embed:
    """Build the main help embed identical in style to the >help command."""
    embed = discord.Embed(
        description=(
            f"**➡️ __Get Started Today__**\n"
            f"**➡️ Type `{prefix}antinuke enable`**\n"
            f"**➡️ Server Prefix:** `{prefix}`\n"
            f"**➡️ Total Commands:** `{len(set(bot.walk_commands()))}`\n"
        ),
        color=0xFF0000,
    )
    embed.set_author(name=f"{user}", icon_url=user.display_avatar.url)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(
        name="☁️ __**Main Features**__",
        value=(
            ">>> \n 🛡️ `»` Security\n"
            " 🤖 `»` Automoderation\n"
            " 🔧 `»` Utility\n"
            " 📶 `»` Autoreact & responder\n"
            " ⚔️ `»` Moderation\n"
            " 👥 `»` Autorole & Invc\n"
            " 🚀 `»` Fun\n"
            " 🎮 `»` Games\n"
            " 🔨 `»` Ignore Channels\n"
            " 📶 `»` Server\n"
            " 🔊 `»` Voice\n"
            " 🌱 `»` Welcomer\n"
            " 🎉 `»` Giveaway\n"
            " 🎫 `»` Ticket 🆕\n"
            " 👥 `»` Invite Tracker 🆕\n"
        ),
    )
    embed.add_field(
        name=" 🧩 __**Extra Features**__",
        value=(
            ">>> \n 📡 `»` Advance Logging\n"
            " ⭐ `»` Vanityroles\n"
            " 🔢 `»` Counting 🆕\n"
            " ⚙️ `»` J2C 🆕\n"
            " 🚀 `»` Boost 🆕\n"
            " ⬆️ `»` Leveling 🆕\n"
            " 📌 `»` Sticky 🆕\n"
            " ⚡ `»` Verification 🆕\n"
            " 🔒 `»` Encryption 🆕\n"
            " ⛏️ `»` Minecraft 🆕\n"
            " ✉️ `»` Joindm 🆕\n"
            " 🎂 `»` Birthday 🆕\n"
            " 🎂 `»` Customrole\n"
        ),
    )
    embed.set_footer(text=f"Requested By {user} | {DEFAULT_BRANDING}")
    return embed


class MentionDropdown(discord.ui.Select):
    def __init__(self, message: discord.Message, bot: commands.Bot, prefix: str):
        self.message = message
        self.bot = bot
        self.prefix = prefix
        options = [
            discord.SelectOption(
                label="About Server",
                emoji="📶",
                description="View this server's information",
            ),
            discord.SelectOption(
                label="Commands",
                emoji="☁️",
                description="Explore all bot commands",
            ),
        ]
        super().__init__(
            placeholder="Choose an option",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.message.author.id:
            return await interaction.response.send_message(
                "This menu is not for you!", ephemeral=True
            )

        if self.values[0] == "About Server":
            embed = build_serverinfo_embed(interaction.guild, interaction.user)
            await interaction.response.edit_message(embed=embed, view=self.view)

        elif self.values[0] == "Commands":
            prefix = ">"  # Prefix is locked to >

            ctx = _MentionCtx(interaction, prefix)
            mapping = {cog: cog.get_commands() for cog in self.bot.cogs.values()}
            embed = build_help_embed(self.bot, interaction.user, prefix)

            help_view = vhelp.View(mapping=mapping, ctx=ctx, homeembed=embed, ui=2)
            await interaction.response.edit_message(embed=embed, view=help_view)


class MentionView(discord.ui.View):
    def __init__(self, message: discord.Message, bot: commands.Bot, prefix: str):
        super().__init__(timeout=None)
        self.add_item(MentionDropdown(message, bot, prefix))


class Mention(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF0000
        self.bot_name = DEFAULT_BRANDING

    async def is_blacklisted(self, message):
        async with aiosqlite.connect("db/block.db") as db:
            cursor = await db.execute(
                "SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (message.guild.id,)
            )
            if await cursor.fetchone():
                return True
            cursor = await db.execute(
                "SELECT 1 FROM user_blacklist WHERE user_id = ?", (message.author.id,)
            )
            if await cursor.fetchone():
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if await self.is_blacklisted(message):
            return

        ignore_data = await get_ignore_data(message.guild.id)
        if (
            str(message.author.id) in ignore_data["user"]
            or str(message.channel.id) in ignore_data["channel"]
        ):
            return

        if self.bot.user in message.mentions and len(message.content.strip().split()) == 1:
            guild_id = message.guild.id
            prefix = ">"  # Prefix is locked to >

            branding = await get_branding(guild_id)
            embed = discord.Embed(
                title=f"{message.guild.name}",
                description=(
                    f"> ❤️ **Hey {message.author.mention}!**\n"
                    f"> ➡️ **Prefix For This Server: `{prefix}`**\n\n"
                    f"> ☁️ Type `/help` or `{prefix}help` to explore all commands."
                ),
                color=branding["embed_color"],
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(
                text=f"Powered by {branding['branding_name']}",
                icon_url=self.bot.user.display_avatar.url,
            )

            view = MentionView(message, self.bot, prefix)
            await message.channel.send(embed=embed, view=view)


def setup(bot):
    bot.add_cog(Mention(bot))
