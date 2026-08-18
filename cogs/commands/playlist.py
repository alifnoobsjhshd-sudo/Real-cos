"""
cogs/commands/playlist.py — Global playlist system for Zyrox X bot.

Commands:
  /playlist list                — browse all playlists
  /playlist create <name>       — create a personal playlist
  /playlist delete <name>       — delete one of your playlists
  /song add <playlist> <song>   — add a song to one of your playlists
  /song remove <playlist> <song>— remove a song from one of your playlists
"""

from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import wavelink
from datetime import datetime
from typing import Optional

from core import Cog, zyrox, Context
from utils.Tools import blacklist_check, ignore_check
from utils.emojis import e as _e

DB_PATH = "db/playlist.db"

# ── Emoji helper (same pattern as music.py) ───────────────────────────────────
def _pe(name: str, fallback: str = "") -> Optional[discord.PartialEmoji]:
    s = _e(name)
    try:
        if s:
            return discord.PartialEmoji.from_str(s)
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════════════════════════════════════

class PlaylistDB:
    """Thin async wrapper around the playlist SQLite database."""

    @staticmethod
    def _conn() -> aiosqlite.Connection:
        """Open a connection with WAL mode and foreign-key enforcement enabled."""
        return aiosqlite.connect(DB_PATH)

    async def _setup(self, db: aiosqlite.Connection):
        """Apply per-connection PRAGMAs (called at the start of every method)."""
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

    async def init(self):
        async with self._conn() as db:
            await self._setup(db)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    TEXT    NOT NULL,
                    name       TEXT    NOT NULL,
                    created_at TEXT    NOT NULL,
                    visibility TEXT    NOT NULL DEFAULT 'public',
                    UNIQUE(user_id, name)
                )
            """)
            # Migrate older databases that lack the visibility column
            try:
                await db.execute("ALTER TABLE playlists ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'")
            except Exception:
                pass
            await db.execute("""
                CREATE TABLE IF NOT EXISTS playlist_songs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    song_name   TEXT    NOT NULL,
                    song_uri    TEXT    NOT NULL,
                    position    INTEGER NOT NULL DEFAULT 0,
                    added_at    TEXT    NOT NULL,
                    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
                )
            """)
            await db.commit()

    async def create_playlist(self, user_id: int, name: str, visibility: str = "public") -> bool:
        vis = visibility if visibility in ("public", "private") else "public"
        try:
            async with self._conn() as db:
                await self._setup(db)
                await db.execute(
                    "INSERT INTO playlists (user_id, name, created_at, visibility) VALUES (?, ?, ?, ?)",
                    (str(user_id), name, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), vis)
                )
                await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def delete_playlist(self, user_id: int, name: str) -> bool:
        async with self._conn() as db:
            await self._setup(db)
            # Explicit child-row delete as belt-and-suspenders (FK cascade handles it too)
            await db.execute(
                "DELETE FROM playlist_songs WHERE playlist_id IN "
                "(SELECT id FROM playlists WHERE user_id = ? AND name = ?)",
                (str(user_id), name)
            )
            cur = await db.execute(
                "DELETE FROM playlists WHERE user_id = ? AND name = ?",
                (str(user_id), name)
            )
            await db.commit()
            return cur.rowcount > 0

    async def get_user_playlists(self, user_id: int) -> list:
        async with self._conn() as db:
            await self._setup(db)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT p.id, p.name, p.created_at, p.visibility, COUNT(s.id) AS song_count "
                "FROM playlists p LEFT JOIN playlist_songs s ON s.playlist_id = p.id "
                "WHERE p.user_id = ? GROUP BY p.id ORDER BY p.name COLLATE NOCASE",
                (str(user_id),)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def get_all_playlists(self, search: str = None, viewer_id: int = None) -> list:
        """Return playlists visible to viewer_id: all public + viewer's own private."""
        async with self._conn() as db:
            await self._setup(db)
            db.row_factory = aiosqlite.Row
            query = (
                "SELECT p.id, p.user_id, p.name, p.created_at, p.visibility, COUNT(s.id) AS song_count "
                "FROM playlists p LEFT JOIN playlist_songs s ON s.playlist_id = p.id "
            )
            conditions: list[str] = []
            args: list = []
            if viewer_id is not None:
                conditions.append("(p.visibility = 'public' OR p.user_id = ?)")
                args.append(str(viewer_id))
            if search:
                conditions.append("LOWER(p.name) LIKE ?")
                args.append(f"%{search.lower()}%")
            if conditions:
                query += "WHERE " + " AND ".join(conditions) + " "
            query += "GROUP BY p.id ORDER BY p.name COLLATE NOCASE"
            async with db.execute(query, args) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def get_playlist_by_owner_name(self, user_id: int, name: str) -> Optional[dict]:
        async with self._conn() as db:
            await self._setup(db)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, user_id, name, created_at FROM playlists WHERE user_id = ? AND name = ?",
                (str(user_id), name)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_playlist_by_id(self, playlist_id: int) -> Optional[dict]:
        async with self._conn() as db:
            await self._setup(db)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT p.id, p.user_id, p.name, p.created_at, p.visibility, COUNT(s.id) AS song_count "
                "FROM playlists p LEFT JOIN playlist_songs s ON s.playlist_id = p.id "
                "WHERE p.id = ? GROUP BY p.id",
                (playlist_id,)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_songs(self, playlist_id: int) -> list:
        async with self._conn() as db:
            await self._setup(db)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, song_name, song_uri, position, added_at "
                "FROM playlist_songs WHERE playlist_id = ? ORDER BY position DESC, id DESC",
                (playlist_id,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def rename_playlist(self, user_id: int, playlist_id: int, new_name: str) -> bool:
        new_name = new_name.strip()[:50]
        if not new_name:
            return False
        try:
            async with self._conn() as db:
                await self._setup(db)
                cur = await db.execute(
                    "UPDATE playlists SET name = ? WHERE id = ? AND user_id = ?",
                    (new_name, playlist_id, str(user_id))
                )
                await db.commit()
                return cur.rowcount > 0
        except aiosqlite.IntegrityError:
            return False

    async def set_visibility(self, user_id: int, playlist_id: int, visibility: str) -> bool:
        vis = visibility if visibility in ("public", "private") else "public"
        async with self._conn() as db:
            await self._setup(db)
            cur = await db.execute(
                "UPDATE playlists SET visibility = ? WHERE id = ? AND user_id = ?",
                (vis, playlist_id, str(user_id))
            )
            await db.commit()
            return cur.rowcount > 0

    async def get_playlist_ids_containing_uri(self, user_id: int, song_uri: str) -> set:
        """Return set of playlist IDs (owned by user_id) that already contain song_uri."""
        async with self._conn() as db:
            await self._setup(db)
            async with db.execute(
                "SELECT ps.playlist_id FROM playlist_songs ps "
                "JOIN playlists p ON p.id = ps.playlist_id "
                "WHERE p.user_id = ? AND ps.song_uri = ?",
                (str(user_id), song_uri)
            ) as cur:
                return {row[0] for row in await cur.fetchall()}

    async def move_song(self, playlist_id: int, song_id: int, direction: str) -> bool:
        """Swap the position of song_id with the adjacent song (direction='up'/'down').

        'up' moves the song toward the top of the list (higher rank = lower index).
        Order matches get_songs() — DESC by position then id so newest is first.
        """
        async with self._conn() as db:
            await self._setup(db)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, position FROM playlist_songs WHERE playlist_id = ? ORDER BY position DESC, id DESC",
                (playlist_id,)
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]

            idx = next((i for i, r in enumerate(rows) if r["id"] == song_id), None)
            if idx is None:
                return False
            swap_idx = idx - 1 if direction == "up" else idx + 1
            if swap_idx < 0 or swap_idx >= len(rows):
                return False

            a, b = rows[idx], rows[swap_idx]
            await db.execute("UPDATE playlist_songs SET position = ? WHERE id = ?", (b["position"], a["id"]))
            await db.execute("UPDATE playlist_songs SET position = ? WHERE id = ?", (a["position"], b["id"]))
            await db.commit()
            return True

    async def add_song(self, playlist_id: int, song_name: str, song_uri: str) -> bool:
        async with self._conn() as db:
            await self._setup(db)
            async with db.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM playlist_songs WHERE playlist_id = ?",
                (playlist_id,)
            ) as cur:
                row  = await cur.fetchone()
                npos = row[0] if row else 1
            await db.execute(
                "INSERT INTO playlist_songs (playlist_id, song_name, song_uri, position, added_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (playlist_id, song_name, song_uri, npos,
                 datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            )
            await db.commit()
        return True

    async def remove_song(self, playlist_id: int, song_id: int) -> bool:
        async with self._conn() as db:
            await self._setup(db)
            cur = await db.execute(
                "DELETE FROM playlist_songs WHERE id = ? AND playlist_id = ?",
                (song_id, playlist_id)
            )
            await db.commit()
            return cur.rowcount > 0


