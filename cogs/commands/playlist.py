"""
cogs/commands/playlist.py — Global playlist system for Zyrox X bot.

Commands:
  /playlist list [search]       — browse all playlists (searchable)
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
    if fallback:
        try:
            return discord.PartialEmoji.from_str(fallback)
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
                    UNIQUE(user_id, name)
                )
            """)
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

    async def create_playlist(self, user_id: int, name: str) -> bool:
        try:
            async with self._conn() as db:
                await self._setup(db)
                await db.execute(
                    "INSERT INTO playlists (user_id, name, created_at) VALUES (?, ?, ?)",
                    (str(user_id), name, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
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
                "SELECT id, name, created_at FROM playlists WHERE user_id = ? ORDER BY name COLLATE NOCASE",
                (str(user_id),)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def get_all_playlists(self, search: str = None) -> list:
        async with self._conn() as db:
            await self._setup(db)
            db.row_factory = aiosqlite.Row
            query = (
                "SELECT p.id, p.user_id, p.name, p.created_at, COUNT(s.id) AS song_count "
                "FROM playlists p LEFT JOIN playlist_songs s ON s.playlist_id = p.id "
            )
            if search:
                query += "WHERE LOWER(p.name) LIKE ? "
                args   = (f"%{search.lower()}%",)
            else:
                args   = ()
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
                "SELECT p.id, p.user_id, p.name, p.created_at, COUNT(s.id) AS song_count "
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
                "FROM playlist_songs WHERE playlist_id = ? ORDER BY position ASC, id ASC",
                (playlist_id,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

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

def _build_playlist_embed(pl: dict, songs: list, page: int = 0, per_page: int = 20) -> discord.Embed:
    """Build the embed showing a playlist's songs."""
    em = discord.Embed(
        title=f"{_e('zmusic') or '🎵'}  {pl['name']}",
        color=0xFF0000
    )
    total = len(songs)
    start = page * per_page
    page_songs = songs[start: start + per_page]

    if page_songs:
        lines = [f"`{start + i + 1}.` **{s['song_name']}**" for i, s in enumerate(page_songs)]
        em.description = "\n".join(lines)
    else:
        em.description = f"*No songs yet — use `/song add` to add some!*"

    total_pages = max(1, (total - 1) // per_page + 1) if total else 1
    em.set_footer(
        text=f"{total} song{'s' if total != 1 else ''}"
             + (f"  •  Page {page + 1}/{total_pages}" if total > per_page else "")
    )
    return em


async def _queue_playlist_and_play(
    interaction: discord.Interaction,
    songs: list,
    start_index: int = 0,
    loop_all: bool = False,
) -> tuple[Optional[wavelink.Player], Optional[wavelink.Playable]]:
    """
    Join the user's VC, queue songs starting from start_index, begin playback.
    Returns (player, first_track) or (None, None) on error.
    """
    if not interaction.user.voice:
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{_e('zwarning') or '⚠️'} You need to be in a voice channel.",
                color=0xFF0000
            ),
            ephemeral=True
        )
        return None, None

    songs_to_play = songs[start_index:]
    if not songs_to_play:
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{_e('zcross') or '❌'} No songs to play from that position.",
                color=0xFF0000
            ),
            ephemeral=True
        )
        return None, None

    vc: wavelink.Player = interaction.guild.voice_client  # type: ignore
    if vc is None:
        vc = await interaction.user.voice.channel.connect(cls=wavelink.Player)
    elif vc.channel != interaction.user.voice.channel:
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{_e('zwarning') or '⚠️'} Join my voice channel first.",
                color=0xFF0000
            ),
            ephemeral=True
        )
        return None, None

    vc.autoplay = wavelink.AutoPlayMode.disabled

    # Provide a fake ctx so display_player_embed (in music cog) can use it
    class _FakeCtx:
        author       = interaction.user
        channel      = interaction.channel
        voice_client = vc
    vc.ctx = _FakeCtx()

    loading = await interaction.followup.send(
        embed=discord.Embed(
            description=f"{_e('loading') or '⏳'} Loading **{len(songs_to_play)}** song(s)…",
            color=0xFF0000
        )
    )

    first_track = None
    queued      = 0
    for song in songs_to_play:
        try:
            results = await wavelink.Playable.search(song["song_uri"] or song["song_name"])
            if not results:
                continue
            track = results.tracks[0] if isinstance(results, wavelink.Playlist) else results[0]
            if first_track is None and not vc.playing:
                first_track = track
                await vc.play(track)
            else:
                await vc.queue.put_wait(track)
            queued += 1
        except Exception:
            continue

    if loop_all:
        vc.queue.mode = wavelink.QueueMode.loop_all

    try:
        await loading.edit(embed=discord.Embed(
            description=f"{_e('ztick') or '✅'} Queued **{queued}** song(s). Now playing!",
            color=0xFF0000
        ))
    except Exception:
        pass

    return vc, first_track


