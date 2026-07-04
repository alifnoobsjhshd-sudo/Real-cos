"""
Fun anime-reaction commands.

Slash command (primary, works regardless of MESSAGE_CONTENT intent):
    /sun action:<keyword> user:<@member>

Message trigger (bonus, requires MESSAGE_CONTENT privileged intent
in the Discord Developer Portal + discord.Intents.all() in code):
    sun <keyword> @mention

Supported keywords: bite, boop, bully, cuddle, cry, dance, greet,
handholding, highfive, hold, hug, insult, kill, kiss, lick, nom,
pat, poke, punch, slap, snuggle, stare, tickle, wave, blush,
deredere, grin, happy, lewd, pout, scoff, shrug, sleepy, smile,
smug, teehee, thinking, thonking, thumbsup, triggered, wag, headpat
"""

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import logging

logger = logging.getLogger(__name__)


# ─── Keyword data ─────────────────────────────────────────────────────────────

PAST_TENSE = {
    "bite":        "bit",
    "boop":        "booped",
    "bully":       "bullied",
    "cuddle":      "cuddled",
    "greet":       "greeted",
    "handholding": "held hands with",
    "highfive":    "high-fived",
    "hold":        "held",
    "hug":         "hugged",
    "insult":      "insulted",
    "kill":        "killed",
    "kiss":        "kissed",
    "lick":        "licked",
    "nom":         "nommed",
    "pat":         "patted",
    "poke":        "poked",
    "punch":       "punched",
    "slap":        "slapped",
    "snuggle":     "snuggled with",
    "stare":       "stared at",
    "tickle":      "tickled",
    "wave":        "waved at",
    "blush":       "blushed at",
    "cry":         "cried for",
    "dance":       "danced with",
    "deredere":    "got deredere for",
    "grin":        "grinned at",
    "happy":       "is happy for",
    "lewd":        "did something lewd to",
    "pout":        "pouted at",
    "scoff":       "scoffed at",
    "shrug":       "shrugged at",
    "sleepy":      "fell asleep on",
    "smile":       "smiled at",
    "smug":        "was smug at",
    "teehee":      "went teehee at",
    "thinking":    "thought about",
    "thonking":    "thonked about",
    "thumbsup":    "gave a thumbs up to",
    "triggered":   "got triggered by",
    "wag":         "wagged excitedly for",
    "headpat":     "headpatted",
}

EMOTIONS = {
    "bite":        "Ouch! That must have hurt! 😬",
    "boop":        "Boop! ✨",
    "bully":       "That's not very nice... 😢",
    "cuddle":      "So warm and fluffy! 🥰",
    "greet":       "Hello there! 👋",
    "handholding": "How wholesome! 🤝",
    "highfive":    "Nice! ✋",
    "hold":        "So gentle! 💕",
    "hug":         "Group hug! 🤗",
    "insult":      "That was really rude! 😤",
    "kill":        "Chill dude! 💀",
    "kiss":        "Ahh! So cute! 😍",
    "lick":        "W-what?! 👅",
    "nom":         "Yummy! 😋",
    "pat":         "Good job! 🥺",
    "poke":        "Hey! Stop that! 👉",
    "punch":       "That's gonna leave a mark! 💢",
    "slap":        "Did you deserve that? 👋",
    "snuggle":     "So cozy! 💤",
    "stare":       "Why are you staring? 👀",
    "tickle":      "Hahaha! Stop! 😂",
    "wave":        "Hello! 👋",
    "blush":       "Look how cute! 😳",
    "cry":         "Don't cry! 😢",
    "dance":       "Let's groove! 💃",
    "deredere":    "You're so sweet! 💕",
    "grin":        "Suspicious… 😏",
    "happy":       "Yay! 🎉",
    "lewd":        "That's inappropriate! 🙈",
    "pout":        "Don't be pouty! 😤",
    "scoff":       "How rude! 😒",
    "shrug":       "Whatever… 🤷",
    "sleepy":      "Time for a nap! 😴",
    "smile":       "Such a beautiful smile! 😊",
    "smug":        "You look very smug! 😏",
    "teehee":      "Teehee~ 😄",
    "thinking":    "Hmm… 🤔",
    "thonking":    "Big brain time! 🧠",
    "thumbsup":    "Great job! 👍",
    "triggered":   "TRIGGERED! 😡",
    "wag":         "So excited! 🐕",
    "headpat":     "Aww! 🥺",
}

