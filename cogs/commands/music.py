import os
import random
import discord
from discord.ext import commands, tasks
import datetime
from discord.ui import Button, View
import wavelink
from utils import Paginator, DescriptionEmbedPaginator
from core import Cog, zyrox, Context
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import aiohttp
from typing import cast
import asyncio
from utils.Tools import *
from utils.emojis import e as _e
track_histories = {}

# ── Emoji helper: parse a custom-emoji string → PartialEmoji, with fallback ──
def _pe(name: str, fallback: str = "") -> discord.PartialEmoji:
    s = _e(name)
    try:
        if s:
            return discord.PartialEmoji.from_str(s)
    except Exception:
        pass
    if fallback:
        try:
            return discord.PartialEmoji.from_str(fallback)
        except Exception:
            pass
    return discord.PartialEmoji.from_str("❓")
import base64
import asyncio
import re

SPOTIFY_TRACK_REGEX = r"https?://open\.spotify\.com/track/([a-zA-Z0-9]+)"
SPOTIFY_PLAYLIST_REGEX = r"https?://open\.spotify\.com/playlist/([a-zA-Z0-9]+)"
SPOTIFY_ALBUM_REGEX = r"https?://open\.spotify\.com/album/([a-zA-Z0-9]+)"

class SpotifyAPI:
    BASE_URL = "https://api.spotify.com/v1"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None

    async def get_token(self):
        auth_url = "https://accounts.spotify.com/api/token"
        auth_value = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode('utf-8')).decode('utf-8')
        headers = {"Authorization": f"Basic {auth_value}"}
        data = {"grant_type": "client_credentials"}
        async with aiohttp.ClientSession() as session:
            async with session.post(auth_url, headers=headers, data=data) as response:
                text = await response.text()
                if response.status != 200:
                    raise Exception(f"Failed to fetch token: {response.status}, response: {text}")
                self.token = (await response.json()).get("access_token")

    async def get(self, endpoint, params=None):
        retries = 2
        for attempt in range(retries):
            if not self.token or attempt > 0:
                await self.get_token()

            url = f"{self.BASE_URL}/{endpoint}"
            headers = {"Authorization": f"Bearer {self.token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 401 and attempt < retries - 1:
                        continue
                    elif response.status != 200:
                        raise Exception(f"Failed to fetch data from Spotify: {response.status}")
                    return await response.json()
        raise Exception("Exceeded max retries to fetch Spotify data")

    
    async def get_track(self, track_id):
        return await self.get(f"tracks/{track_id}")

    async def get_playlist(self, playlist_id):
        return await self.get(f"playlists/{playlist_id}")

spotify_api = SpotifyAPI(
    client_id=os.getenv("SPOTIFY_CLIENT_ID", ""),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ""),
)

class PlatformSelectView(View):
    def __init__(self, ctx, query):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.query = query

        platforms = [
            ("Spotify", "spsearch", discord.ButtonStyle.green, _pe("spotify")),
        ]

        for name, source, style, emoji in platforms:
            button = Button(label=name, style=style, emoji=emoji)
            button.callback = self.create_callback(source)
            self.add_item(button)

    def create_callback(self, source):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.ctx.author:
                await interaction.response.send_message("Only the command author can select a platform.", ephemeral=True)
                return

            await interaction.response.send_message(f"Searching on {interaction.data['custom_id']}...", ephemeral=True)
            await self.perform_search(source)
            await interaction.message.delete()
        return callback

    async def perform_search(self, source):
        results = await wavelink.Playable.search(self.query, source=source)
        if not results:
            return await self.ctx.send(embed=discord.Embed(description="No results found.", color=0xFF0000))

        top_results = results[:5]
        embed = discord.Embed(
            title=f"Top 5 Results for '{self.query}' ({source})",
            color=0x1DB954
        )
        for i, track in enumerate(top_results, start=1):
            embed.add_field(name=f"{i}. {track.title}", value=f"Duration: {track.length // 1000 // 60}:{track.length // 1000 % 60} | [Link]({track.uri})", inline=False)

        await self.ctx.send(embed=embed, view=SearchResultView(self.ctx, top_results))

    

class SearchResultView(View):
    def __init__(self, ctx, results):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.results = results

        for i in range(5):
            button = Button(label=str(i + 1), style=discord.ButtonStyle.primary)
            button.callback = self.create_callback(i)
            self.add_item(button)

    def create_callback(self, index):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.ctx.author:
                await interaction.response.send_message("Only the command author can select a track.", ephemeral=True)
                return

            track = self.results[index]
            vc = self.ctx.voice_client or await self.ctx.author.voice.channel.connect(cls=wavelink.Player)
            vc.ctx = self.ctx


            if not vc.playing:
                await vc.play(track)
                await interaction.response.send_message(f"Started playing `{track.title}`.")
                await self.ctx.cog.display_player_embed(vc, track, self.ctx)

            else:
                await vc.queue.put_wait(track)
                await interaction.response.send_message(f"Added `{track.title}` to the queue.")

        return callback



class VolumeModal(discord.ui.Modal, title="Set Volume"):
    volume_input = discord.ui.TextInput(
        label="Volume (1–150)",
        placeholder="Enter a number between 1 and 150",
        min_length=1,
        max_length=3,
        required=True,
    )

    def __init__(self, player):
        super().__init__()
        self.player = player

    async def on_submit(self, interaction: discord.Interaction):
        try:
            level = int(self.volume_input.value)
        except ValueError:
            return await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
        if not 1 <= level <= 150:
            return await interaction.response.send_message("Volume must be between 1 and 150.", ephemeral=True)
        await self.player.set_volume(level)
        await interaction.response.send_message(
            f"🔊 Volume set to **{level}%** by {interaction.user.display_name}.", ephemeral=True
        )