_db = PlaylistDB()


# ════════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ════════════════════════════════════════════════════════════════════════════════

# ── Design constants (mirror music.py) ────────────────────────────────────────
COLOR_NOW_PLAYING = 0xFFD700
COLOR_CONTROL     = 0x36393F
CONFIRM_DELAY     = 2

async def _auto_delete(interaction: discord.Interaction, delay: int = CONFIRM_DELAY):
    """Schedule deletion of an ephemeral interaction response."""
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except Exception:
        pass

async def _confirm(interaction: discord.Interaction, text: str):
    """Send a brief ephemeral confirmation and auto-delete after CONFIRM_DELAY s."""
    await interaction.response.send_message(
        embed=discord.Embed(description=text, color=COLOR_NOW_PLAYING),
        ephemeral=True,
    )
    asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))


def _build_playlist_embed(
    pl: dict,
    songs: list,
    page: int = 0,
    per_page: int = 20,
    owner_name: str = "",
) -> discord.Embed:
    """Build the embed showing a playlist's details and song list."""
    vis_icon = "🔒" if pl.get("visibility") == "private" else "🌐"
    em = discord.Embed(
        title=f"{_e('zmusic') or '🎵'}  {pl['name']}  {vis_icon}",
        color=COLOR_CONTROL,
    )
    total      = len(songs)
    start      = page * per_page
    page_songs = songs[start: start + per_page]

    # Header info
    info_lines = []
    if owner_name:
        info_lines.append(f"**Owner:** {owner_name}")
    info_lines.append(f"**Songs:** {total}")
    info_lines.append(f"**Visibility:** {'Private 🔒' if pl.get('visibility') == 'private' else 'Public 🌐'}")
    em.description = "\n".join(info_lines)

    if page_songs:
        song_lines = [
            f"`{start + i + 1}.` {s['song_name']}"
            for i, s in enumerate(page_songs)
        ]
        em.add_field(name="Track List", value="\n".join(song_lines), inline=False)
    else:
        em.add_field(
            name="Track List",
            value="*No songs yet — use `/song add` to add some!*",
            inline=False,
        )

    total_pages = max(1, (total - 1) // per_page + 1) if total else 1
    em.set_footer(
        text=f"{total} song{'s' if total != 1 else ''}"
             + (f"  ·  Page {page + 1}/{total_pages}" if total > per_page else "")
    )
    return em


async def _queue_playlist_and_play(
    interaction: discord.Interaction,
    pl: dict,
    songs: list,
    start_index: int = 0,
    loop_all: bool = False,
) -> Optional[wavelink.Player]:
    """
    Join the user's VC, queue songs starting from start_index, and begin playback.
    The caller is responsible for updating the track-list message with PlaylistActiveView.
    on_wavelink_track_start (in music.py) sends the per-song NP embed automatically.
    Returns the player on success, or None on error.
    """
    if not interaction.user.voice:
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{_e('zwarning') or '⚠️'} You need to be in a voice channel.",
                color=0xFF0000,
            ),
            ephemeral=True,
        )
        return None

    songs_to_play = songs[start_index:]
    if not songs_to_play:
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{_e('zcross') or '❌'} No songs to play from that position.",
                color=0xFF0000,
            ),
            ephemeral=True,
        )
        return None

    vc: wavelink.Player = interaction.guild.voice_client  # type: ignore
    if vc is None:
        vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
    elif vc.channel != interaction.user.voice.channel:
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{_e('zwarning') or '⚠️'} Join my voice channel first.",
                color=0xFF0000,
            ),
            ephemeral=True,
        )
        return None

    vc.autoplay = wavelink.AutoPlayMode.disabled

    # Minimal fake ctx so music.py listeners can access author/channel safely
    _channel = interaction.channel
    _user    = interaction.user

    class _FakeCtx:
        author       = _user
        channel      = _channel
        voice_client = vc

        async def send(self, *args, **kwargs):
            try:
                return await _channel.send(*args, **kwargs)
            except Exception:
                pass

        async def reply(self, *args, **kwargs):
            kwargs.pop("mention_author", None)
            return await self.send(*args, **kwargs)

    vc.ctx = _FakeCtx()

    # ── Mark player as playlist-driven ────────────────────────────────────────
    # on_wavelink_track_start detects _is_playlist to send the per-song NP embed
    # on_wavelink_track_end detects _is_playlist to avoid disconnecting
    vc._is_playlist      = True
    vc._playlist_channel = _channel
    vc._playlist_np_msg  = None

    # ── Resolve the complete playlist before starting playback ───────────────
    # Starting the first track before the remaining searches finish creates a
    # race: a short first song can end while the queue is still empty, causing
    # the track-end listener to mark the playlist as exhausted.  Resolve first,
    # then seed the player queue, then start the first track.
    resolved_tracks = []
    for song in songs_to_play:
        try:
            results = await wavelink.Playable.search(song["song_uri"] or song["song_name"])
            if not results:
                continue
            track = results.tracks[0] if isinstance(results, wavelink.Playlist) else results[0]
            resolved_tracks.append(track)
        except Exception:
            continue

    if not resolved_tracks:
        await _channel.send(
            embed=discord.Embed(
                description=f"{_e('zcross') or '❌'} Could not load any songs from this playlist.",
                color=0xFF0000,
            )
        )
        return None

    for track in resolved_tracks[1:]:
        await vc.queue.put_wait(track)

    if loop_all:
        vc.queue.mode = wavelink.QueueMode.loop_all

    await vc.play(resolved_tracks[0])  # triggers on_wavelink_track_start → NP embed

    return vc


# ════════════════════════════════════════════════════════════════════════════════
# VOLUME MODAL
# ════════════════════════════════════════════════════════════════════════════════

class VolumeModal(discord.ui.Modal, title="Set Volume"):
    volume_input = discord.ui.TextInput(
        label="Volume (1–150)",
        placeholder="Enter a number between 1 and 150",
        min_length=1,
        max_length=3,
        required=True,
    )

    def __init__(self, player: wavelink.Player):
        super().__init__()
        self.player = player

    async def on_submit(self, interaction: discord.Interaction):
        try:
            level = int(self.volume_input.value)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))
            return
        if not 1 <= level <= 150:
            await interaction.response.send_message("Volume must be between 1 and 150.", ephemeral=True)
            asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))
            return
        await self.player.set_volume(level)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{_e('zunmute') or '🔊'} Volume set to **{level}%**.",
                color=COLOR_NOW_PLAYING,
            ),
            ephemeral=True,
        )
        asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))


# ════════════════════════════════════════════════════════════════════════════════
# ADD SONG MODAL
# ════════════════════════════════════════════════════════════════════════════════

class AddSongModal(discord.ui.Modal, title="Add Song to Playlist"):
    song_input = discord.ui.TextInput(
        label="Song Name or URL",
        placeholder="Enter a song name or Spotify / YouTube URL",
        min_length=2,
        max_length=200,
        required=True,
    )

    def __init__(self, playlist: dict, view):
        """parent view may be PlaylistDetailView, PlaylistActiveView, or None."""
        super().__init__()
        self.playlist    = playlist
        self.parent_view = view

    async def on_submit(self, interaction: discord.Interaction):
        query = self.song_input.value.strip()
        await interaction.response.defer(ephemeral=True)

        try:
            results = await wavelink.Playable.search(query)
        except Exception:
            results = []

        if not results:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} Could not find **{query}**.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return

        track = results.tracks[0] if isinstance(results, wavelink.Playlist) else results[0]
        await _db.add_song(self.playlist["id"], track.title, track.uri)

        # Refresh song list and update the main track-list message
        if self.parent_view is not None:
            self.parent_view.songs = await _db.get_songs(self.playlist["id"])
            self.parent_view._rebuild_song_select()
            if getattr(self.parent_view, 'message', None):
                try:
                    await self.parent_view.message.edit(
                        embed=self.parent_view._build_embed(),
                        view=self.parent_view,
                    )
                except Exception:
                    pass

        em = discord.Embed(
            description=f"{_e('ztick') or '✅'} Added **{track.title}** to **{self.playlist['name']}**.",
            color=COLOR_NOW_PLAYING,
        )
        if getattr(track, 'artwork', None):
            em.set_thumbnail(url=track.artwork)
        em.set_footer(text=f"Added by {interaction.user.display_name}")
        await interaction.followup.send(embed=em, ephemeral=True)
        # Auto-delete confirmation after CONFIRM_DELAY
        async def _del():
            await asyncio.sleep(CONFIRM_DELAY)
            try:
                await interaction.delete_original_response()
            except Exception:
                pass
        asyncio.create_task(_del())


