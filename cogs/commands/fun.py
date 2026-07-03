import discord
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
    "pats":        "patted",
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
    "thumbs":      "gave thumbs to",
    "triggered":   "got triggered by",
    "wag":         "wagged excitedly for",
    "pic":         "took a pic of",
    "gif":         "made a gif of",
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
    "pats":        "There, there! 🥺",
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
    "thumbs":      "You got it! 👍",
    "triggered":   "TRIGGERED! 😡",
    "wag":         "So excited! 🐕",
    "pic":         "Say cheese! 📸",
    "gif":         "GIF time! 🎬",
    "headpat":     "Aww! 🥺",
}

# Maps keyword → waifu.pics SFW endpoint (free, no API key needed)
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
    "pats":        "pat",
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
    "thumbs":      "thumbsup",
    "triggered":   "triggered",
    "wag":         "wag",
    "pic":         "lurk",
    "gif":         "lurk",
    "headpat":     "bonk",
}

KEYWORDS = frozenset(PAST_TENSE.keys())


# ─── Cog ──────────────────────────────────────────────────────────────────────

class Fun(commands.Cog):
    """Fun reaction commands triggered with the sun prefix."""

    def __init__(self, bot):
        self.bot = bot

    # ── GIF fetcher ───────────────────────────────────────────────────────────

    async def _get_gif(self, keyword):
        """Fetch a random anime GIF URL for the keyword via waifu.pics."""
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
            logger.warning(f"[Fun] GIF fetch failed for keyword '{keyword}': {exc}")
        return ""

    # ── Message listener ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            # Ignore bots and DMs
            if message.author.bot or not message.guild:
                return

            content = message.content.strip()
            if not content:
                return

            lower = content.lower()

            # Must start with "sun " (case-insensitive)
            if not lower.startswith("sun "):
                return

            # Parse: sun <keyword> ...
            parts = lower.split()
            if len(parts) < 2:
                return

            keyword = parts[1]
            if keyword not in KEYWORDS:
                return

            # Must have at least one non-bot, non-self mention
            mentions = [
                m for m in message.mentions
                if not m.bot and m.id != message.author.id
            ]
            if not mentions:
                return

            target = mentions[0]

            # Fetch GIF (graceful fallback if API unavailable)
            gif_url = await self._get_gif(keyword)

            # Build embed
            past    = PAST_TENSE[keyword]
            emotion = EMOTIONS[keyword]

            # Author field carries the profile pic + full action sentence
            author_line = f"{message.author.display_name} {past} {target.display_name}! {emotion}"

            embed = discord.Embed(
                # description is required for the embed to be accepted by Discord's API
                description=f"{target.mention} {emotion}",
                color=0xFFD700,
            )
            embed.set_author(
                name=author_line,
                icon_url=message.author.display_avatar.url,
            )
            if gif_url:
                embed.set_image(url=gif_url)

            try:
                await message.channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(
                    f"[Fun] Missing Embed Links / Send Messages permission in "
                    f"#{message.channel} ({message.guild})"
                )
            except discord.HTTPException as exc:
                logger.error(f"[Fun] HTTPException sending embed: {exc}")

        except Exception as exc:
            logger.error(f"[Fun] Unhandled error in on_message: {exc}", exc_info=True)