# keyword → waifu.pics SFW endpoint (free, no API key required)
_WAIFUPICS = {
    "bite":        "bite",
    "boop":        "poke",
    "bully":       "bully",
    "cuddle":      "cuddle",
    "greet":       "wave",
    "handholding": "handhold",
    "highfive":    "highfive",
    "hold":        "hug",
    "hug":         "hug",
    "insult":      "bully",
    "kill":        "shoot",
    "kiss":        "kiss",
    "lick":        "lick",
    "nom":         "nom",
    "pat":         "pat",
    "poke":        "poke",
    "punch":       "punch",
    "slap":        "slap",
    "snuggle":     "cuddle",
    "stare":       "stare",
    "tickle":      "tickle",
    "wave":        "wave",
    "blush":       "blush",
    "cry":         "cry",
    "dance":       "dance",
    "deredere":    "hug",
    "grin":        "smug",
    "happy":       "happy",
    "lewd":        "smug",
    "pout":        "pout",
    "scoff":       "smug",
    "shrug":       "shrug",
    "sleepy":      "sleep",
    "smile":       "smile",
    "smug":        "smug",
    "teehee":      "laugh",
    "thinking":    "think",
    "thonking":    "think",
    "thumbsup":    "thumbsup",
    "triggered":   "triggered",
    "wag":         "wag",
    "headpat":     "bonk",
}

KEYWORDS = frozenset(PAST_TENSE.keys())


# ─── Cog ──────────────────────────────────────────────────────────────────────

class Fun(commands.Cog):
    """Fun anime-reaction commands."""

    def __init__(self, bot):
        self.bot = bot

    # ── Shared helpers ────────────────────────────────────────────────────────

    async def _get_gif(self, keyword: str) -> str:
        """Return a random GIF URL from waifu.pics for the given keyword."""
        endpoint = _WAIFUPICS.get(keyword, "hug")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.waifu.pics/sfw/{endpoint}",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        url = data.get("url", "")
                        if url:
                            return url
        except Exception as exc:
            logger.warning("[Fun] GIF fetch failed for '%s': %s", keyword, exc)
        return ""

    async def _build_embed(
        self,
        author: discord.abc.User,
        target: discord.abc.User,
        keyword: str,
    ) -> discord.Embed:
        """Build the reaction embed (fetches a GIF internally)."""
        gif_url  = await self._get_gif(keyword)
        past     = PAST_TENSE[keyword]
        emotion  = EMOTIONS[keyword]

        embed = discord.Embed(
            description=f"{target.mention} {emotion}",
            color=0xFFD700,
        )
        embed.set_author(
            name=f"{author.display_name} {past} {target.display_name}! {emotion}",
            icon_url=author.display_avatar.url,
        )
        if gif_url:
            embed.set_image(url=gif_url)
        return embed

    # ── Slash command (/sun action:<keyword> user:<member>) ───────────────────

    @app_commands.command(
        name="sun",
        description="Send an anime reaction GIF to someone.",
    )
    @app_commands.describe(
        action="The reaction (e.g. kiss, hug, pat) — start typing to see all options",
        user="The server member to react to",
    )
    @app_commands.guild_only()
    async def sun(
        self,
        interaction: discord.Interaction,
        action: str,
        user: discord.Member,
    ) -> None:
        # Validate action (autocomplete filters, but manual entry is possible)
        if action not in KEYWORDS:
            await interaction.response.send_message(
                f"❌ Unknown action **{discord.utils.escape_markdown(action)}**. "
                "Start typing in the `action` field to see all options.",
                ephemeral=True,
            )
            return

        if user.bot:
            await interaction.response.send_message(
                "❌ You can't use that on a bot!", ephemeral=True
            )
            return

        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You can't use that on yourself!", ephemeral=True
            )
            return

        # Defer so we have time to fetch the GIF
        await interaction.response.defer()

        try:
            embed = await self._build_embed(interaction.user, user, action)
            await interaction.followup.send(embed=embed)
        except Exception as exc:
            logger.error("[Fun] Error sending slash reaction: %s", exc, exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ Something went wrong sending the reaction.", ephemeral=True
                )
            except Exception:
                pass

    @sun.autocomplete("action")
    async def _sun_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for the /sun action parameter."""
        return [
            app_commands.Choice(
                name=f"{kw}  —  {PAST_TENSE[kw]}",
                value=kw,
            )
            for kw in sorted(KEYWORDS)
            if current.lower() in kw.lower()
        ][:25]

    # ── Message listener (bonus — needs MESSAGE_CONTENT privileged intent) ────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        try:
            if message.author.bot or not message.guild:
                return

            content = message.content  # empty str if MESSAGE_CONTENT intent disabled
            if not content:
                return

            lower = content.strip().lower()
            if not lower.startswith("sun "):
                return

            parts = lower.split()
            if len(parts) < 2:
                return

            keyword = parts[1]
            if keyword not in KEYWORDS:
                return

            # At least one non-bot, non-self user must be mentioned
            mentions = [
                m for m in message.mentions
                if not m.bot and m.id != message.author.id
            ]
            if not mentions:
                return

            embed = await self._build_embed(message.author, mentions[0], keyword)

            try:
                await message.channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(
                    "[Fun] Missing Embed Links / Send Messages in #%s (%s)",
                    message.channel, message.guild,
                )
            except discord.HTTPException as exc:
                logger.error("[Fun] HTTP error sending embed: %s", exc)

        except Exception as exc:
            logger.error("[Fun] Unhandled error in on_message: %s", exc, exc_info=True)
