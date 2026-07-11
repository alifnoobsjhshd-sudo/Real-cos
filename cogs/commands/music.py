import os
import random
import discord
from discord.ext import commands, tasks
import datetime
from discord.ui import Button, View
import wavelink
from wavelink.enums import TrackSource
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
            ("YouTube",   "ytsearch", discord.ButtonStyle.red,   _pe("YouTube")),
            ("JioSaavn",  "jssearch", discord.ButtonStyle.green,  _pe("jiosaavn")),
            ("SoundCloud","scsearch", discord.ButtonStyle.grey,   _pe("SoundCloud")),
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
        # Wrap initial connect in a silent helper so a startup failure is only
        # logged, not an unhandled task exception. connect_nodes() itself now
        # re-raises so the reconnect loop can detect genuine failures.
        async def _initial_connect():
            try:
                await self.connect_nodes()
            except Exception:
                pass
        self.client.loop.create_task(_initial_connect())
        self.client.loop.create_task(self.monitor_inactivity())
        
        self.inactivity_timeout = 120 
        self.player_inactivity = {}  

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
        if len(guild.voice_channels[0].members) == 1:
            player = None
            for vc in self.client.voice_clients:
                if vc.guild.id == guild.id:
                    player = vc
                    break
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

    async def connect_nodes(self) -> None:
        """
        Connect to the configured Lavalink node.
        Raises on failure so callers (e.g. the reconnect loop) can detect
        genuine connection errors. The startup wrapper catches and silences
        the initial attempt.
        """
        lavalink_uri = os.getenv("LAVALINK_URI", "https://lava-v4.ajieblogs.eu.org")
        lavalink_pass = os.getenv("LAVALINK_PASSWORD", "https://dsc.gg/ajidevserver")
        if lavalink_uri and not lavalink_uri.startswith(("http://", "https://", "ws://", "wss://")):
            # Public nodes are usually HTTPS; self-hosted with a port is usually plain HTTP.
            scheme = "http://" if ":" in lavalink_uri else "https://"
            lavalink_uri = f"{scheme}{lavalink_uri}"
        nodes = [wavelink.Node(uri=lavalink_uri, password=lavalink_pass)]
        # Let the exception propagate — callers decide how to handle it.
        await wavelink.Pool.connect(nodes=nodes, client=self.client, cache_capacity=None)
        print(f"[Music] Connected to Lavalink node: {lavalink_uri}")

    @commands.Cog.listener()
    async def on_wavelink_node_disconnected(self, payload) -> None:
        """Reconnect to Lavalink automatically when the node drops."""
        print(f"[Music] Lavalink node disconnected — will retry in 15 s …")
        for attempt in range(1, 6):
            await asyncio.sleep(15)
            try:
                await self.connect_nodes()
                print(f"[Music] Lavalink reconnected on attempt {attempt}.")
                return
            except Exception as e:
                print(f"[Music] Reconnect attempt {attempt} failed: {e}")
        print("[Music] Could not reconnect to Lavalink after 5 attempts.")




    async def display_player_embed(self, player, track, ctx, autoplay=False):
        sec      = track.length // 1000
        duration = f"0{sec // 60}:{sec % 60:02d}" if sec < 600 else f"{sec // 60}:{sec % 60:02d}"
        _src     = track.source if track.source else ""

        color = (
            0x1DB954 if "spotify"    in _src else
            0x00E6A7 if "jiosaavn"   in _src else
            0xFF0000 if "youtube"    in _src else
            0xFF5500
        )

        embed = discord.Embed(title=f"**{track.title}**", color=color)
        embed.add_field(name="Author",   value=f"`{track.author}`")
        embed.add_field(name="Duration", value=f"`{duration}`")

        # Source link — emoji placed BEFORE the hyperlink so it renders as a real emoji
        if "spotify"     in _src: _src_txt = f"{_e('zplay') or '▶'}  [Listen on Spotify]({track.uri})"
        elif "jiosaavn"  in _src: _src_txt = f"{_e('jiosaavn') or '🎵'} [Listen on JioSaavn]({track.uri})"
        elif "soundcloud" in _src: _src_txt = f"{_e('SoundCloud') or '☁'} [Listen on SoundCloud]({track.uri})"
        else:                     _src_txt = f"{_e('YouTube') or '▶'} [Listen on YouTube]({track.uri})"
        embed.add_field(name="Source", value=_src_txt)

        # Thumbnail = song artwork (replaces the old composite banner image)
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        embed.set_footer(
            text="Requested by " + (ctx.author.display_name if not autoplay else f"{ctx.author.display_name} (Autoplay Mode)"),
            icon_url=ctx.author.display_avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
        )

        await ctx.send(embed=embed, view=MusicControlView(player, ctx))


    async def on_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player.queue:
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

        if vc.playing:
            if ctx.voice_client and ctx.voice_client.channel != ctx.author.voice.channel:
                await ctx.send(embed=discord.Embed(description=f"You must be connected to {ctx.voice_client.channel.mention} to play.", color=0xFF0000))
                return
        vc.autoplay = wavelink.AutoPlayMode.disabled

        try:
            tracks = await wavelink.Playable.search(query)
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"⚠️ Search failed: `{e}`\nThe music node may be temporarily unavailable.",
                color=0xFF0000,
            ))
            return

        if not tracks:
            await ctx.send(embed=discord.Embed(description="No results found for that query.", color=0xFF0000))
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
            await ctx.send(embed=discord.Embed(description=f"➕ Added **{track.title}** to the queue.", color=0xFF0000))
            if not vc.playing:
                await vc.play(await vc.queue.get_wait())
                await self.display_player_embed(vc, track, ctx)
            self.client.loop.create_task(self.check_inactivity(ctx.guild.id))


    
    async def handle_spotify_link(self, ctx, vc, link, type_):
        try:
            if type_ == "track":
                track_id = re.search(SPOTIFY_TRACK_REGEX, link).group(1)
                track_info = await spotify_api.get_track(track_id)

                
                title = track_info['name']
                author = ', '.join(artist['name'] for artist in track_info['artists'])

                
                search_query = f"{title} by {author}"
                search_results = await wavelink.Playable.search(search_query, source=wavelink.enums.TrackSource.YouTube)

                if not search_results:
                    await ctx.send("Can't play this track from Spotify, please try with another track.")
                    return

                track = search_results[0]
                await vc.queue.put_wait(track)
                await ctx.send(embed=discord.Embed(description=f"➕  Added [{track.title}](https://discord.gg/codexdev) to the queue.", color=0xFF0000))
                if not vc.playing:
                    await vc.play(track)
                    await self.display_player_embed(vc, track, ctx)

                #await self.display_player_embed(vc, track, ctx)
                
            elif type_ == "playlist":
                lmao = await ctx.send("⏳ Processing to add tracks from the playlist, this may take a while...")
                
                playlist_id = re.search(SPOTIFY_PLAYLIST_REGEX, link).group(1)
                playlist_info = await spotify_api.get(f"playlists/{playlist_id}")
                tracks = playlist_info.get("tracks", {}).get("items", [])
                playlist_length = len(tracks)

                if not tracks:
                    await ctx.send("No tracks found in the playlist.")
                    return

                c = 0
                for track in tracks:
                    title = track['track']['name']
                    author = ', '.join(artist['name'] for artist in track['track']['artists'])
                    search_query = f"{title} {author}"

                    track_results = await wavelink.Playable.search(search_query, source=wavelink.enums.TrackSource.YouTube)
                    if track_results:
                        await vc.queue.put_wait(track_results[0])
                        c += 1
                        await ctx.message.add_reaction("✅")

                await ctx.send(embed=discord.Embed(description=f"➕ Added **{c}** of **{playlist_length}** tracks from **playlist** **[{playlist_info['name']}](https://discord.gg/codexdev)** to the queue.", color=0xFF0000))
                await lmao.delete()
                
                if not vc.playing:
                    next_track = await vc.queue.get_wait()
                    await vc.play(next_track)
                    await self.display_player_embed(vc, next_track, ctx)


            elif type_ == "album":
                await ctx.message.add_reaction("⌛")
                album_id = re.search(SPOTIFY_ALBUM_REGEX, link).group(1)
                album_info = await spotify_api.get(f"albums/{album_id}")
                tracks = album_info.get("tracks", {}).get("items", [])

                if not tracks:
                    await ctx.send("No tracks found in the album.")
                    return

                for track in tracks:
                    title = track['name']
                    author = ', '.join(artist['name'] for artist in track['artists'])
                    search_query = f"{title} {author}"

                    track_results = await wavelink.Playable.search(search_query, source=wavelink.enums.TrackSource.YouTube)
                    if track_results:
                        await vc.queue.put_wait(track_results[0])

                await ctx.send(embed=discord.Embed(description=f"➕ Added all tracks from album **[{album_info['name']}](https://discord.gg/codexdev)** to the queue.", color=0xFF0000))
                if not vc.playing:
                    next_track = await vc.queue.get_wait()
                    await vc.play(next_track)
                    await self.display_player_embed(vc, next_track, ctx)

                
        except Exception as e:
            await ctx.send(f"An error occurred while processing the Spotify link: {e}")



    def create_progress_bar(self, completed, total, length=10):
        filled_length = int(length * (completed / total))
        bar = '█' * filled_length + '░' * (length - filled_length)
        return bar

    @commands.hybrid_command(name="play", aliases=['p'], usage="play <query>", help="Plays a song or playlist.")
    @discord.app_commands.describe(query="A song name, YouTube/Spotify/SoundCloud link, or playlist link.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def play(self, ctx: commands.Context, *, query: str):
        
        await self.play_source(ctx, query)


    @commands.command(name="search", usage="search <query>", help="Searches music from multiple platforms.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def search2(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            await ctx.send(embed=discord.Embed(description="⚠️ You need to be in a voice channel to use this command.", color=0xFF0000))
            return

        embed = discord.Embed(
            title="Select a platform to search from:",
            description="Click a button below to choose.",
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
        elif "youtube" in track.uri:
            source_name = "YouTube"
        elif "soundcloud" in track.uri:
            source_name = "SoundCloud"
        elif "jiosaavn" in track.uri:
            source_name = "JioSaavn"
        else:
            source_name = "Unknown Source"


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

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player = payload.player
        track = player.current
        guild_id = player.guild.id

        voice_channel = player.channel
        if voice_channel:
            await voice_channel.edit(status=f"🎵 Playing: {track.title}")  # type: ignore

        if guild_id not in track_histories:
            track_histories[guild_id] = []

        if not track_histories[guild_id] or track_histories[guild_id][-1] != track:
            track_histories[guild_id].append(track)


            if len(track_histories[guild_id]) > 10:
                track_histories[guild_id].pop(0)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        voice_channel = player.channel

        if voice_channel:
            await voice_channel.edit(status=None)  # type: ignore
        await self.on_track_end(payload)