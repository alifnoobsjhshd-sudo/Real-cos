from utils import getConfig
import discord
from discord.ext import commands
from utils.Tools import get_ignore_data
from utils.emojis import e as _e
import aiosqlite
from utils import help as vhelp


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
            f"**Owner <:king:1448951721479901334> :** {guild.owner} (<@{guild.owner_id}>)\n"
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
        value=f"Level: {guild.premium_tier} [<:boost:1448966463586041906>{guild.premium_subscription_count} boosts]",
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
            f"**<a:ArrowRed:1448951520077811806> __Start Zyrox X Today__**\n"
            f"**<:zArrow:1448951532837015643> Type `{prefix}antinuke enable`**\n"
            f"**<:zArrow:1448951532837015643> Server Prefix:** `{prefix}`\n"
            f"**<:zArrow:1448951532837015643> Total Commands:** `{len(set(bot.walk_commands()))}`\n"
        ),
        color=0xFF0000,
    )
    embed.set_author(name=f"{user}", icon_url=user.display_avatar.url)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(
        name="<:zCloud:1448951498213032036> __**Main Features**__",
        value=(
            ">>> \n <:zSafe:1448951403434479626> `»` Security\n"
            " <:zbot:1448951393216888905> `»` Automoderation\n"
            " <:zwrench:1448951382597177495> `»` Utility\n"
            " <:zwifi:1448951466931912715> `»` Autoreact & responder\n"
            " <:zsowrd:1448951362238021682> `»` Moderation\n"
            " <:zpeople:1448951456861519962> `»` Autorole & Invc\n"
            " <:zrocket:1448951445989888010> `»` Fun\n"
            " <:games:1448951285498777641> `»` Games\n"
            " <:zban:1448951424665784373> `»` Ignore Channels\n"
            " <:zwifi:1448951466931912715> `»` Server\n"
            " <:zunmute:1448951487970414694> `»` Voice\n"
            " <:zseed:1448951477640101929> `»` Welcomer\n"
            " <:ztada:1448951329664925717> `»` Giveaway\n"
            " <:zticket:1448951318713470987> `»` Ticket <:New:1448949337395695616>\n"
            " <:zpeople:1448951456861519962> `»` Invite Tracker <:New:1448949337395695616>\n"
        ),
    )
    embed.add_field(
        name=" <:zmodule:1448951340716785744> __**Extra Features**__",
        value=(
            ">>> \n <:zcast:1448951414301655175> `»` Advance Logging\n"
            " <:starr:1448951307707748395> `»` Vanityroles\n"
            " <:zcounting:1448949348103749713> `»` Counting <:New:1448949337395695616>\n"
            " <:zyrox_system:1448949359159939143> `»` J2C <:New:1448949337395695616>\n"
            " <:boost:1448966463586041906> `»` Boost <:New:1448949337395695616>\n"
            " <:zlevelup:1448964376504696943> `»` Leveling <:New:1448949337395695616>\n"
            " <:zpin:1448949810462855249> `»` Sticky <:New:1448949337395695616>\n"
            " <:zyroxthunder:1448949415200034907> `»` Verification <:New:1448949337395695616>\n"
            " <:lock:1448949549455511685> `»` Encryption <:New:1448949337395695616>\n"
            " <:zmc:1448964387426537474> `»` Minecraft <:New:1448949337395695616>\n"
            " <:zmsg:1448964399166394483> `»` Joindm <:New:1448949337395695616>\n"
            " <:zcircle:1448964410155470848> `»` Birthday <:New:1448949337395695616>\n"
            " <:zcircle:1448951351601270814> `»` Customrole\n"
        ),
    )
    embed.set_footer(text=f"Requested By {user} | [Support](https://discord.gg/codexdev)")
    return embed


class MentionDropdown(discord.ui.Select):
    def __init__(self, message: discord.Message, bot: commands.Bot, prefix: str):
        self.message = message
        self.bot = bot
        self.prefix = prefix
        options = [
            discord.SelectOption(
                label="About Server",
                emoji="<:zwifi:1448951466931912715>",
                description="View this server's information",
            ),
            discord.SelectOption(
                label="Commands",
                emoji="<:zCloud:1448951498213032036>",
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
            data = await getConfig(interaction.guild.id)
            prefix = data["prefix"]

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
        self.bot_name = "Zyrox X"

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
            data = await getConfig(guild_id)
            prefix = data["prefix"]

            embed = discord.Embed(
                title=f"{message.guild.name}",
                description=(
                    f"> <:heart3:1448966390353756200> **Hey {message.author.mention}!**\n"
                    f"> <a:ArrowRed:1448951520077811806> **Prefix For This Server: `{prefix}`**\n\n"
                    f"> <:zCloud:1448951498213032036> Type `/help` or `{prefix}help` to explore all commands."
                ),
                color=self.color,
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(
                text="Powered by Zyrox Development™",
                icon_url=self.bot.user.display_avatar.url,
            )

            view = MentionView(message, self.bot, prefix)
            await message.channel.send(embed=embed, view=view)


def setup(bot):
    bot.add_cog(Mention(bot))
