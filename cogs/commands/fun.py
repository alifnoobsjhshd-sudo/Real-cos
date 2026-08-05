"""
Fun anime-reaction commands.

Slash command (primary, works regardless of MESSAGE_CONTENT intent):
    /fun action:<keyword> user:<@member>

Message trigger (bonus, requires MESSAGE_CONTENT privileged intent
in the Discord Developer Portal + discord.Intents.all() in code):
    sun <keyword> @mention

Supported keywords: bite, boop, bully, cuddle, cry, dance, greet,
handholding, highfive, hold, hug, insult, kill, kiss, lick, nom,
pat, poke, punch, slap, snuggle, stare, tickle, wave, blush,
deredere, grin, happy, lewd, pout, scoff, shrug, sleepy, smile,
smug, teehee, thinking, thonking, thumbsup, triggered, wag, headpat,
tackle, bonk, nuzzle, yeet

Blocked keywords (respond with 'I can't show that'): sex, fuck
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
    "tackle":      "tackled",
    "bonk":        "bonked",
    "nuzzle":      "nuzzled",
    "yeet":        "yeeted",
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
    "tackle":      "Oof! You got tackled! 💨",
    "bonk":        "No horny! 🔨",
    "nuzzle":      "So affectionate! 🐾",
    "yeet":        "They're gone! 🚀",
}

# Keywords that get a blocked response instead of a GIF
BLOCKED_KEYWORDS: frozenset[str] = frozenset({"sex", "fuck"})

# keyword → nekos.best SFW endpoint (primary; free, no API key)
# Fallback: waifu.pics SFW endpoint (same free/no-key policy)
# Note: "bully" and "lick" are 404 on nekos.best — mapped to closest alternatives.
_NEKOSBEST = {
    "bite":        "bite",
    "boop":        "poke",
    "bully":       "slap",       # "bully" returns 404 on nekos.best
    "cuddle":      "cuddle",
    "greet":       "wave",
    "handholding": "handhold",
    "highfive":    "highfive",
    "hold":        "hug",
    "hug":         "hug",
    "insult":      "slap",       # "bully" returns 404 on nekos.best
    "kill":        "shoot",
    "kiss":        "kiss",
    "lick":        "nom",        # "lick" returns 404 on nekos.best
    "nom":         "nom",
    "pat":         "pat",
    "poke":        "poke",
    "punch":       "punch",
    "slap":        "slap",
    "snuggle":     "cuddle",
    "stare":       "stare",
    "tickle":      "pat",       # no tickle on nekos.best
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
    "triggered":   "bully",     # no triggered on nekos.best
    "wag":         "wag",
    "headpat":     "bonk",
    "tackle":      "slap",      # no tackle on nekos.best
    "bonk":        "bonk",
    "nuzzle":      "cuddle",    # no nuzzle on nekos.best
    "yeet":        "throw",     # no yeet on nekos.best
}

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
    "tickle":      "pat",       # no tickle on waifu.pics either
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
    "tackle":      "slap",      # no tackle on waifu.pics
    "bonk":        "bonk",
    "nuzzle":      "cuddle",    # no nuzzle on waifu.pics
    "yeet":        "throw",     # no yeet on waifu.pics
}

_OTAKUGIFS = {
    # ── Confirmed-working otakugifs endpoints ───────────────────────────────
    # Endpoints that return 400 on otakugifs are remapped to the closest
    # working alternative so every keyword always produces a GIF.
    "bite":        "bite",
    "boop":        "poke",
    "bully":       "slap",        # "bully" → 400; use slap
    "cuddle":      "cuddle",
    "greet":       "wave",
    "handholding": "cuddle",      # "handholding" → 400; use cuddle
    "highfive":    "wave",        # "highfive" → 400; use wave
    "hold":        "hug",
    "hug":         "hug",
    "insult":      "slap",        # "shoot" → 400; use slap
    "kill":        "slap",        # "shoot" → 400; use slap
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
    "thinking":    "stare",       # "think" → 400; use stare
    "thonking":    "stare",       # "think" → 400; use stare
    "thumbsup":    "thumbsup",
    "triggered":   "punch",       # "triggered" → 400; use punch
    "wag":         "smile",       # "wag" → 400; use smile
    "headpat":     "pat",
    "tackle":      "slap",
    "bonk":        "pat",         # "bonk" → 400; use pat
    "nuzzle":      "cuddle",
    "yeet":        "slap",        # "throw" → 400; use slap
}

KEYWORDS = frozenset(PAST_TENSE.keys())
ALL_TRIGGER_KEYWORDS = KEYWORDS | BLOCKED_KEYWORDS


# ─── Cog ──────────────────────────────────────────────────────────────────────

class Fun(commands.Cog):
    """Fun anime-reaction commands."""

    def __init__(self, bot):
        self.bot = bot

    # ── Shared helpers ────────────────────────────────────────────────────────

    async def _get_gif(self, keyword: str) -> str:
        """Return a GIF URL for the keyword.

        Tries otakugifs.xyz first (reliable, no auth), then nekos.best with a
        proper User-Agent, then waifu.pics on both known hostnames. Returns ""
        if all fail so the embed still posts without an image.
        """
        connector = aiohttp.TCPConnector(ssl=False)
        # Several anime GIF APIs block requests with no User-Agent or with a
        # generic aiohttp string. Use a browser-like one.
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        }

        def _valid(url: str) -> bool:
            # Exclude video files — Discord embed image fields only show still
            # images or GIFs, not .mp4 files (nekos.best v2 returns .mp4).
            return (
                isinstance(url, str)
                and url.startswith(("http://", "https://"))
                and not url.lower().endswith((".mp4", ".webm", ".mov"))
            )

        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            # ── Primary: otakugifs.xyz (most reliable from Replit/Render) ─────
            og_endpoint = _OTAKUGIFS.get(keyword, "hug")
            try:
                async with session.get(
                    f"https://api.otakugifs.xyz/gif?reaction={og_endpoint}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        url = data.get("url") or data.get("link") or data.get("image") or ""
                        if _valid(url):
                            return url
                    logger.warning(
                        "[Fun] otakugifs returned %s for '%s' (%s)",
                        resp.status, keyword, og_endpoint,
                    )
            except Exception as exc:
                logger.warning(
                    "[Fun] otakugifs fetch failed for '%s': %s", keyword, exc
                )

            # ── Fallback 1: nekos.best (needs a real User-Agent) ──────────────
            nb_endpoint = _NEKOSBEST.get(keyword, "hug")
            try:
                async with session.get(
                    f"https://nekos.best/api/v2/{nb_endpoint}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        results = data.get("results", [])
                        if results:
                            url = results[0].get("url") or results[0].get("url") or ""
                            if _valid(url):
                                return url
                    logger.warning(
                        "[Fun] nekos.best returned %s for '%s' (%s)",
                        resp.status, keyword, nb_endpoint,
                    )
            except Exception as exc:
                logger.warning(
                    "[Fun] nekos.best fetch failed for '%s': %s", keyword, exc
                )

            # ── Fallback 2: waifu.pics (two possible hostnames) ─────────────────
            wp_endpoint = _WAIFUPICS.get(keyword, "hug")
            for wp_base in ("https://api.waifu.pics", "https://waifu.pics/api"):
                try:
                    async with session.get(
                        f"{wp_base}/sfw/{wp_endpoint}",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            url = data.get("url") or data.get("link") or ""
                            if _valid(url):
                                return url
                        logger.warning(
                            "[Fun] waifu.pics (%s) returned %s for '%s' (%s)",
                            wp_base, resp.status, keyword, wp_endpoint,
                        )
                except Exception as exc:
                    logger.warning(
                        "[Fun] waifu.pics (%s) fetch failed for '%s': %s",
                        wp_base, keyword, exc,
                    )

        return ""

    async def _build_embed(
        self,
        author: discord.abc.User,
        target: discord.abc.User,
        keyword: str,
    ) -> discord.Embed:
        """Build the reaction embed (fetches a GIF internally).

        Title format (per fun.txt):
          [author avatar] {author} {past} {target} -| {emotion}
        The embed image is the reaction GIF.
        """
        gif_url  = await self._get_gif(keyword)
        past     = PAST_TENSE[keyword]
        emotion  = EMOTIONS[keyword]

        embed = discord.Embed(color=0xFFD700)
        # Author line carries the profile pic + full action + emotion in one line
        embed.set_author(
            name=f"{author.display_name} {past} {target.display_name} -| {emotion}",
            icon_url=author.display_avatar.url,
        )
        if gif_url:
            embed.set_image(url=gif_url)
        return embed

    # ── Slash command (/fun action:<keyword> user:<member>) ──────────────────

    @app_commands.command(
        name="fun",
        description="Send an anime reaction GIF to someone.",
    )
    @app_commands.describe(
        action="The reaction (e.g. kiss, hug, pat) — start typing to see all options",
        user="The server member to react to",
    )
    @app_commands.guild_only()
    async def fun(
        self,
        interaction: discord.Interaction,
        action: str,
        user: discord.Member,
    ) -> None:
        from utils.emojis import e as _e
        action = action.strip().lower()

        # Blocked keywords — politely decline
        if action in BLOCKED_KEYWORDS:
            await interaction.response.send_message(
                f"{_e('zcross')} I can't show that", ephemeral=True
            )
            return

        # Validate action (autocomplete filters, but manual entry is possible)
        if action not in KEYWORDS:
            await interaction.response.send_message(
                f"{_e('zwarning')} Unknown action **{discord.utils.escape_markdown(action)}**. "
                "Start typing in the `action` field to see all options.",
                ephemeral=True,
            )
            return

        if user.bot:
            await interaction.response.send_message(
                f"{_e('zwarning')} {action} a real human dude!", ephemeral=True
            )
            return

        if user.id == interaction.user.id:
            await interaction.response.send_message(
                f"{_e('zwarning')} lol you can't {action} yourself!", ephemeral=True
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
                from utils.emojis import e as _e
                await interaction.followup.send(
                    f"{_e('zcross')} Something went wrong sending the reaction.", ephemeral=True
                )
            except Exception:
                pass

    @fun.autocomplete("action")
    async def _fun_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for the /fun action parameter."""
        return [
            app_commands.Choice(
                name=f"{kw}  —  {PAST_TENSE[kw]}",
                value=kw,
            )
            for kw in sorted(KEYWORDS)
            if current.lower() in kw.lower()
        ][:25]
        # Note: BLOCKED_KEYWORDS (sex, fuck) are intentionally excluded from autocomplete

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
            # Read the guild's configured fun prefix; isolate in its own try so
            # a DB error never silences the entire on_message handler.
            try:
                from utils.branding import get_fun_prefix as _gfp
                fun_prefix = await _gfp(message.guild.id)
            except Exception:
                fun_prefix = "sun"
            if not lower.startswith(fun_prefix + " "):
                return

            parts = lower.split()
            if len(parts) < 2:
                return

            keyword = parts[1]

            # ── <prefix> game <game_name> [@user] ────────────────────────────
            if keyword == "game":
                game_name = parts[2] if len(parts) > 2 else None
                AVAILABLE_GAMES = [
                    "blackjack", "chess", "tic-tac-toe", "country-guesser",
                    "rps", "lights-out", "wordle", "2048", "memory-game",
                    "number-slider", "battleship", "connect-four", "slots",
                ]
                if not game_name:
                    games_list = ", ".join(f"`{g}`" for g in AVAILABLE_GAMES)
                    await message.channel.send(
                        f"🎮 **Available games:** {games_list}\n"
                        f"Usage: `{fun_prefix} game <game_name> [@player]`"
                    )
                    return
                if game_name not in AVAILABLE_GAMES:
                    games_list = ", ".join(f"`{g}`" for g in AVAILABLE_GAMES)
                    await message.channel.send(
                        f"❌ No game called `{game_name}`.\n"
                        f"🎮 **Available:** {games_list}"
                    )
                    return
                game_cmd = self.bot.get_command(game_name)
                if game_cmd is None:
                    await message.channel.send(f"❌ Game `{game_name}` is not available right now.")
                    return
                ctx = await self.bot.get_context(message)
                mentions = [m for m in message.mentions if not m.bot and m.id != message.author.id]
                try:
                    if mentions:
                        try:
                            await ctx.invoke(game_cmd, player=mentions[0])
                        except TypeError:
                            await ctx.invoke(game_cmd)
                    else:
                        await ctx.invoke(game_cmd)
                except Exception as exc:
                    await message.channel.send(f"❌ Could not start `{game_name}`: {exc}")
                return

            # Blocked keywords — reply and stop
            if keyword in BLOCKED_KEYWORDS:
                try:
                    await message.channel.send("I can't show that")
                except Exception:
                    pass
                return

            if keyword not in KEYWORDS:
                return

            raw_mentions = message.mentions
            if not raw_mentions:
                return

            # Self-mention check
            if all(m.id == message.author.id for m in raw_mentions):
                try:
                    await message.channel.send(f"lol you can't {keyword} yourself")
                except Exception:
                    pass
                return

            # Bot-mention check
            if all(m.bot for m in raw_mentions):
                try:
                    await message.channel.send(f"{keyword} a real human dude")
                except Exception:
                    pass
                return

            # At least one valid (non-bot, non-self) mention required
            mentions = [
                m for m in raw_mentions
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