# ════════════════════════════════════════════════════════════════════════════════
# MODALS  (new)
# ════════════════════════════════════════════════════════════════════════════════

class RenamePlaylistModal(discord.ui.Modal, title="Rename Playlist"):
    name_input = discord.ui.TextInput(
        label="New playlist name",
        placeholder="Enter a new name (max 50 characters)",
        min_length=1,
        max_length=50,
        required=True,
    )

    def __init__(self, playlist: dict, parent_view):
        super().__init__()
        self.playlist    = playlist
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip()
        ok = await _db.rename_playlist(
            interaction.user.id, self.playlist["id"], new_name
        )
        if not ok:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} Could not rename — you may already have a playlist with that name.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return
        # Refresh cached name in parent_view if it's PlaylistDetailView/PlaylistActiveView
        self.playlist["name"] = new_name
        if self.parent_view is not None and getattr(self.parent_view, 'playlist', None) is not None:
            self.parent_view.playlist["name"] = new_name
            if getattr(self.parent_view, 'message', None):
                try:
                    await self.parent_view.message.edit(
                        embed=self.parent_view._build_embed(),
                        view=self.parent_view,
                    )
                except Exception:
                    pass
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{_e('ztick') or '✅'} Renamed to **{new_name}**.",
                color=COLOR_NOW_PLAYING,
            ),
            ephemeral=True,
        )
        asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))


class SaveCreateModal(discord.ui.Modal, title="Create New Playlist & Save"):
    name_input = discord.ui.TextInput(
        label="Playlist name",
        placeholder="Enter a name (max 50 characters)",
        min_length=1,
        max_length=50,
        required=True,
    )
    visibility_input = discord.ui.TextInput(
        label="Visibility  (public / private)",
        placeholder="public",
        default="public",
        min_length=6,
        max_length=7,
        required=False,
    )

    def __init__(self, track, user_id: int):
        super().__init__()
        self.track   = track   # wavelink.Playable
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()[:50]
        raw_vis = (self.visibility_input.value or "public").strip().lower()
        visibility = "private" if raw_vis == "private" else "public"

        ok = await _db.create_playlist(self.user_id, name, visibility)
        if not ok:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} You already have a playlist named **{name}**.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return

        pl = await _db.get_playlist_by_owner_name(self.user_id, name)
        if pl:
            await _db.add_song(pl["id"], self.track.title, self.track.uri)
            songs    = await _db.get_songs(pl["id"])
            edit_view = PlaylistEditView(pl, None)
            embed = _build_playlist_embed(pl, songs)
            await interaction.response.send_message(embed=embed, view=edit_view, ephemeral=True)
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('ztick') or '✅'} Playlist **{name}** created and song saved!",
                    color=COLOR_NOW_PLAYING,
                ),
                ephemeral=True,
            )


# ════════════════════════════════════════════════════════════════════════════════
# ORDER SONGS VIEW  (new)
# ════════════════════════════════════════════════════════════════════════════════

class OrderSongsView(discord.ui.View):
    """Ephemeral view: select a song then Move Up / Move Down."""

    def __init__(self, playlist: dict, parent_view, songs: list = None):
        super().__init__(timeout=120)
        self.playlist    = playlist
        self.parent_view = parent_view
        self._selected_id: Optional[int] = None
        # Accept pre-loaded songs so the select is populated immediately on send.
        # Falls back to async load only if songs not provided (legacy path).
        self._songs: list = songs if songs is not None else []
        if songs is not None:
            self._rebuild_select()
        else:
            asyncio.create_task(self._load())

    async def _load(self):
        self._songs = await _db.get_songs(self.playlist["id"])
        self._rebuild_select()

    def _rebuild_select(self):
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        if not self._songs:
            return
        options = [
            discord.SelectOption(
                label=f"{i + 1}. {s['song_name'][:80]}",
                value=str(s["id"]),
            )
            for i, s in enumerate(self._songs[:25])
        ]
        sel = discord.ui.Select(placeholder="Select a song to move…", options=options, row=0)
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        self._selected_id = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def _move(self, interaction: discord.Interaction, direction: str):
        if self._selected_id is None:
            await _confirm(interaction, "Select a song first.")
            return
        moved = await _db.move_song(self.playlist["id"], self._selected_id, direction)
        if not moved:
            await _confirm(interaction, "Can't move that song any further.")
            return
        self._songs = await _db.get_songs(self.playlist["id"])
        self._rebuild_select()
        # Refresh parent message if possible
        if self.parent_view is not None:
            self.parent_view.songs = self._songs
            self.parent_view._rebuild_song_select()
            if getattr(self.parent_view, 'message', None):
                try:
                    await self.parent_view.message.edit(
                        embed=self.parent_view._build_embed(),
                        view=self.parent_view,
                    )
                except Exception:
                    pass
        await _confirm(interaction, f"{_e('ztick') or '✅'} Song moved {'up' if direction == 'up' else 'down'}.")

    @discord.ui.button(label="⬆ Move Up", style=discord.ButtonStyle.secondary, row=1)
    async def btn_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._move(interaction, "up")

    @discord.ui.button(label="⬇ Move Down", style=discord.ButtonStyle.secondary, row=1)
    async def btn_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._move(interaction, "down")


# ════════════════════════════════════════════════════════════════════════════════
# SAVE SONG VIEW  (new)
# ════════════════════════════════════════════════════════════════════════════════

class SaveSongView(discord.ui.View):
    """Ephemeral view shown when a user clicks the 💾 Save button on an NP embed."""

    def __init__(self, track, user_id: int,
                 playlists: list = None, saved_in: set = None):
        super().__init__(timeout=60)
        self.track   = track
        self.user_id = user_id

        if playlists is not None:
            # Synchronous build — data already fetched by caller
            self._build_with_data(playlists, saved_in or set())
        else:
            # Fallback: async build (legacy call path)
            asyncio.create_task(self._build())

    def _build_with_data(self, playlists: list, saved_in: set):
        """Populate the Select synchronously from pre-fetched data."""
        options: list[discord.SelectOption] = [
            discord.SelectOption(
                label="➕ Create New Playlist",
                value="__new__",
                description="Create a playlist and save this song",
            )
        ]
        for pl in playlists[:24]:
            already = pl["id"] in saved_in
            options.append(
                discord.SelectOption(
                    label=pl["name"][:100],
                    value=str(pl["id"]),
                    description="(✓ Already saved)" if already else f"{pl['song_count']} song(s)",
                    emoji="✅" if already else None,
                )
            )
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        sel = discord.ui.Select(
            placeholder="Choose a playlist to save this song…",
            options=options,
            row=0,
        )
        sel.callback = self._on_select
        self.add_item(sel)

    async def _build(self):
        """Async build — only used when pre-fetched data is not supplied."""
        playlists = await _db.get_user_playlists(self.user_id)
        saved_in  = await _db.get_playlist_ids_containing_uri(self.user_id, self.track.uri or "")
        self._build_with_data(playlists, saved_in)

    async def _on_select(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]

        if value == "__new__":
            await interaction.response.send_modal(
                SaveCreateModal(self.track, self.user_id)
            )
            return

        pid = int(value)
        # Check if already saved
        saved_in = await _db.get_playlist_ids_containing_uri(self.user_id, self.track.uri or "")
        if pid in saved_in:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} This song is already in that playlist.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))
            return

        # Verify ownership
        pl = await _db.get_playlist_by_id(pid)
        if not pl or str(pl.get("user_id")) != str(self.user_id):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} Playlist not found.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))
            return

        await _db.add_song(pid, self.track.title, self.track.uri)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{_e('ztick') or '✅'} Saved **{self.track.title}** to **{pl['name']}**.",
                color=COLOR_NOW_PLAYING,
            ),
            ephemeral=True,
        )
        asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))