# ════════════════════════════════════════════════════════════════════════════════
# VIEWS
# ════════════════════════════════════════════════════════════════════════════════

class PlaylistDetailView(discord.ui.View):
    """
    Shown after a user selects a playlist.
    Rows:
      Row 0 — ▶ Play All | 🔁 Loop
      Row 1 — ⏮ Prev page | Next ⏭  (pagination for song list)
      Row 2 — Select: Play from song #N  (up to 25 songs shown)
    """

    PER_PAGE = 20

    def __init__(self, playlist: dict, songs: list, page: int = 0):
        super().__init__(timeout=300)
        self.playlist  = playlist
        self.songs     = songs
        self.page      = page
        self._loop_on  = False

        self._rebuild_dropdown()
        self._update_nav_buttons()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _rebuild_dropdown(self):
        # Remove old selects
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        total = len(self.songs)
        if total == 0:
            return

        start = self.page * self.PER_PAGE
        end   = min(start + self.PER_PAGE, total)
        options = [
            discord.SelectOption(
                label=f"{i + 1}. {self.songs[i]['song_name'][:80]}",
                value=str(i),
                description="Play from this song onwards"
            )
            for i in range(start, min(end, start + 25))
        ]

        sel = discord.ui.Select(
            placeholder=f"{_e('zplay') or '▶'} Play from song # …",
            options=options,
            row=2
        )
        sel.callback = self._on_song_jump
        self.add_item(sel)

    def _update_nav_buttons(self):
        total_pages = max(1, (len(self.songs) - 1) // self.PER_PAGE + 1) if self.songs else 1
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                cid = getattr(item, "custom_id", "")
                if cid == "pdv_prev":
                    item.disabled = (self.page == 0)
                elif cid == "pdv_next":
                    item.disabled = (self.page >= total_pages - 1)

    def _build_embed(self) -> discord.Embed:
        return _build_playlist_embed(self.playlist, self.songs, self.page, self.PER_PAGE)

    # ── callbacks ─────────────────────────────────────────────────────────────

    async def _on_song_jump(self, interaction: discord.Interaction):
        await interaction.response.defer()
        idx = int(interaction.data["values"][0])
        await _queue_playlist_and_play(interaction, self.songs, start_index=idx, loop_all=self._loop_on)

    @discord.ui.button(label="▶ Play All", style=discord.ButtonStyle.success, row=0)
    async def btn_play_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await _queue_playlist_and_play(interaction, self.songs, start_index=0, loop_all=self._loop_on)

    @discord.ui.button(label="🔁 Loop: OFF", style=discord.ButtonStyle.secondary, row=0)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._loop_on = not self._loop_on
        button.label  = f"🔁 Loop: {'ON' if self._loop_on else 'OFF'}"
        button.style  = discord.ButtonStyle.success if self._loop_on else discord.ButtonStyle.secondary

        vc = interaction.guild.voice_client
        if vc and isinstance(vc, wavelink.Player):
            vc.queue.mode = wavelink.QueueMode.loop_all if self._loop_on else wavelink.QueueMode.normal

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏮ Prev", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="pdv_prev", disabled=True)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self._rebuild_dropdown()
            self._update_nav_buttons()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ⏭", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="pdv_next")
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_pages = max(1, (len(self.songs) - 1) // self.PER_PAGE + 1) if self.songs else 1
        if self.page < total_pages - 1:
            self.page += 1
            self._rebuild_dropdown()
            self._update_nav_buttons()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.defer()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


class PlaylistBrowserView(discord.ui.View):
    """Shows a paginated list of all playlists with a select-menu to open one."""

    PER_PAGE = 10

    def __init__(self, playlists: list, page: int = 0, search: str = None):
        super().__init__(timeout=300)
        self.playlists = playlists
        self.page      = page
        self.search    = search

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
                description=f"{pl['song_count']} song(s)"
            )
            for pl in page_pls
        ]
        sel = discord.ui.Select(
            placeholder=f"{_e('zmusic') or '🎵'} Select a playlist to view…",
            options=options,
            row=0
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
        title = f"{_e('zmusic') or '🎵'}  Playlists"
        if self.search:
            title += f"  —  search: *{self.search}*"

        em = discord.Embed(title=title, color=0xFF0000)

        start    = self.page * self.PER_PAGE
        page_pls = self.playlists[start: start + self.PER_PAGE]
        if page_pls:
            lines = [
                f"`{start + i + 1}.` **{pl['name']}**  —  {pl['song_count']} song(s)"
                for i, pl in enumerate(page_pls)
            ]
            em.description = "\n".join(lines)
        else:
            em.description = "*No playlists found.*"

        total_pages = max(1, (total - 1) // self.PER_PAGE + 1) if total else 1
        em.set_footer(text=f"{total} playlist(s)  •  Page {self.page + 1}/{total_pages}")
        return em

    async def _on_select(self, interaction: discord.Interaction):
        pid = int(interaction.data["values"][0])
        pl  = await _db.get_playlist_by_id(pid)
        if not pl:
            return await interaction.response.send_message("Playlist not found.", ephemeral=True)

        songs = await _db.get_songs(pid)
        view  = PlaylistDetailView(pl, songs)
        embed = _build_playlist_embed(pl, songs)
        await interaction.response.send_message(embed=embed, view=view)

    @discord.ui.button(label="⏮ Prev", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="pbv_prev", disabled=True)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self._rebuild_select()
            self._update_nav()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ⏭", style=discord.ButtonStyle.secondary,
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

    @playlist_group.command(name="list", description="Browse all playlists (searchable by name).")
    @app_commands.describe(search="Filter playlists by name (optional)")
    async def cmd_playlist_list(
        self, interaction: discord.Interaction, search: str = None
    ):
        await interaction.response.defer()
        playlists = await _db.get_all_playlists(search)

        if not playlists:
            msg = f"No playlists found" + (f" matching **{search}**." if search else ".")
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} {msg}",
                    color=0xFF0000
                )
            )

        view  = PlaylistBrowserView(playlists, search=search)
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view)

    # ── /playlist create ──────────────────────────────────────────────────────

    @playlist_group.command(name="create", description="Create a new personal playlist.")
    @app_commands.describe(name="Name for your playlist (max 50 characters)")
    async def cmd_playlist_create(self, interaction: discord.Interaction, name: str):
        name = name.strip()[:50]
        if not name:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} Playlist name cannot be empty.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        ok = await _db.create_playlist(interaction.user.id, name)
        if not ok:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{_e('zcross') or '❌'} You already have a playlist named **{name}**.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

        em = discord.Embed(
            description=(
                f"{_e('ztick') or '✅'} Playlist **{name}** created!\n"
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
