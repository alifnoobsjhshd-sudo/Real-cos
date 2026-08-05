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
    from utils.emojis import e as _e
    embed.add_field(
        name="**__About__**",
        value=(
            f"**Name : ** {guild.name}\n"
            f"**ID :** {guild.id}\n"
            f"**Owner {_e('king')} :** {guild.owner} (<@{guild.owner_id}>)\n"
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
            [f"{_e('ztick')}: {f[:1].upper() + f[1:].lower().replace('_', ' ')}"
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
        value=f"Level: {guild.premium_tier} [{_e('zrocket')}{guild.premium_subscription_count} boosts]",
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
            f"**{_e('zArrow')} __Get Started Today__**\n"
            f"**{_e('zArrow')} Type `{prefix}antinuke enable`**\n"
            f"**{_e('zArrow')} Server Prefix:** `{prefix}`\n"
            f"**{_e('zArrow')} Total Commands:** `{len(set(bot.walk_commands()))}`\n"
        ),
        color=0xFF0000,
    )
    embed.set_author(name=f"{user}", icon_url=user.display_avatar.url)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(
        name=f"{_e('zCloud')} __**Main Features**__",
        value=(
            f">>> \n {_e('zSafe')} `»` Security\n"
            f" {_e('zbot')} `»` Automoderation\n"
            f" {_e('zwrench')} `»` Utility\n"
            f" {_e('zwifi')} `»` Autoreact & responder\n"
            f" {_e('zsowrd')} `»` Moderation\n"
            f" {_e('zpeople')} `»` Autorole & Invc\n"
            f" {_e('zrocket')} `»` Fun\n"
            f" {_e('games')} `»` Games\n"
            f" {_e('zyroxhammer')} `»` Ignore Channels\n"
            f" {_e('zwifi')} `»` Server\n"
            f" {_e('zvoice')} `»` Voice\n"
            f" {_e('zseed')} `»` Welcomer\n"
            f" {_e('ztada')} `»` Giveaway\n"
            f" {_e('zticket')} `»` Ticket {_e('New')}\n"
            f" {_e('zpeople')} `»` Invite Tracker {_e('New')}\n"
        ),
    )
    embed.add_field(
        name=f" {_e('zmodule')} __**Extra Features**__",
        value=(
            f">>> \n {_e('zcast')} `»` Advance Logging\n"
            f" {_e('starr')} `»` Vanityroles\n"
            f" {_e('zcounting')} `»` Counting {_e('New')}\n"
            f" {_e('zsettings')} `»` J2C {_e('New')}\n"
            f" {_e('zrocket')} `»` Boost {_e('New')}\n"
            f" {_e('zlevelup')} `»` Leveling {_e('New')}\n"
            f" {_e('zpin')} `»` Sticky {_e('New')}\n"
            f" {_e('zyroxthunder')} `»` Verification {_e('New')}\n"
            f" {_e('lock')} `»` Encryption {_e('New')}\n"
            f" {_e('zpickaxe')} `»` Minecraft {_e('New')}\n"
            f" {_e('zenvelope')} `»` Joindm {_e('New')}\n"
            f" {_e('zbirthday')} `»` Birthday {_e('New')}\n"
            f" {_e('zbirthday')} `»` Customrole\n"
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
                emoji=_e("zwifi") or "📶",
                description="View this server's information",
            ),
            discord.SelectOption(
                label="Commands",
                emoji=_e("zCloud") or "☁️",
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
                    f"> {_e('heart3')} **Hey {message.author.mention}!**\n"
                    f"> {_e('zArrow')} **Prefix For This Server: `{prefix}`**\n\n"
                    f"> {_e('zCloud')} Type `/help` or `{prefix}help` to explore all commands."
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