async def _handle_save_button(interaction: discord.Interaction):
    """Called by the Save button in NowPlayingActionsView and playlist-mode NP."""
    vc = interaction.guild.voice_client
    if not vc or not isinstance(vc, __import__('wavelink').Player) or not vc.current:
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{_e('zwarning') or '⚠️'} Nothing is playing right now.",
                color=0xFF0000,
            ),
            ephemeral=True,
        )
        return
    track = vc.current

    # Pre-fetch playlist data BEFORE sending the message so the Select
    # dropdown is fully populated when the user sees the message.
    playlists = await _db.get_user_playlists(interaction.user.id)
    saved_in  = await _db.get_playlist_ids_containing_uri(interaction.user.id, track.uri or "")

    view = SaveSongView(track, interaction.user.id, playlists, saved_in)

    embed = discord.Embed(
        title=f"{_e('zmusic') or '🎵'}  Save Song",
        description=(
            f"**{track.title}**\n\n"
            "Select a playlist from the dropdown below, or choose\n"
            "**➕ Create New Playlist** to make a new one."
        ),
        color=COLOR_NOW_PLAYING,
    )
    if not playlists:
        embed.set_footer(text="You have no playlists yet — create one with ➕ Create New Playlist.")

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════════
# VIEWS
# ════════════════════════════════════════════════════════════════════════════════