class MusicControlView(View):
    def __init__(self, player, ctx):
        super().__init__(timeout=None)
        self.player = player
        self.ctx = ctx
        # Assign custom emojis AND labels — order must match decorator definition order below:
        # Row 0: rewind, pause, forward
        # Row 1: previous, stop, skip
        # Row 2: autoplay, shuffle, loop
        # Row 3: replay, volume
        _emoji_map = [
            _pe("rewind1"),                           # 0  rewind
            _pe("zpause"),                            # 1  pause / play toggle
            _pe("forward"),                           # 2  forward
            _pe("zback"),                             # 3  previous track
            _pe("musicstop_icons"),                   # 4  stop
            _pe("skip"),                              # 5  skip
            _pe("zautoplay"),                         # 6  autoplay
            _pe("shuffle"),                           # 7  shuffle
            _pe("zloop"),                             # 8  loop
            _pe("zplay"),                             # 9  replay
            discord.PartialEmoji.from_str("🔊"),      # 10 volume
        ]
        _label_map = [
            "Rewind",    # 0
            "Pause",     # 1
            "Forward",   # 2
            "Previous",  # 3
            "Stop",      # 4
            "Skip",      # 5
            "Autoplay",  # 6
            "Shuffle",   # 7
            "Loop",      # 8
            "Replay",    # 9
            "Volume",    # 10
        ]
        buttons = [c for c in self.children if isinstance(c, discord.ui.Button)]
        for btn, emoji, label in zip(buttons, _emoji_map, _label_map):
            btn.emoji = emoji
            btn.label = label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.ctx.voice_client or not self.player.playing:
            await interaction.response.send_message("I'm not currently playing this anymore.", ephemeral=True)
            return False
        if interaction.user in self.ctx.voice_client.channel.members:
            return True
        await interaction.response.send_message(
            embed=discord.Embed(description="Only members in the same voice channel as me can control the player.", color=0xFF0000),
            ephemeral=True
        )
        return False

    # ── Row 0: Rewind | Pause | Forward ──────────────────────────────────────

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary, row=0)
    async def rewind_button(self, interaction: discord.Interaction, button: Button):
        if self.player.playing:
            new_position = max(self.player.position - 10000, 0)
            await self.player.seek(new_position)
            await interaction.response.send_message("Rewound 10 seconds.", ephemeral=True)
        else:
            await interaction.response.send_message("No track is currently playing.", ephemeral=True)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.success, row=0)
    async def pause_button(self, interaction: discord.Interaction, button: Button):
        if self.player.paused:
            await self.player.pause(False)
            await self.player.channel.edit(status=f"🎵 Playing: {self.player.current.title}")
            button.emoji = _pe("zpause")
            button.label = "Pause"
            await interaction.response.edit_message(view=self)
        elif self.player.playing:
            await self.player.pause(True)
            await self.player.channel.edit(status=f"⏸️ Paused: {self.player.current.title}")
            button.emoji = _pe("zplay")
            button.label = "Play"
            await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.secondary, row=0)
    async def forward_button(self, interaction: discord.Interaction, button: Button):
        if self.player.playing:
            new_position = min(self.player.position + 10000, self.player.current.length)
            await self.player.seek(new_position)
            await interaction.response.send_message("Forwarded 10 seconds.", ephemeral=True)
        else:
            await interaction.response.send_message("No track is currently playing.", ephemeral=True)

    # ── Row 1: Previous | Stop | Skip ────────────────────────────────────────

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=1)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        guild_id = interaction.guild.id

        if guild_id in track_histories and len(track_histories[guild_id]) > 1:
            # Remove the current track from history to get to the one before it
            track_histories[guild_id].pop()
            previous_track = track_histories[guild_id][-1]

            player = self.player
            vc = self.ctx.voice_client

            # Insert the previous track at the front of the queue so it plays next
            _current_queue = list(vc.queue)
            vc.queue.clear()
            await vc.queue.put_wait(previous_track)
            for _t in _current_queue:
                await vc.queue.put_wait(_t)

            # Stopping the current track triggers on_track_end → picks from queue
            if player.playing:
                await player.stop()

            await interaction.response.send_message(
                f"⏮ Playing previous track: **{previous_track.title}**"
            )
        else:
            await interaction.response.send_message("No previous track available.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=1)
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        if self.player:
            voice_channel = self.player.channel
            if voice_channel:
                await voice_channel.edit(status=None)
            await self.player.disconnect()
            await interaction.response.send_message(f"Stopped and disconnected by **{interaction.user.display_name}**.")
        else:
            await interaction.response.send_message("Not connected.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=1)
    async def skip_button(self, interaction: discord.Interaction, button: Button):
        if self.player.autoplay == wavelink.AutoPlayMode.enabled:
            await self.player.stop()
            return await interaction.response.send_message(f"Skipped song by **{interaction.user.display_name}**.")

        if self.player and self.player.playing and not self.player.queue.is_empty:
            await self.player.stop()
            await interaction.response.send_message(f"Skipped song by **{interaction.user.display_name}**.")
        else:
            await interaction.response.send_message("No song in queue to skip.", ephemeral=True)

    # ── Row 2: Autoplay | Shuffle | Loop ─────────────────────────────────────

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=2)
    async def autoplay_button(self, interaction: discord.Interaction, button: Button):
        self.player.autoplay = (
            wavelink.AutoPlayMode.enabled if self.player.autoplay != wavelink.AutoPlayMode.enabled else wavelink.AutoPlayMode.disabled
        )
        await interaction.response.send_message(
            f"Autoplay {'enabled' if self.player.autoplay == wavelink.AutoPlayMode.enabled else 'disabled'} by **{interaction.user.display_name}**."
        )

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=2)
    async def shuffle_button(self, interaction: discord.Interaction, button: Button):
        if self.player.queue:
            random.shuffle(self.player.queue)
            await interaction.response.send_message(f"Queue shuffled by **{interaction.user.display_name}**.")
        else:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)

    @discord.ui.button(emoji="⏳", style=discord.ButtonStyle.secondary, row=2)
    async def loop_button(self, interaction: discord.Interaction, button: Button):
        self.player.queue.mode = (
            wavelink.QueueMode.loop if self.player.queue.mode != wavelink.QueueMode.loop
            else wavelink.QueueMode.normal
        )
        await interaction.response.send_message(
            f"Loop {'enabled' if self.player.queue.mode == wavelink.QueueMode.loop else 'disabled'} by **{interaction.user.display_name}**."
        )

    # ── Row 3: Replay | Volume ────────────────────────────────────────────────

    @discord.ui.button(emoji="🎵", style=discord.ButtonStyle.secondary, row=3)
    async def replay_button(self, interaction: discord.Interaction, button: Button):
        if self.player.playing:
            await self.player.seek(0)
            await interaction.response.send_message("Replaying the current track.", ephemeral=True)
        else:
            await interaction.response.send_message("No track is currently playing.", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=3)
    async def volume_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(VolumeModal(self.player))