# ── PlaylistEditView ─────────────────────────────────────────────────────────
class PlaylistEditView(discord.ui.View):
    """
    Private (ephemeral) view shown to the playlist owner when they click 'Edit Playlist'.

    Row 0: Add Song | Remove Song | Rename
    Row 1: Order Songs | Delete Playlist
    Row 2: Visibility Select (Public / Private)
    """

    def __init__(self, playlist: dict, parent_view):
        super().__init__(timeout=300)
        self.playlist    = playlist
        self.parent_view = parent_view

        _emap = {
            "pev_add":    _pe("zplus") or None,
            "pev_remove": _pe("delete") or None,
        }
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                cid = getattr(child, "custom_id", "")
                for key, emo in _emap.items():
                    if key in cid and emo:
                        child.emoji = emo

        # Populate the visibility select with the current value pre-selected
        cur_vis = self.playlist.get("visibility", "public")
        for child in self.children:
            if isinstance(child, discord.ui.Select) and getattr(child, 'custom_id', '') == 'pev_vis':
                for opt in child.options:
                    opt.default = (opt.value == cur_vis)

    # ── Row 0 ─────────────────────────────────────────────────────────────────

    @discord.ui.button(label="Add Song", style=discord.ButtonStyle.success,
                       row=0, custom_id="pev_add")
    async def btn_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddSongModal(self.playlist, self.parent_view))

    @discord.ui.button(label="Remove Song", style=discord.ButtonStyle.danger,
                       row=0, custom_id="pev_remove")
    async def btn_remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        songs = await _db.get_songs(self.playlist["id"])
        if not songs:
            await _confirm(interaction, "No songs in this playlist.")
            return

        options = [
            discord.SelectOption(
                label=f"{i + 1}. {s['song_name'][:80]}",
                value=str(s["id"]),
            )
            for i, s in enumerate(songs[:25])
        ]

        _outer_playlist = self.playlist
        _outer_parent   = self.parent_view

        class RemoveSelect(discord.ui.View):
            def __init__(rs_self):
                super().__init__(timeout=10)
                sel = discord.ui.Select(placeholder="Select song to remove…", options=options)

                async def _on_remove(sel_inter: discord.Interaction):
                    song_id = int(sel_inter.data["values"][0])
                    removed = await _db.remove_song(_outer_playlist["id"], song_id)
                    if removed and _outer_parent is not None:
                        _outer_parent.songs = await _db.get_songs(_outer_playlist["id"])
                        _outer_parent._rebuild_song_select()
                        if getattr(_outer_parent, 'message', None):
                            try:
                                await _outer_parent.message.edit(
                                    embed=_outer_parent._build_embed(),
                                    view=_outer_parent,
                                )
                            except Exception:
                                pass
                    await sel_inter.response.send_message(
                        embed=discord.Embed(
                            description=f"{_e('ztick') or '✅'} Song removed.",
                            color=COLOR_NOW_PLAYING,
                        ),
                        ephemeral=True,
                    )
                    async def _del():
                        await asyncio.sleep(CONFIRM_DELAY)
                        try:
                            await sel_inter.delete_original_response()
                        except Exception:
                            pass
                    asyncio.create_task(_del())

                sel.callback = _on_remove
                rs_self.add_item(sel)

        await interaction.response.send_message(
            embed=discord.Embed(description="Select a song to remove:", color=COLOR_CONTROL),
            view=RemoveSelect(),
            ephemeral=True,
        )
        async def _del_panel():
            await asyncio.sleep(5)
            try:
                await interaction.delete_original_response()
            except Exception:
                pass
        asyncio.create_task(_del_panel())

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary,
                       row=0, custom_id="pev_rename")
    async def btn_rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenamePlaylistModal(self.playlist, self.parent_view))

    # ── Row 1 ─────────────────────────────────────────────────────────────────

    @discord.ui.button(label="Order Songs", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="pev_order")
    async def btn_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Load songs before building the view so the select is fully populated immediately.
        songs = await _db.get_songs(self.playlist["id"])
        if not songs:
            await _confirm(interaction, f"{_e('zwarning') or '⚠️'} No songs in this playlist to reorder.")
            return
        order_view = OrderSongsView(self.playlist, self.parent_view, songs)
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"{_e('zmusic') or '🎵'}  Order Songs",
                description=(
                    f"**{len(songs)} song(s)** in this playlist.\n\n"
                    "Select a song from the dropdown, then use **⬆ Move Up** or **⬇ Move Down** "
                    "to change its position in the list."
                ),
                color=COLOR_NOW_PLAYING,
            ),
            view=order_view,
            ephemeral=True,
        )

    @discord.ui.button(label="Delete Playlist", style=discord.ButtonStyle.danger,
                       row=1, custom_id="pev_delete")
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm-then-delete: first click turns red and asks for confirmation."""
        # Use a quick ephemeral confirm pattern
        class ConfirmDeleteView(discord.ui.View):
            def __init__(cv_self):
                super().__init__(timeout=15)
                cv_self._pl    = self.playlist
                cv_self._uid   = interaction.user.id
                cv_self._pview = self.parent_view

            @discord.ui.button(label="Yes, delete it", style=discord.ButtonStyle.danger)
            async def confirm(cv_self, inter: discord.Interaction, btn: discord.ui.Button):
                ok = await _db.delete_playlist(cv_self._uid, cv_self._pl["name"])
                msg = (
                    f"{_e('ztick') or '✅'} Playlist **{cv_self._pl['name']}** deleted."
                    if ok else
                    f"{_e('zcross') or '❌'} Could not delete — playlist not found."
                )
                await inter.response.edit_message(
                    embed=discord.Embed(description=msg, color=COLOR_NOW_PLAYING),
                    view=None,
                )
                # Destroy parent track-list message if it exists
                if cv_self._pview is not None and getattr(cv_self._pview, 'message', None):
                    try:
                        await cv_self._pview.message.delete()
                    except Exception:
                        pass

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(cv_self, inter: discord.Interaction, btn: discord.ui.Button):
                await inter.response.edit_message(
                    embed=discord.Embed(description="Deletion cancelled.", color=COLOR_CONTROL),
                    view=None,
                )

        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"⚠️ Delete **{self.playlist['name']}**? This cannot be undone.",
                color=0xFF0000,
            ),
            view=ConfirmDeleteView(),
            ephemeral=True,
        )

    # ── Row 2: Visibility ─────────────────────────────────────────────────────

    @discord.ui.select(
        placeholder="Visibility…",
        options=[
            discord.SelectOption(label="🌐  Public",  value="public",  description="Anyone can see and browse this playlist"),
            discord.SelectOption(label="🔒  Private", value="private", description="Only you can see this playlist"),
        ],
        row=2,
        custom_id="pev_vis",
    )
    async def sel_visibility(self, interaction: discord.Interaction, select: discord.ui.Select):
        vis = interaction.data["values"][0]
        ok  = await _db.set_visibility(interaction.user.id, self.playlist["id"], vis)
        if ok:
            self.playlist["visibility"] = vis
            # Update default selection
            for opt in select.options:
                opt.default = (opt.value == vis)
            if self.parent_view is not None and getattr(self.parent_view, 'playlist', None):
                self.parent_view.playlist["visibility"] = vis
                if getattr(self.parent_view, 'message', None):
                    try:
                        await self.parent_view.message.edit(
                            embed=self.parent_view._build_embed(),
                            view=self.parent_view,
                        )
                    except Exception:
                        pass
        label = "Private 🔒" if vis == "private" else "Public 🌐"
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{_e('ztick') or '✅'} Visibility set to **{label}**.",
                color=COLOR_NOW_PLAYING,
            ),
            ephemeral=True,
        )
        asyncio.create_task(_auto_delete(interaction, CONFIRM_DELAY))


# ── PlaylistActiveView ────────────────────────────────────────────────────────
class PlaylistActiveView(discord.ui.View):
    """
    Replaces PlaylistDetailView's message when a playlist is actively playing.
    Merges the track list (with pagination) and all playback controls into one message.

    Row 0: Song select dropdown (jump to / restart from that song)
    Row 1: ⏮ Previous | ⏸ Pause/Resume | ⏭ Next | ⏹ Stop
    Row 2: 🔄 Replay   | 🔀 Shuffle     | 🔁 Loop | 🔊 Volume
    Row 3: ◀ Prev Page | ▶ Next Page | ✏️ Edit Playlist (owner only)
    """

    PER_PAGE = 20

    def __init__(
        self,
        player: wavelink.Player,
        channel,
        playlist: dict,
        songs: list,
        viewer_id: int,
        page: int = 0,
        owner_name: str = "",
    ):
        super().__init__(timeout=None)
        self.player       = player
        self.channel      = channel
        self.playlist     = playlist
        self.songs        = songs
        self.page         = page
        self._owner_name  = owner_name
        self._is_owner    = str(viewer_id) == str(playlist.get("user_id", ""))
        self._viewer_id   = viewer_id
        self._loop_on     = False
        self._shuffle_on  = False
        self._pre_shuffle: list = []
        self.message      = None  # set by caller after editing the message

        # Assign emojis to the playback/control buttons only (skip nav/edit)
        # rewind1 = backward/previous (same as music.py MusicControlView)
        # zreplay = circular replay arrow (restart current track)
        _nav_ids = {"pav_prev", "pav_next", "pav_edit"}
        _emap = [
            _pe("rewind1"),          # 0 previous  (⏮ rewind symbol, matches music.py)
            _pe("zpause"),           # 1 pause/resume
            _pe("skip"),             # 2 next
            _pe("musicstop_icons"),  # 3 stop
            _pe("zreplay"),          # 4 replay     (circular arrow, new dedicated emoji)
            _pe("shuffle"),          # 5 shuffle
            _pe("zloop"),            # 6 loop
            _pe("zunmute"),          # 7 volume
        ]
        ctrl_buttons = [
            c for c in self.children
            if isinstance(c, discord.ui.Button)
            and (getattr(c, "custom_id", "") or "") not in _nav_ids
        ]
        for btn, emo in zip(ctrl_buttons, _emap):
            if emo:
                btn.emoji = emo

        # Hide edit button for non-owners
        if not self._is_owner:
            for child in list(self.children):
                if (getattr(child, "custom_id", "") or "") == "pav_edit":
                    self.remove_item(child)

        self._rebuild_song_select()
        self._update_nav()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rebuild_song_select(self):
        for item in list(self.children):
            if isinstance(item, discord.ui.Select) and getattr(item, '_is_song_select', False):
                self.remove_item(item)
        total = len(self.songs)
        if total == 0:
            return
        start   = self.page * self.PER_PAGE
        options = [
            discord.SelectOption(
                label=f"{i + 1}. {self.songs[i]['song_name'][:80]}",
                value=str(i),
                description="Restart playlist from this song",
            )
            for i in range(start, min(start + self.PER_PAGE, total, start + 25))
        ]
        if not options:
            return
        sel = discord.ui.Select(placeholder="Jump to a song…", options=options, row=0)
        sel._is_song_select = True
        sel.callback = self._on_song_select
        self.add_item(sel)

    def _update_nav(self):
        total_pages = max(1, (len(self.songs) - 1) // self.PER_PAGE + 1) if self.songs else 1
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                cid = getattr(item, "custom_id", "") or ""
                if cid == "pav_prev":
                    item.disabled = (self.page == 0)
                elif cid == "pav_next":
                    item.disabled = (self.page >= total_pages - 1)

    def _build_embed(self) -> discord.Embed:
        return _build_playlist_embed(
            self.playlist, self.songs, self.page, self.PER_PAGE, self._owner_name
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = (interaction.data or {}).get("custom_id", "") or ""
        # Pagination and edit don't require VC membership
        if cid in ("pav_prev", "pav_next", "pav_edit"):
            return True
        vc = interaction.guild.voice_client
        if not vc or not isinstance(vc, wavelink.Player):
            await interaction.response.send_message(
                embed=discord.Embed(description="No active player.", color=0xFF0000),
                ephemeral=True,
            )
            return False
        if interaction.user in vc.channel.members:
            return True
        await interaction.response.send_message(
            embed=discord.Embed(
                description="You need to be in the same voice channel to control playback.",
                color=0xFF0000,
            ),
            ephemeral=True,
        )
        return False

    # ── Song selector ─────────────────────────────────────────────────────────

    async def _on_song_select(self, interaction: discord.Interaction):
        idx = int(interaction.data["values"][0])
        await interaction.response.defer()
        existing_vc = interaction.guild.voice_client
        if existing_vc and isinstance(existing_vc, wavelink.Player):
            # Delete the current NP message so it doesn't linger after jumping
            np_msg = getattr(existing_vc, '_playlist_np_msg', None)
            if np_msg:
                try:
                    await np_msg.delete()
                except Exception:
                    pass
                existing_vc._playlist_np_msg = None

            existing_vc.queue.clear()
            if existing_vc.playing:
                existing_vc._playlist_restarting = True
                await existing_vc.stop()
                await asyncio.sleep(0.3)
                existing_vc._playlist_restarting = False
        player = await _queue_playlist_and_play(
            interaction, self.playlist, self.songs,
            start_index=idx, loop_all=self._loop_on,
        )
        if player:
            self.player = player

    # ── Row 1: Playback ───────────────────────────────────────────────────────

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, row=1)
    async def btn_previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.commands.music import track_histories
        guild_id = interaction.guild.id
        vc = interaction.guild.voice_client
        if guild_id in track_histories and len(track_histories[guild_id]) > 1:
            track_histories[guild_id].pop()
            prev = track_histories[guild_id][-1]
            q = list(vc.queue)
            vc.queue.clear()
            await vc.queue.put_wait(prev)
            for t in q:
                await vc.queue.put_wait(t)
            if vc.playing:
                await vc.stop()
            await _confirm(interaction, f"{_e('rewind1') or '⏮'} Playing previous track.")
        else:
            await _confirm(interaction, "No previous track in history.")

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.success, row=1)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            if vc.paused:
                await vc.pause(False)
                try:
                    await vc.channel.edit(status=f"🎵 Playing: {vc.current.title}")
                except Exception:
                    pass
                button.emoji = _pe("zpause") or discord.PartialEmoji.from_str("⏸")
                button.style = discord.ButtonStyle.success
            elif vc.playing:
                await vc.pause(True)
                try:
                    await vc.channel.edit(status=f"⏸️ Paused: {vc.current.title}")
                except Exception:
                    pass
                button.emoji = _pe("zplay") or discord.PartialEmoji.from_str("▶")
                button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self)
        else:
            await _confirm(interaction, "Nothing is playing.")

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, row=1)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player) and vc.playing:
            if not vc.queue.is_empty:
                np_msg = getattr(vc, '_playlist_np_msg', None)
                if np_msg:
                    try:
                        await np_msg.delete()
                    except Exception:
                        pass
                    vc._playlist_np_msg = None
                await vc.stop()
                await _confirm(interaction, f"{_e('skip') or '⏭'} Skipped.")
            else:
                await _confirm(interaction, "No next track queued.")
        else:
            await _confirm(interaction, "Nothing is playing.")

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=1)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            if vc.channel:
                try:
                    await vc.channel.edit(status=None)
                except Exception:
                    pass
            await vc.disconnect()
            await _confirm(interaction, f"{_e('musicstop_icons') or '⏹'} Stopped.")
        else:
            await _confirm(interaction, "Not connected.")

    # ── Row 2: Controls ───────────────────────────────────────────────────────

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
    async def btn_replay(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player) and vc.playing:
            await vc.seek(0)
            await _confirm(interaction, f"{_e('zreplay') or '🔄'} Replaying from the start.")
        else:
            await _confirm(interaction, "Nothing is playing.")

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=2)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        import random as _random
        vc = interaction.guild.voice_client
        if not vc or not isinstance(vc, wavelink.Player):
            await _confirm(interaction, "No active player.")
            return
        if not self._shuffle_on:
            if not vc.queue:
                await _confirm(interaction, "Queue is empty — nothing to shuffle.")
                return
            self._pre_shuffle = list(vc.queue)
            vc.queue.clear()
            shuffled = list(self._pre_shuffle)
            _random.shuffle(shuffled)
            for t in shuffled:
                await vc.queue.put_wait(t)
            self._shuffle_on = True
            button.style = discord.ButtonStyle.success
        else:
            if self._pre_shuffle:
                vc.queue.clear()
                for t in self._pre_shuffle:
                    await vc.queue.put_wait(t)
            self._pre_shuffle = []
            self._shuffle_on  = False
            button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=2)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._loop_on = not self._loop_on
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            vc.queue.mode = (
                wavelink.QueueMode.loop_all if self._loop_on else wavelink.QueueMode.normal
            )
        button.style = discord.ButtonStyle.success if self._loop_on else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=2)
    async def btn_volume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            await interaction.response.send_modal(VolumeModal(vc))
        else:
            await _confirm(interaction, "Not connected to a voice channel.")

    # ── Row 3: Pagination + Edit ─────────────────────────────────────────────

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary,
                       row=3, custom_id="pav_prev", disabled=True)
    async def btn_prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self._rebuild_song_select()
            self._update_nav()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary,
                       row=3, custom_id="pav_next")
    async def btn_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_pages = max(1, (len(self.songs) - 1) // self.PER_PAGE + 1) if self.songs else 1
        if self.page < total_pages - 1:
            self.page += 1
            self._rebuild_song_select()
            self._update_nav()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Edit Playlist", emoji="✏️", style=discord.ButtonStyle.secondary,
                       row=3, custom_id="pav_edit")
    async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.playlist.get("user_id", "")):
            await _confirm(interaction, "Only the playlist owner can edit this playlist.")
            return
        edit_view = PlaylistEditView(self.playlist, self)
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"✏️  Edit: {self.playlist['name']}",
                description="Use the buttons below to manage songs in your playlist.",
                color=COLOR_NOW_PLAYING,
            ),
            view=edit_view,
            ephemeral=True,
        )


class PlaylistControlView(discord.ui.View):
    """
    Persistent control panel shown when a playlist is actively playing.
    Mirrors MusicControlView but loop = loop_all (entire playlist).

    Row 0 (Playback):  Previous | Pause/Resume | Next | Stop
    Row 1 (Controls):  Replay   | Shuffle      | Loop | Volume
    All buttons emoji-only; toggles turn green when enabled.
    """

    def __init__(self, player: wavelink.Player, channel):
        super().__init__(timeout=None)
        self.player       = player
        self.channel      = channel
        self._loop_on     = False
        self._shuffle_on  = False
        self._pre_shuffle: list = []

        _emap = [
            _pe("rewind1"),         # 0 previous  (⏮ rewind — matches music.py)
            _pe("zpause"),          # 1 pause/resume
            _pe("skip"),            # 2 next
            _pe("musicstop_icons"), # 3 stop
            _pe("zreplay"),         # 4 replay     (circular arrow — new dedicated emoji)
            _pe("shuffle"),         # 5 shuffle
            _pe("zloop"),           # 6 loop (loop_all)
            _pe("zunmute"),         # 7 volume
        ]
        buttons = [c for c in self.children if isinstance(c, discord.ui.Button)]
        for btn, emo in zip(buttons, _emap):
            btn.emoji = emo

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        vc = interaction.guild.voice_client
        if not vc or not isinstance(vc, wavelink.Player):
            await interaction.response.send_message(
                embed=discord.Embed(description="No active player.", color=0xFF0000),
                ephemeral=True,
            )
            return False
        if interaction.user in vc.channel.members:
            return True
        await interaction.response.send_message(
            embed=discord.Embed(
                description="You need to be in the same voice channel to control playback.",
                color=0xFF0000,
            ),
            ephemeral=True,
        )
        return False

    # ── Row 0: Playback ───────────────────────────────────────────────────────

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def btn_previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.commands.music import track_histories
        guild_id = interaction.guild.id
        vc = interaction.guild.voice_client
        if guild_id in track_histories and len(track_histories[guild_id]) > 1:
            track_histories[guild_id].pop()
            prev = track_histories[guild_id][-1]
            q = list(vc.queue)
            vc.queue.clear()
            await vc.queue.put_wait(prev)
            for t in q:
                await vc.queue.put_wait(t)
            if vc.playing:
                await vc.stop()
            await _confirm(interaction, f"{_e('rewind1') or '⏮'} Playing previous track.")
        else:
            await _confirm(interaction, "No previous track in history.")

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.success, row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            if vc.paused:
                await vc.pause(False)
                try:
                    await vc.channel.edit(status=f"🎵 Playing: {vc.current.title}")
                except Exception:
                    pass
                button.emoji = _pe("zpause") or discord.PartialEmoji.from_str("⏸")
                button.style = discord.ButtonStyle.success
            elif vc.playing:
                await vc.pause(True)
                try:
                    await vc.channel.edit(status=f"⏸️ Paused: {vc.current.title}")
                except Exception:
                    pass
                button.emoji = _pe("zplay") or discord.PartialEmoji.from_str("▶")
                button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self)
        else:
            await _confirm(interaction, "Nothing is playing.")

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, row=0)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player) and vc.playing:
            if not vc.queue.is_empty:
                # Delete current NP embed before skipping
                np_msg = getattr(vc, '_playlist_np_msg', None)
                if np_msg:
                    try:
                        await np_msg.delete()
                    except Exception:
                        pass
                    vc._playlist_np_msg = None
                await vc.stop()
                await _confirm(interaction, f"{_e('skip') or '⏭'} Skipped.")
            else:
                await _confirm(interaction, "No next track queued.")
        else:
            await _confirm(interaction, "Nothing is playing.")

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=0)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            if vc.channel:
                try:
                    await vc.channel.edit(status=None)
                except Exception:
                    pass
            await vc.disconnect()
            await _confirm(interaction, f"{_e('musicstop_icons') or '⏹'} Stopped.")
        else:
            await _confirm(interaction, "Not connected.")

    # ── Row 1: Controls ───────────────────────────────────────────────────────

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.secondary, row=1)
    async def btn_replay(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player) and vc.playing:
            await vc.seek(0)
            await _confirm(interaction, f"{_e('zreplay') or '🔄'} Replaying from the start.")
        else:
            await _confirm(interaction, "Nothing is playing.")

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=1)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        import random as _random
        vc = interaction.guild.voice_client
        if not vc or not isinstance(vc, wavelink.Player):
            await _confirm(interaction, "No active player.")
            return
        if not self._shuffle_on:
            if not vc.queue:
                await _confirm(interaction, "Queue is empty — nothing to shuffle.")
                return
            self._pre_shuffle = list(vc.queue)
            vc.queue.clear()
            shuffled = list(self._pre_shuffle)
            _random.shuffle(shuffled)
            for t in shuffled:
                await vc.queue.put_wait(t)
            self._shuffle_on = True
            button.style = discord.ButtonStyle.success
        else:
            if self._pre_shuffle:
                vc.queue.clear()
                for t in self._pre_shuffle:
                    await vc.queue.put_wait(t)
            self._pre_shuffle = []
            self._shuffle_on  = False
            button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=1)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Loop toggles the entire playlist (loop_all mode)."""
        self._loop_on = not self._loop_on
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            vc.queue.mode = (
                wavelink.QueueMode.loop_all if self._loop_on else wavelink.QueueMode.normal
            )
        button.style = discord.ButtonStyle.success if self._loop_on else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def btn_volume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            await interaction.response.send_modal(VolumeModal(vc))
        else:
            await _confirm(interaction, "Not connected to a voice channel.")


class PlaylistDetailView(discord.ui.View):
    """
    Public message shown after selecting a playlist from the browser.

    Layout (all users):
      Row 0 — Song Selector dropdown (start playback from chosen song)
      Row 1 — ▶ Play Playlist  |  ✏️ Edit Playlist (owner only — opens private edit panel)
      Row 2 — ◀ Prev Page | ▶ Next Page

    When play starts the message is updated in-place to PlaylistActiveView
    (which contains the full playback control panel).
    """

    PER_PAGE = 20

    def __init__(
        self,
        playlist: dict,
        songs: list,
        viewer_id: int,
        page: int = 0,
        owner_name: str = "",
    ):
        super().__init__(timeout=300)
        self.playlist     = playlist
        self.songs        = songs
        self.page         = page
        self._loop_on     = False
        self._owner_name  = owner_name
        self._viewer_id   = viewer_id
        self._is_owner    = str(viewer_id) == str(playlist.get("user_id", ""))
        self.message      = None  # set after sending

        # Assign custom emojis
        _emap = {
            "pdv_play_btn": _pe("zplay") or None,
            "pdv_edit_btn": _pe("ztools") or None,
        }
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                cid = getattr(child, "custom_id", "") or ""
                for key, emo in _emap.items():
                    if key in cid and emo:
                        child.emoji = emo

        # Hide edit button for non-owners
        if not self._is_owner:
            for child in list(self.children):
                if (getattr(child, "custom_id", "") or "") == "pdv_edit_btn":
                    self.remove_item(child)

        self._rebuild_song_select()
        self._update_nav()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rebuild_song_select(self):
        for item in list(self.children):
            if isinstance(item, discord.ui.Select) and getattr(item, '_is_song_select', False):
                self.remove_item(item)
        total = len(self.songs)
        if total == 0:
            return
        start = self.page * self.PER_PAGE
        options = [
            discord.SelectOption(
                label=f"{i + 1}. {self.songs[i]['song_name'][:80]}",
                value=str(i),
                description="Start playlist from this song",
            )
            for i in range(start, min(start + self.PER_PAGE, total, start + 25))
        ]
        if not options:
            return
        sel = discord.ui.Select(placeholder="Choose a song to play…", options=options, row=0)
        sel._is_song_select = True
        sel.callback = self._on_song_select
        self.add_item(sel)

    def _update_nav(self):
        total_pages = max(1, (len(self.songs) - 1) // self.PER_PAGE + 1) if self.songs else 1
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                cid = getattr(item, "custom_id", "") or ""
                if cid == "pdv_prev":
                    item.disabled = (self.page == 0)
                elif cid == "pdv_next":
                    item.disabled = (self.page >= total_pages - 1)

    def _build_embed(self) -> discord.Embed:
        return _build_playlist_embed(
            self.playlist, self.songs, self.page, self.PER_PAGE, self._owner_name
        )

    async def _start_playback(
        self, interaction: discord.Interaction, start_index: int = 0
    ):
        """
        Internal: queue & play the playlist, then transition this message
        in-place to PlaylistActiveView (track list + controls in one message).
        """
        existing_vc = interaction.guild.voice_client
        if existing_vc and isinstance(existing_vc, wavelink.Player):
            existing_vc.queue.clear()
            if existing_vc.playing:
                existing_vc._playlist_restarting = True
                await existing_vc.stop()
                await asyncio.sleep(0.3)
                existing_vc._playlist_restarting = False

        player = await _queue_playlist_and_play(
            interaction, self.playlist, self.songs,
            start_index=start_index, loop_all=self._loop_on,
        )

        if player and self.message:
            active_view = PlaylistActiveView(
                player=player,
                channel=interaction.channel,
                playlist=self.playlist,
                songs=self.songs,
                viewer_id=self._viewer_id,
                page=self.page,
                owner_name=self._owner_name,
            )
            active_view._loop_on = self._loop_on
            try:
                await self.message.edit(embed=self._build_embed(), view=active_view)
                active_view.message = self.message
            except Exception:
                pass

    # ── Song selector callback ────────────────────────────────────────────────

    async def _on_song_select(self, interaction: discord.Interaction):
        idx = int(interaction.data["values"][0])
        await interaction.response.defer()
        await self._start_playback(interaction, start_index=idx)

    # ── Row 1: Play | Edit (owner) ────────────────────────────────────────────

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.success,
                       row=1, custom_id="pdv_play_btn")
    async def btn_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self._start_playback(interaction, start_index=0)

    @discord.ui.button(label="Edit Playlist", emoji="✏️", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="pdv_edit_btn")
    async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Owner only: opens private edit panel."""
        if str(interaction.user.id) != str(self.playlist.get("user_id", "")):
            await _confirm(interaction, "Only the playlist owner can edit this playlist.")
            return
        edit_view = PlaylistEditView(self.playlist, self)
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"✏️  Edit: {self.playlist['name']}",
                description="Use the buttons below to manage songs in your playlist.",
                color=COLOR_NOW_PLAYING,
            ),
            view=edit_view,
            ephemeral=True,
        )

    # ── Row 2: Pagination ─────────────────────────────────────────────────────

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary,
                       row=2, custom_id="pdv_prev", disabled=True)
    async def btn_prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self._rebuild_song_select()
            self._update_nav()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary,
                       row=2, custom_id="pdv_next")
    async def btn_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_pages = max(1, (len(self.songs) - 1) // self.PER_PAGE + 1) if self.songs else 1
        if self.page < total_pages - 1:
            self.page += 1
            self._rebuild_song_select()
            self._update_nav()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.defer()


class PlaylistBrowserView(discord.ui.View):
    """Shows a paginated list of all playlists with a select-menu to open one."""

    PER_PAGE = 10

    def __init__(self, playlists: list, viewer_id: int = 0, page: int = 0):
        super().__init__(timeout=300)
        self.playlists = playlists
        self.viewer_id = viewer_id
        self.page      = page

        self._rebuild_select()
        self._update_nav()

    def _rebuild_select(self):
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        start    = self.page * self.PER_PAGE
        page_pls = self.playlists[start: start + self.PER_PAGE]
        if not page_pls:
            return

        options = [
            discord.SelectOption(
                label=pl["name"][:100],
                value=str(pl["id"]),
                description=f"{'🔒 Private' if pl.get('visibility') == 'private' else '🌐 Public'}  ·  {pl['song_count']} song(s)",
            )
            for pl in page_pls
        ]
        sel = discord.ui.Select(
            placeholder="Select a playlist to view…",
            options=options,
            row=0,
        )
        sel.callback = self._on_select
        self.add_item(sel)

    def _update_nav(self):
        total_pages = max(1, (len(self.playlists) - 1) // self.PER_PAGE + 1) if self.playlists else 1
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                cid = getattr(item, "custom_id", "")
                if cid == "pbv_prev":
                    item.disabled = (self.page == 0)
                elif cid == "pbv_next":
                    item.disabled = (self.page >= total_pages - 1)

    def build_embed(self) -> discord.Embed:
        total = len(self.playlists)
        em    = discord.Embed(
            title=f"{_e('zmusic') or '🎵'}  Playlists",
            color=COLOR_CONTROL,
        )
        start    = self.page * self.PER_PAGE
        page_pls = self.playlists[start: start + self.PER_PAGE]
        if page_pls:
            lines = [
                f"`{start + i + 1}.` {'🔒' if pl.get('visibility') == 'private' else '🌐'}  **{pl['name']}**  ·  {pl['song_count']} song(s)"
                for i, pl in enumerate(page_pls)
            ]
            em.description = "\n".join(lines)
        else:
            em.description = "*No playlists found.*"
        total_pages = max(1, (total - 1) // self.PER_PAGE + 1) if total else 1
        em.set_footer(text=f"{total} playlist(s)  ·  Page {self.page + 1}/{total_pages}")
        return em

    async def _on_select(self, interaction: discord.Interaction):
        pid = int(interaction.data["values"][0])
        pl  = await _db.get_playlist_by_id(pid)
        if not pl:
            return await interaction.response.send_message("Playlist not found.", ephemeral=True)

        # Block private playlists for non-owners
        if pl.get("visibility") == "private" and str(pl.get("user_id")) != str(interaction.user.id):
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"🔒 This playlist is **private** and can only be viewed by its owner.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )

        songs = await _db.get_songs(pid)

        # Try to resolve owner display name (best-effort)
        owner_name = ""
        try:
            owner_user = interaction.guild.get_member(int(pl["user_id"]))
            if owner_user:
                owner_name = owner_user.display_name
            else:
                owner_name = f"<@{pl['user_id']}>"
        except Exception:
            pass

        view  = PlaylistDetailView(pl, songs, viewer_id=interaction.user.id, owner_name=owner_name)
        embed = _build_playlist_embed(pl, songs, owner_name=owner_name)
        # Public message — visible to everyone in the channel
        await interaction.response.send_message(embed=embed, view=view)
        # Store the message so PlaylistDetailView can edit it in-place when play starts
        try:
            view.message = await interaction.original_response()
        except Exception:
            pass

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="pbv_prev", disabled=True)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self._rebuild_select()
            self._update_nav()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="pbv_next")
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_pages = max(1, (len(self.playlists) - 1) // self.PER_PAGE + 1) if self.playlists else 1
        if self.page < total_pages - 1:
            self.page += 1
            self._rebuild_select()
            self._update_nav()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()


# ════════════════════════════════════════════════════════════════════════════════
# AUTOCOMPLETE
# ════════════════════════════════════════════════════════════════════════════════

async def _ac_user_playlists(interaction: discord.Interaction, current: str):
    rows = await _db.get_user_playlists(interaction.user.id)
    return [
        app_commands.Choice(name=r["name"], value=r["name"])
        for r in rows if current.lower() in r["name"].lower()
    ][:25]


async def _ac_songs_in_playlist(interaction: discord.Interaction, current: str):
    try:
        pl_name = getattr(interaction.namespace, "playlist", None)
    except Exception:
        return []
    if not pl_name:
        return []

    pl = await _db.get_playlist_by_owner_name(interaction.user.id, pl_name)
    if not pl:
        return []

    songs = await _db.get_songs(pl["id"])
    return [
        app_commands.Choice(
            name=f"{i + 1}. {s['song_name'][:80]}",
            value=str(s["id"])
        )
        for i, s in enumerate(songs)
        if current.lower() in s["song_name"].lower()
    ][:25]


# ════════════════════════════════════════════════════════════════════════════════
# COG
# ════════════════════════════════════════════════════════════════════════════════

class PlaylistCog(Cog):
    """Global playlist system — create, manage, and play saved playlists."""

    # Slash command groups ────────────────────────────────────────────────────
    playlist_group = app_commands.Group(
        name="playlist",
        description="Manage and browse playlists."
    )
    song_group = app_commands.Group(
        name="song",
        description="Manage songs in your playlists."
    )

    def __init__(self, client: zyrox):
        self.client = client
        self.client.loop.create_task(self._init_db())

    async def _init_db(self):
        await _db.init()

    def help_custom(self):
        emoji       = _e("zmusic") or "🎵"
        label       = "Playlist Commands"
        description = "Create, manage, and play personal playlists across all servers."
        return emoji, label, description

    # ── /playlist list ────────────────────────────────────────────────────────

    @playlist_group.command(name="list", description="Browse all playlists.")
    async def cmd_playlist_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        playlists = await _db.get_all_playlists(viewer_id=interaction.user.id)

        if not playlists:
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} No playlists found.",
                    color=0xFF0000
                )
            )

        view  = PlaylistBrowserView(playlists, viewer_id=interaction.user.id)
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view)

    # ── /playlist create ──────────────────────────────────────────────────────

    @playlist_group.command(name="create", description="Create a new personal playlist.")
    @app_commands.describe(
        name="Name for your playlist (max 50 characters)",
        visibility="Who can see this playlist: public (default) or private",
    )
    @app_commands.choices(visibility=[
        app_commands.Choice(name="🌐 Public",  value="public"),
        app_commands.Choice(name="🔒 Private", value="private"),
    ])
    async def cmd_playlist_create(
        self, interaction: discord.Interaction, name: str,
        visibility: str = "public",
    ):
        name = name.strip()[:50]
        if not name:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} Playlist name cannot be empty.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        ok = await _db.create_playlist(interaction.user.id, name, visibility)
        if not ok:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} You already have a playlist named **{name}**.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        vis_label = "Private 🔒" if visibility == "private" else "Public 🌐"
        em = discord.Embed(
            description=(
                f"{_e('ztick') or '✅'} Playlist **{name}** created! ({vis_label})\n"
                f"Use `/song add` to add songs to it."
            ),
            color=0xFF0000
        )
        em.set_footer(text=f"Created by {interaction.user.display_name}")
        await interaction.response.send_message(embed=em)

    # ── /playlist delete ──────────────────────────────────────────────────────

    @playlist_group.command(name="delete", description="Delete one of your playlists.")
    @app_commands.describe(name="Name of the playlist to delete")
    @app_commands.autocomplete(name=_ac_user_playlists)
    async def cmd_playlist_delete(self, interaction: discord.Interaction, name: str):
        ok = await _db.delete_playlist(interaction.user.id, name)
        if not ok:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} No playlist named **{name}** in your library.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        em = discord.Embed(
            description=f"{_e('ztick') or '✅'} Playlist **{name}** and all its songs have been deleted.",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=em)

    # ── /song add ─────────────────────────────────────────────────────────────

    @song_group.command(name="add", description="Add a song to one of your playlists.")
    @app_commands.describe(
        playlist="Your playlist name",
        song="Song name or URL (YouTube, Spotify, SoundCloud…)"
    )
    @app_commands.autocomplete(playlist=_ac_user_playlists)
    async def cmd_song_add(
        self, interaction: discord.Interaction, playlist: str, song: str
    ):
        await interaction.response.defer()

        pl = await _db.get_playlist_by_owner_name(interaction.user.id, playlist)
        if not pl:
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} You don't have a playlist named **{playlist}**.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        # Search via Lavalink so we persist the real URI
        try:
            results = await wavelink.Playable.search(song)
        except Exception:
            results = []

        if not results:
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} Could not find **{song}**. Try a different name or URL.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        track = results.tracks[0] if isinstance(results, wavelink.Playlist) else results[0]
        await _db.add_song(pl["id"], track.title, track.uri)

        em = discord.Embed(
            description=f"{_e('ztick') or '✅'} Added **{track.title}** to **{playlist}**.",
            color=0xFF0000
        )
        em.set_thumbnail(url=track.artwork or "")
        em.set_footer(text=f"Added by {interaction.user.display_name}")
        await interaction.followup.send(embed=em)

    # ── /song remove ──────────────────────────────────────────────────────────

    @song_group.command(name="remove", description="Remove a song from one of your playlists.")
    @app_commands.describe(
        playlist="Your playlist name",
        song="Song to remove (select from list)"
    )
    @app_commands.autocomplete(playlist=_ac_user_playlists, song=_ac_songs_in_playlist)
    async def cmd_song_remove(
        self, interaction: discord.Interaction, playlist: str, song: str
    ):
        pl = await _db.get_playlist_by_owner_name(interaction.user.id, playlist)
        if not pl:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} You don't have a playlist named **{playlist}**.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        try:
            song_id = int(song)
        except ValueError:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} Invalid song selection. Use autocomplete.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        # Fetch song name before deletion for confirmation
        songs    = await _db.get_songs(pl["id"])
        song_obj = next((s for s in songs if s["id"] == song_id), None)

        ok = await _db.remove_song(pl["id"], song_id)
        if not ok:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} Song not found in **{playlist}**.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        name = song_obj["song_name"] if song_obj else "Song"
        em   = discord.Embed(
            description=f"{_e('ztick') or '✅'} Removed **{name}** from **{playlist}**.",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=em)