class Music(commands.Cog):
    def __init__(self, client: zyrox):
        self.client = client
        # Wait until the bot is actually logged in before connecting to Lavalink.
        # Wavelink's websocket handshake requires a valid client.user.id in the
        # headers; connecting too early (before on_ready) results in a silent
        # handshake failure. Exceptions are logged so they are visible in Render.
        async def _initial_connect():
            await self.client.wait_until_ready()
            try:
                await self.connect_nodes()
            except Exception as e:
                print(f"[Music] Initial Lavalink connect failed: {e}")
        self.client.loop.create_task(_initial_connect())
        self.client.loop.create_task(self.monitor_inactivity())
        
        self.inactivity_timeout = 120
        self.player_inactivity = {}

        # Ordered list of every configured node — populated by _build_lavalink_nodes().
        # [{index, uri, password}]  — index is 1-based priority order.
        self._configured_nodes: list[dict] = []
        # Tracks the last time each node (by URI) returned a successful search result.
        self._node_last_success: dict[str, datetime.datetime] = {}

    async def monitor_inactivity(self):
        while True:
            for guild in self.client.guilds:
                await self.check_inactivity(guild.id) 
            await asyncio.sleep(60) 

    async def check_inactivity(self, guild_id):
        guild = self.client.get_guild(guild_id)
        if not guild:
            return

        player = None
        for vc in self.client.voice_clients:
            if vc.guild.id == guild.id:
                player = vc
                break

        if player and player.playing and len(player.channel.members) == 1:
            # Rule: if loop is active, never auto-disconnect (only /stop disconnects)
            if player.queue.mode in (wavelink.QueueMode.loop, wavelink.QueueMode.loop_all):
                return
            await self.inactivity_timer(guild)

    async def inactivity_timer(self, guild):
        await asyncio.sleep(self.inactivity_timeout)
        # Find the bot's player in this guild
        player = None
        for vc in self.client.voice_clients:
            if vc.guild.id == guild.id:
                player = vc
                break
        # Check the correct voice channel — not guild.voice_channels[0]
        if player and len(player.channel.members) == 1:
            if player:
                await player.disconnect(force=True)
                try:
                    ended = discord.Embed(description="Bot has been disconnected due to inactivity (being idle in Voice Channel) for more than 2 minutes." , color=0xFF0000)
                    ended.set_author(name="Inactive Timeout", icon_url=self.client.user.display_avatar.url)
                    from utils.branding import DEFAULT_BRANDING
                    ended.set_footer(text=f"Thanks for choosing {DEFAULT_BRANDING}!")
                    await player.ctx.channel.send(embed=ended)
                except:
                    pass

    def _build_lavalink_nodes(self) -> list[wavelink.Node]:
        """
        Build a list of wavelink Nodes from environment variables.

        Supported styles (checked in order; first match wins):

        1. Pipe-separated list:
               LAVALINK_URIS=https://node1.com|http://node2:2333
               LAVALINK_PASSWORDS=pass1|pass2

        2. Numbered variables (add as many as needed):
               LAVALINK_URL_1=https://node1.com   LAVALINK_PASSWORD_1=pass1
               LAVALINK_URL_2=http://node2:2333   LAVALINK_PASSWORD_2=pass2
               LAVALINK_URL_3=http://node3:80     LAVALINK_PASSWORD_3=pass3
               (also accepts LAVALINK_URI_N instead of LAVALINK_URL_N)
               Scanning stops at the first gap (missing _N).

        3. Single node:
               LAVALINK_URI=https://node.com  or  LAVALLINK_URL=...
               LAVALINK_PASSWORD=...          or  LAVALLINK_PASSWORD=...

        4. Built-in pool (_BUILTIN_NODES) — 7 public nodes tested live July 2026,
           used automatically when no env vars are configured.

        When the passwords list is shorter than the URI list, the last supplied
        password is reused for the remaining nodes.
        """
        uris:      list[str] = []
        passwords: list[str] = []

        # ── Style 1: pipe-separated LAVALINK_URIS ────────────────────────────
        multi_uris      = os.getenv("LAVALINK_URIS",      "").strip()
        multi_passwords = os.getenv("LAVALINK_PASSWORDS",  "").strip()
        if multi_uris:
            uris      = [u.strip() for u in multi_uris.split("|")      if u.strip()]
            passwords = [p.strip() for p in multi_passwords.split("|") if p.strip()] if multi_passwords else []

        # ── Style 2: numbered LAVALINK_URL_N / LAVALINK_URI_N ───────────────
        # NOTE: scan ALL indices 1-50 without stopping at gaps.
        # Users sometimes configure e.g. _1, _3, _5 with gaps — we collect
        # every index that has a URI and ignore the ones that don't.
        if not uris:
            found_any = False
            for n in range(1, 51):          # supports up to 50 nodes
                uri = (
                    os.getenv(f"LAVALINK_URL_{n}") or
                    os.getenv(f"LAVALINK_URI_{n}") or
                    os.getenv(f"LAVALLINK_URL_{n}") or   # double-L variant
                    os.getenv(f"LAVALLINK_URI_{n}") or   # double-L variant
                    ""
                ).strip()
                if not uri:
                    continue                # skip gaps — do NOT break
                found_any = True
                uris.append(uri)
                pw = (
                    os.getenv(f"LAVALINK_PASSWORD_{n}") or
                    os.getenv(f"LAVALLINK_PASSWORD_{n}") or   # double-L variant
                    ""
                ).strip()
                passwords.append(pw)

        # ── Style 3: single node ─────────────────────────────────────────────
        if not uris:
            single_uri = (
                os.getenv("LAVALINK_URI") or
                os.getenv("LAVALINK_URL") or   # plain LAVALINK_URL also accepted
                os.getenv("LAVALLINK_URL") or
                ""
            ).strip()
            single_password = (
                os.getenv("LAVALINK_PASSWORD") or
                os.getenv("LAVALINK_PASSWORDS") or  # accept plural form too if only one node
                os.getenv("LAVALLINK_PASSWORD") or
                ""
            ).strip()
            if single_uri:
                uris      = [single_uri]
                passwords = [single_password] if single_password else []

        # Normalize URIs — Lavalink requires a scheme.
        # Bare "host:port" → http://, bare "host" → https://.
        normalized: list[str] = []
        for uri in uris:
            if uri and not uri.startswith(("http://", "https://", "ws://", "wss://")):
                scheme = "http://" if ":" in uri else "https://"
                uri = f"{scheme}{uri}"
            normalized.append(uri)

        # Deduplicate by normalized URI — never connect to the same host twice.
        seen: set[str] = set()
        deduped_uris:      list[str] = []
        deduped_passwords: list[str] = []
        fallback_pw = passwords[-1] if passwords else "youshallnotpass"
        for i, uri in enumerate(normalized):
            if uri in seen:
                continue
            seen.add(uri)
            pw = passwords[i] if i < len(passwords) and passwords[i] else fallback_pw
            deduped_uris.append(uri)
            deduped_passwords.append(pw)

        nodes: list[wavelink.Node] = []
        for uri, pw in zip(deduped_uris, deduped_passwords):
            nodes.append(wavelink.Node(uri=uri, password=pw))

        # Save the ordered config for failover search and /lavalink display.
        self._configured_nodes = [
            {"index": i + 1, "uri": uri, "password": pw}
            for i, (uri, pw) in enumerate(zip(deduped_uris, deduped_passwords))
        ]

        return nodes

    async def connect_nodes(self) -> None:
        """
        Connect to the configured Lavalink node(s).
        Raises on failure so callers (e.g. the reconnect loop) can detect
        genuine connection errors. The startup wrapper catches and silences
        the initial attempt.

        When multiple nodes are configured, wavelink.Pool will use them for
        failover automatically — if one node drops, the next available node
        takes over for new searches/playback.
        """
        nodes = self._build_lavalink_nodes()
        # Let the exception propagate — callers decide how to handle it.
        await wavelink.Pool.connect(nodes=nodes, client=self.client, cache_capacity=None)
        print(f"[Music] Connected to {len(nodes)} Lavalink node(s): {', '.join(n.uri for n in nodes)}")

    @commands.Cog.listener()
    async def on_wavelink_node_disconnected(self, payload) -> None:
        """Reconnect to Lavalink automatically when a node drops."""
        # If other nodes are still in the pool, playback can continue while we
        # try to restore the one that dropped. With a single node, this is
        # the only path back to working music.
        remaining = len(wavelink.Pool.nodes) if wavelink.Pool.nodes else 0
        print(f"[Music] Lavalink node disconnected — {remaining} node(s) still in pool. Retrying in 15 s …")
        for attempt in range(1, 6):
            await asyncio.sleep(15)
            try:
                await self.connect_nodes()
                print(f"[Music] Lavalink reconnected on attempt {attempt}.")
                return
            except Exception as e:
                print(f"[Music] Reconnect attempt {attempt} failed: {e}")
        print("[Music] Could not reconnect to Lavalink after 5 attempts.")

    async def _search_with_failover(
        self,
        query: str,
        is_spotify_url: bool,
    ):
        """
        Try every connected Lavalink node in configured priority order until one
        successfully returns tracks.  For text queries we attempt spsearch first,
        then fall back to scsearch on the same node before moving on.

        Returns the first non-empty track list/playlist found, or None if every
        node fails.  Also records which node succeeded in self._node_last_success
        so the /lavalink command can display playback health per node.
        """
        pool = wavelink.Pool.nodes          # dict — Python 3.7+ preserves insertion order
        if not pool:
            return None

        # Build a priority-sorted list of connected nodes.
        # self._configured_nodes is in the order the user declared them (env var index).
        configured_uris = [n["uri"] for n in self._configured_nodes]

        def _priority(node: wavelink.Node) -> int:
            try:
                return configured_uris.index(node.uri)
            except ValueError:
                return 9999  # any extra node goes last

        ordered = sorted(pool.values(), key=_priority)

        for node in ordered:
            label = node.uri
            try:
                if is_spotify_url:
                    # Spotify / playlist URL — pass raw to LavaSrc
                    tracks = await wavelink.Playable.search(query, node=node)
                else:
                    # Text query — prefer Spotify search, fall back to SoundCloud
                    tracks = None
                    try:
                        tracks = await wavelink.Playable.search(
                            query, source="spsearch", node=node
                        )
                    except Exception as sp_err:
                        print(f"[Music] {label}: spsearch failed — {sp_err}")

                    if not tracks:
                        try:
                            tracks = await wavelink.Playable.search(
                                query, source="scsearch", node=node
                            )
                        except Exception as sc_err:
                            print(f"[Music] {label}: scsearch failed — {sc_err}")

                if tracks:
                    self._node_last_success[label] = datetime.datetime.utcnow()
                    print(f"[Music] Search resolved via {label}")
                    return tracks

                print(f"[Music] {label}: returned no tracks, trying next node …")

            except Exception as e:
                print(f"[Music] {label}: search error — {e}")
                continue

        return None

    async def display_player_embed(self, player, track, ctx, autoplay=False):
        sec      = track.length // 1000
        duration = f"0{sec // 60}:{sec % 60:02d}" if sec < 600 else f"{sec // 60}:{sec % 60:02d}"
        _src     = track.source if track.source else ""

        color = (
            0x1DB954 if "spotify" in _src else
            0xFF5500
        )

        embed = discord.Embed(title=f"**{track.title}**", color=color)
        embed.add_field(name="Author",   value=f"`{track.author}`")
        embed.add_field(name="Duration", value=f"`{duration}`")

        # Source link — emoji placed BEFORE the hyperlink so it renders as a real emoji
        _src_txt = f"{_e('zplay') or '▶'}  [Listen on Spotify]({track.uri})"
        embed.add_field(name="Source", value=_src_txt)

        # Thumbnail = song artwork (replaces the old composite banner image)
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        embed.set_footer(
            text="Requested by " + (ctx.author.display_name if not autoplay else f"{ctx.author.display_name} (Autoplay Mode)"),
            icon_url=ctx.author.display_avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
        )

        await ctx.send(embed=embed, view=MusicControlView(player, ctx))


    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        """Track started: log, fix volume, update VC status, record history."""
        player   = payload.player
        track    = player.current
        guild_id = player.guild.id

        print(f"[Music] Track started: {track.title}")
        # Ensure volume is audible — Lavalink defaults to 100 but be explicit
        if player.volume != 100:
            await player.set_volume(100)

        # Update VC status
        voice_channel = player.channel
        if voice_channel:
            try:
                await voice_channel.edit(status=f"🎵 Playing: {track.title}")
            except Exception:
                pass

        # Update track history (used by Previous button in music + playlist)
        if guild_id not in track_histories:
            track_histories[guild_id] = []
        if not track_histories[guild_id] or track_histories[guild_id][-1] != track:
            track_histories[guild_id].append(track)
            if len(track_histories[guild_id]) > 10:
                track_histories[guild_id].pop(0)

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload) -> None:
        """When a Spotify-resolved track fails to stream, log it and tell the user."""
        player = payload.player
        exc    = payload.exception
        title  = payload.track.title
        print(f"[Music] Track exception on '{title}': {exc}")
        ctx = getattr(player, "ctx", None)

        if ctx:
            try:
                await ctx.send(embed=discord.Embed(
                    description=(
                        f"⚠️ Could not play **{title}**.\n"
                        "Try a different Spotify track or check the Lavalink server."
                    ),
                    color=0xFF0000,
                ))
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload) -> None:
        """Handle a stuck track by skipping it."""
        player = payload.player
        print(f"[Music] Track stuck: {payload.track.title}")
        ctx = getattr(player, "ctx", None)
        if ctx:
            try:
                await ctx.send(embed=discord.Embed(
                    description=f"⚠️ Track **{payload.track.title}** got stuck and was skipped.",
                    color=0xFF0000,
                ))
            except Exception:
                pass
        if not player.queue.is_empty:
            next_track = await player.queue.get_wait()
            await player.play(next_track)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player

        # If a playlist restart is in progress, skip normal end-of-track logic
        # so the fresh re-queue can take over without triggering a disconnect.
        if getattr(player, '_playlist_restarting', False):
            return

        # Clear VC status when a track ends
        if player.channel:
            try:
                await player.channel.edit(status=None)
            except Exception:
                pass

        # Queue progression
        if player.queue.is_empty:
            if player.queue.mode == wavelink.QueueMode.loop:
                await player.play(payload.track)
            elif player.autoplay == wavelink.AutoPlayMode.enabled:
                await asyncio.sleep(5)
                if player.current:
                    try:
                        await self.display_player_embed(player, player.current, player.ctx, autoplay=True)
                    except Exception:
                        pass
                else:
                    try:
                        await player.ctx.send("No suitable track found for autoplay.")
                    except Exception:
                        pass
            else:
                try:
                    await player.disconnect()
                except Exception:
                    pass
                ended = discord.Embed(description="All tracks have been played, leaving the voice channel.", color=0xFF0000)
                ended.set_author(name="Queue Ended", icon_url=self.client.user.display_avatar.url)
                try:
                    await player.ctx.send(embed=ended)
                except Exception:
                    pass
        else:
            next_track = await player.queue.get_wait()
            await player.play(next_track)
            # Wrap in try/except — ctx may be a lightweight proxy (e.g. from playlist.py)
            # that doesn't have every method a real Context has; playback must not stop.
            try:
                await self.display_player_embed(player, next_track, player.ctx)
            except Exception:
                pass



    async def play_source(self, ctx, query):
        if not ctx.author.voice:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in a voice channel to use this command.", color=0xFF0000))
            return

        # Guard: make sure at least one Lavalink node is available
        try:
            nodes = wavelink.Pool.nodes
            if not nodes:
                raise RuntimeError("no nodes")
        except Exception:
            await ctx.send(embed=discord.Embed(
                description="⚠️ Music is currently unavailable — Lavalink node not connected. Please try again in a moment.",
                color=0xFF0000,
            ))
            return

        try:
            vc = ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player)
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"⚠️ Could not join your voice channel: {e}", color=0xFF0000))
            return

        vc.ctx = ctx

        # Guarantee the player is audible — Lavalink defaults to 100 but some
        # nodes or reconnect paths can reset it. Set explicitly on every play.
        if vc.volume != 100:
            await vc.set_volume(100)

        if vc.playing:
            if ctx.voice_client and ctx.voice_client.channel != ctx.author.voice.channel:
                await ctx.send(embed=discord.Embed(description=f"You must be connected to {ctx.voice_client.channel.mention} to play.", color=0xFF0000))
                return
        vc.autoplay = wavelink.AutoPlayMode.disabled

        # Spotify-only mode: plain text queries are searched with spsearch, and
        # Spotify URLs are passed straight to Lavalink so LavaSrc resolves them.
        is_spotify_url = bool(
            re.search(SPOTIFY_TRACK_REGEX, query) or
            re.search(SPOTIFY_PLAYLIST_REGEX, query) or
            re.search(SPOTIFY_ALBUM_REGEX, query)
        )

        # Try every configured node in priority order until one returns tracks.
        tracks = await self._search_with_failover(query, is_spotify_url)

        if not tracks:
            await ctx.send(embed=discord.Embed(
                description=(
                    "❌ No results found.\n"
                    "All Lavalink nodes failed to resolve this track — "
                    "they may be temporarily unavailable or the track doesn't exist."
                ),
                color=0xFF0000,
            ))
            return

        if isinstance(tracks, wavelink.Playlist):
            await vc.queue.put_wait(tracks.tracks)
            await ctx.send(embed=discord.Embed(description=f"➕ Added playlist **{tracks.name}** with **{len(tracks.tracks)} songs** to the queue.", color=0xFF0000))
            if not vc.playing:
                track = await vc.queue.get_wait()
                await vc.play(track)
                await self.display_player_embed(vc, track, ctx)
        else:
            track = tracks[0]
            await vc.queue.put_wait(track)
            if not vc.playing:
                await vc.play(await vc.queue.get_wait())
                await self.display_player_embed(vc, track, ctx)
            else:
                queue_pos = len(vc.queue)
                await ctx.send(embed=discord.Embed(
                    description=f"➕ Added **{track.title}** to the queue  `#{queue_pos}`",
                    color=0x1DB954,
                ))
            self.client.loop.create_task(self.check_inactivity(ctx.guild.id))


    def create_progress_bar(self, completed, total, length=10):
        filled_length = int(length * (completed / total))
        bar = '█' * filled_length + '░' * (length - filled_length)
        return bar

    @commands.hybrid_command(name="play", aliases=['p'], usage="play <query>", help="Plays a Spotify song or playlist.")
    @discord.app_commands.describe(query="A Spotify song/playlist/album link, or a search query.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def play(self, ctx: commands.Context, *, query: str):
        # Defer immediately when invoked as slash command — Lavalink search can
        # take several seconds and Discord's 3-second interaction timeout fires
        # before we respond, causing "application did not respond".
        if ctx.interaction:
            await ctx.defer()
        await self.play_source(ctx, query)


    @commands.command(name="search", usage="search <query>", help="Searches music from Spotify.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def search2(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in a voice channel to use this command.", color=0xFF0000))
            return

        embed = discord.Embed(
            title="Spotify Search",
            description="Searching Spotify for your query. (Spotify needs SPOTIFY_CLIENT_ID/SECRET set on the Lavalink server.)",
            color=0xff0000
        )
        await ctx.send(embed=embed, view=PlatformSelectView(ctx, query))


    @commands.command(name="nowplaying", aliases=["nop"], usage="nowplaying", help="Shows the info about current playing song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def nowplaying(self, ctx: commands.Context):
        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="No song is currently playing.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        track = vc.current
        position = vc.position / 1000  
        length = track.length / 1000  

        progress_bar = self.create_progress_bar(position, length, length=10)
        position_str = f"{int(position // 60)}:{int(position % 60):02}"
        length_str = f"{int(length // 60)}:{int(length % 60):02}"


        queue_length = len(vc.queue) if vc.queue else 0


        if "spotify" in track.uri:
            source_name = "Spotify"
        else:
            source_name = "Music"


        embed = discord.Embed(
            title="Now Playing",
            color=0x1DB954 if source_name == "Spotify" else 0xFF0000
        )
        embed.add_field(name="Track", value=f"[{track.title}]({track.uri})", inline=False)
        embed.add_field(name="Song By", value=track.author, inline=False)
        embed.add_field(name="Progress", value=f"{position_str} [{progress_bar}] {length_str}", inline=False)
        embed.add_field(name="Duration", value=length_str, inline=False)
        embed.add_field(name="Queue Length", value=str(queue_length), inline=False)
        embed.add_field(name="Source", value=f"{source_name} - [Link]({track.uri})", inline=False)
        embed.set_thumbnail(url=track.artwork if track.artwork else "")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.send(embed=embed)

    @commands.command(name="autoplay", usage="autoplay", help="Toggles autoplay mode.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def autoplay(self, ctx: commands.Context):
        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="⚠️ No song is currently playing.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc:
            vc.autoplay = (
                wavelink.AutoPlayMode.enabled if vc.autoplay != wavelink.AutoPlayMode.enabled else wavelink.AutoPlayMode.disabled
            )
            await ctx.send(embed=discord.Embed(description=f"✅ Autoplay {'enabled' if vc.autoplay == wavelink.AutoPlayMode.enabled else 'disabled'} by {ctx.author.mention}.", color=0xFF0000))

    @commands.command(name="loop", usage="loop", help="Toggles loop mode.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def loop(self, ctx: commands.Context):
        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="⚠️ No song is currently playing.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc:
            vc.queue.mode = wavelink.QueueMode.loop if vc.queue.mode != wavelink.QueueMode.loop else wavelink.QueueMode.normal
            await ctx.send(embed=discord.Embed(description=f"✅ Loop {'enabled' if vc.queue.mode == wavelink.QueueMode.loop else 'disabled'} by {ctx.author.mention}.", color=0xFF0000))
        else:
            await ctx.send(embed=discord.Embed(description="I'm not connected to a voice channel.", color=0xFF0000))


    @commands.command(name="pause", usage="pause", help="Pauses the current song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pause(self, ctx: commands.Context):
        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="⚠️ No song is currently playing.", color=0x000000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc and vc.playing and not vc.paused:
            await vc.pause(True)
            await vc.channel.edit(status=f"⏸️ Paused: {vc.current.title}")
            await ctx.send(embed=discord.Embed(description=f"Paused by {ctx.author.mention}.", color=0x000000))
        else:
            await ctx.send(embed=discord.Embed(description="⚠️   Nothing is playing or already paused.", color=0xFF0000))

    @commands.command(name="resume", usage="resume", help="Resumes the paused song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def resume(self, ctx: commands.Context):
        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="⚠️ No song is currently playing.", color=0x000000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc and vc.paused:
            await vc.pause(False)
            await vc.channel.edit(status=f"🎵 Playing: {vc.current.title}")
            await ctx.send(embed=discord.Embed(description=f"Resumed by {ctx.author.mention}.", color=0xFF0000))
        else:
            await ctx.send(embed=discord.Embed(description="Player is not paused.", color=0xFF0000))

    @commands.command(name="skip", usage="skip", help="Skips the current song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def skip(self, ctx: commands.Context):
        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="No song is currently playing.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc.autoplay == wavelink.AutoPlayMode.enabled:
            await vc.stop()
            return await ctx.send(embed=discord.Embed(description=f"Skipped by {ctx.author.mention}.", color=0xFF0000))


        if vc and vc.playing and not vc.queue.is_empty:
            await vc.stop()
            await ctx.send(embed=discord.Embed(description=f"Skipped by {ctx.author.mention}.", color=0xFF0000))
        else:
            await ctx.send(embed=discord.Embed(description="⚠️ No song is playing or in the queue to skip.", color=0xFF0000))

    @commands.command(name="shuffle", usage="shuffle", help="Shuffles the queue.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def shuffle(self, ctx: commands.Context):
        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="⚠️  No song is currently playing.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc and vc.queue:
            random.shuffle(vc.queue)
            await ctx.send(embed=discord.Embed(description=f"Queue shuffled by {ctx.author.mention}.", color=0xFF0000))
        else:
            await ctx.send(embed=discord.Embed(description="Queue is empty.", color=0xFF0000))

    @commands.hybrid_command(name="stop", usage="stop", help="Stops the current song and clears the queue.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def stop(self, ctx: commands.Context):
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="⚠️ No song is currently playing.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc and player:
            await vc.channel.edit(status=None)
            vc.queue.clear()
            await vc.disconnect(force=True)
            await ctx.send(embed=discord.Embed(description=f"Stopped and queue cleared by {ctx.author.mention}.", color=0xFF0000))
        else:
            await ctx.send(embed=discord.Embed(description="Nothing is playing to stop.", color=0xFF0000))

    @commands.command(name="volume", aliases=["vol"], usage="volume <level>", help="Sets the volume of the player.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def volume(self, ctx: commands.Context, level: int):
        vc = ctx.voice_client

        if not vc:
            await ctx.send(embed=discord.Embed(description="⚠️ I'm not connected to a voice channel.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc:
            if 1 <= level <= 150:
                await vc.set_volume(level)
                await ctx.send(embed=discord.Embed(description=f"🔇 Volume set to {level}% by {ctx.author.mention}.", color=0xFF0000))
            else:
                await ctx.send(embed=discord.Embed(description="⚠️ Volume must be between 1 and 150.", color=0xFF0000))
        else:
            await ctx.send(embed=discord.Embed(description="Bot is not connected to a voice channel.", color=0xFF0000))

    @commands.command(name="queue", usage="queue", help="Shows the current queue.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def queue(self, ctx: commands.Context):
        vc = ctx.voice_client

        if not vc or not vc.queue or vc.queue.is_empty:
            await ctx.send(embed=discord.Embed(description="⚠️ The queue is currently empty.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ you need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return


        entries = [f"{index + 1}. [{track.title} - {track.author}]({track.uri})" for index, track in enumerate(vc.queue)]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title="Current Queue",
            description="List of upcoming songs.",
            per_page=10,
            color=0xFF0000),
            ctx=ctx)
        await paginator.paginate()

    @commands.command(name="clearqueue", usage="clearqueue", help="Clears the queue.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def clearqueue(self, ctx: commands.Context):
        vc = ctx.voice_client

        if not vc or not vc.queue or vc.queue.is_empty:
            await ctx.send(embed=discord.Embed(description="⚠️ No Queue to clear.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc and vc.queue:
            vc.queue.clear()
            await ctx.send(embed=discord.Embed(description="Queue has been cleared.", color=0x1DB954))
        else:
            await ctx.send(embed=discord.Embed(description="No queue to clear.", color=0xFF0000))

    @commands.command(name="replay", usage="replay", help="Replays the current song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def replay(self, ctx: commands.Context):
        vc = ctx.voice_client

        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="⚠️ I'm not connected to any voice channel.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc and vc.playing:
            await vc.seek(0)
            await ctx.send(embed=discord.Embed(description="Replaying the current track.", color=0x1DB954))
        else:
            await ctx.send(embed=discord.Embed(description="No track is currently playing.", color=0xFF0000))

    @commands.command(name="join", aliases=["connect"], usage="join", help="Joins the voice channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def join(self, ctx: commands.Context):
        if ctx.author.voice:
            await ctx.author.voice.channel.connect(cls=wavelink.Player)
            await ctx.send(embed=discord.Embed(description="Joined the voice channel.", color=0x1DB954))
        else:
            await ctx.send(embed=discord.Embed(description="You need to join a voice channel first.", color=0xFF0000))

    @commands.command(name="disconnect", aliases=["dc", "leave"], usage="disconnect", help="Disconnects the bot from the voice channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def disconnect(self, ctx: commands.Context):
        vc = ctx.voice_client
        if not vc:
            await ctx.send(embed=discord.Embed(description="⚠️  I'm not connected to any voice channel.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        if vc:
            await vc.disconnect()
            await ctx.send(embed=discord.Embed(description="Disconnected from the voice channel.", color=0x1DB954))
        else:
            await ctx.send(embed=discord.Embed(description="Bot is not connected to any voice channel.", color=0xFF0000))

    @commands.hybrid_command(name="lavalink", usage="lavalink", help="Shows all configured Lavalink nodes with connection and playback status.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def lavalink_info(self, ctx: commands.Context):
        """
        Shows every configured Lavalink node in priority order.
        For each node: WebSocket status, REST reachability, live stats, and
        when it last successfully resolved a search for this bot.
        """
        # Defer immediately so Discord doesn't time out while we ping nodes.
        if ctx.interaction:
            await ctx.defer()

        # ── Gather configured nodes ──────────────────────────────────────────
        cfg_nodes = self._configured_nodes  # [{index, uri, password}]

        # Also include any pool nodes that aren't in _configured_nodes
        # (can happen if nodes were added dynamically or config was reloaded).
        pool: dict = {}
        try:
            pool = wavelink.Pool.nodes or {}
        except Exception:
            pool = {}

        # Build a pool lookup by URI  →  wavelink Node
        pool_by_uri: dict[str, "wavelink.Node"] = {}
        for node in pool.values():
            pool_by_uri[node.uri] = node

        # Merge: all configured + any extra pool nodes not in config
        all_uris_ordered: list[tuple[int, str, str]] = [
            (c["index"], c["uri"], c["password"]) for c in cfg_nodes
        ]
        configured_uris = {c["uri"] for c in cfg_nodes}
        extra_idx = len(cfg_nodes) + 1
        for node in pool.values():
            if node.uri not in configured_uris:
                all_uris_ordered.append((extra_idx, node.uri, ""))
                extra_idx += 1

        if not all_uris_ordered:
            await ctx.send(embed=discord.Embed(
                description="❌ No Lavalink nodes are configured. Set `LAVALINK_URL` (or `LAVALINK_URL_1`, `LAVALINK_URL_2` …) in your environment.",
                color=0xFF0000,
            ))
            return

        # ── Ping every node's REST API in parallel ───────────────────────────
        async def _rest_ping(uri: str, password: str) -> bool:
            """Returns True if the node responds to GET /v4/info within 4 s."""
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        f"{uri}/v4/info",
                        headers={"Authorization": password or "youshallnotpass"},
                        timeout=aiohttp.ClientTimeout(total=4),
                    ) as r:
                        return r.status < 500
            except Exception:
                return False

        ping_tasks = [_rest_ping(uri, pw) for _, uri, pw in all_uris_ordered]
        rest_results: list[bool] = list(await asyncio.gather(*ping_tasks, return_exceptions=False))

        # ── Build embed ───────────────────────────────────────────────────────
        now = datetime.datetime.utcnow()
        embed = discord.Embed(
            title="🎵 Lavalink Nodes",
            description=(
                f"**{len(all_uris_ordered)}** node(s) configured · "
                f"nodes are tried in priority order (#1 first) when you play a track."
            ),
            color=0x1DB954,
        )

        for i, ((idx, uri, pw), rest_ok) in enumerate(zip(all_uris_ordered, rest_results)):
            wl_node = pool_by_uri.get(uri)

            # WebSocket connection status
            ws_connected = False
            if wl_node is not None:
                try:
                    ws_connected = wl_node.status == wavelink.NodeStatus.CONNECTED
                except Exception:
                    ws_connected = getattr(wl_node, "connected", True)

            ws_icon   = "🟢" if ws_connected  else "🔴"
            rest_icon = "✅" if rest_ok        else "❌"

            lines = [
                f"`{uri}`",
                f"{ws_icon} **WebSocket** {'Connected' if ws_connected else 'Disconnected'} · "
                f"{rest_icon} **REST** {'Reachable' if rest_ok else 'Unreachable'}",
            ]

            # Live stats (only if WebSocket is connected and stats arrived)
            if ws_connected and wl_node is not None:
                try:
                    stats = wl_node.stats
                    if stats:
                        mem_mb   = stats.memory.used // (1024 * 1024)
                        up_s     = stats.uptime // 1000
                        h, r     = divmod(up_s, 3600)
                        m, s     = divmod(r, 60)
                        cpu      = stats.cpu.lavalink_load * 100
                        playing  = stats.playing_players
                        total_p  = stats.players
                        lines.append(
                            f"🎵 **{playing}** playing / **{total_p}** total · "
                            f"💾 **{mem_mb} MB** · 🖥️ **{cpu:.1f}%** · ⏱️ {h}h {m}m {s}s"
                        )
                except Exception:
                    pass

            # Last successful search on this node
            last = self._node_last_success.get(uri)
            if last:
                delta   = now - last
                mins    = int(delta.total_seconds() // 60)
                ago_str = f"{mins}m ago" if mins < 60 else f"{mins // 60}h {mins % 60}m ago"
                lines.append(f"🔍 **Last search:** {ago_str}")
            else:
                lines.append("🔍 **Last search:** not yet used this session")

            field_name = f"#{idx}  {'(priority)' if idx == 1 else ''}"
            embed.add_field(
                name=field_name.strip(),
                value="\n".join(lines),
                inline=False,
            )

        connected_count = sum(
            1 for _, uri, _ in all_uris_ordered
            if pool_by_uri.get(uri) is not None
               and getattr(pool_by_uri[uri], "status", None) == wavelink.NodeStatus.CONNECTED
        )
        embed.set_footer(text=f"{connected_count}/{len(all_uris_ordered)} nodes connected via WebSocket")
        await ctx.send(embed=embed)

    @commands.command(name="seek", usage="seek <percentage>", help="Seeks to a specific percentage of the song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def seek(self, ctx: commands.Context, percentage: int):
        if not 1 <= percentage <= 100:
            await ctx.send(embed=discord.Embed(description="Please provide a percentage between 1 and 100.", color=0xFF0000))
            return

        vc = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send(embed=discord.Embed(description="No song is currently playing.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        track = vc.current
        target_position = int(track.length * (percentage / 100))  
        await vc.seek(target_position)

        await ctx.send(embed=discord.Embed(description=f"Seeked to {percentage}% of the current track.", color=0x1DB954))

    # NOTE: on_wavelink_track_start and on_wavelink_track_end are defined earlier
    # in this class (single merged implementations). Duplicate definitions were
    # removed — Python silently overwrites the first with the second, so keeping
    # two methods with the same name means the first (with the full logic) is lost.