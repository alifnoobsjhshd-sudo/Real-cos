import aiosqlite
import sqlite3
import discord

DEFAULT_BRANDING = "Sunlight"
DEFAULT_COLOR = 0xFFD700
DEFAULT_FUN_PREFIX = "sun"

# guild_id = 0 is used as the "global default" slot


def _setup_branding_db():
    conn = sqlite3.connect('db/branding.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS guild_branding (
            guild_id    INTEGER PRIMARY KEY,
            branding_name TEXT,
            embed_color   INTEGER,
            embed_thumbnail TEXT,
            embed_banner    TEXT,
            fun_prefix  TEXT
        )
    ''')
    # Add fun_prefix column to existing DBs that were created before this field
    try:
        conn.execute("ALTER TABLE guild_branding ADD COLUMN fun_prefix TEXT")
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS guild_profile (
            guild_id     INTEGER PRIMARY KEY,
            display_name TEXT,
            bio          TEXT,
            avatar_url   TEXT,
            banner_url   TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bot_activity (
            id            INTEGER PRIMARY KEY CHECK (id = 0),
            activity_type TEXT,
            activity_name TEXT
        )
    ''')
    conn.commit()
    conn.close()


_setup_branding_db()


async def get_fun_prefix(guild_id: int) -> str:
    """Return the fun prefix for a guild, falling back to global then 'sun'.
    Never raises — always returns a usable string."""
    try:
        async with aiosqlite.connect('db/branding.db') as db:
            async with db.execute(
                "SELECT fun_prefix FROM guild_branding WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
        # Fall back to global
        async with aiosqlite.connect('db/branding.db') as db:
            async with db.execute(
                "SELECT fun_prefix FROM guild_branding WHERE guild_id = 0"
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
    except Exception:
        pass  # DB missing, column not yet migrated, etc. — just use default
    return DEFAULT_FUN_PREFIX


async def set_fun_prefix(guild_id: int, prefix: str):
    """Persist a fun prefix for a guild (guild_id=0 = global default)."""
    async with aiosqlite.connect('db/branding.db') as db:
        await db.execute(
            "INSERT OR IGNORE INTO guild_branding (guild_id) VALUES (?)", (guild_id,)
        )
        await db.execute(
            "UPDATE guild_branding SET fun_prefix = ? WHERE guild_id = ?",
            (prefix.strip().lower(), guild_id),
        )
        await db.commit()


async def get_global_branding() -> dict:
    """Get global default branding (stored with guild_id = 0).

    Self-healing: automatically migrates a missing fun_prefix column and
    retries rather than propagating a crash to callers.
    """
    _default = {
        "branding_name":   DEFAULT_BRANDING,
        "embed_color":     DEFAULT_COLOR,
        "embed_thumbnail": None,
        "embed_banner":    None,
        "fun_prefix":      DEFAULT_FUN_PREFIX,
    }
    for _attempt in range(2):
        try:
            async with aiosqlite.connect('db/branding.db') as db:
                async with db.execute(
                    "SELECT branding_name, embed_color, embed_thumbnail, embed_banner, fun_prefix "
                    "FROM guild_branding WHERE guild_id = 0"
                ) as cursor:
                    row = await cursor.fetchone()
            if row:
                return {
                    "branding_name":   row[0] if row[0] else DEFAULT_BRANDING,
                    "embed_color":     row[1] if row[1] is not None else DEFAULT_COLOR,
                    "embed_thumbnail": row[2],
                    "embed_banner":    row[3],
                    "fun_prefix":      row[4] if row[4] else DEFAULT_FUN_PREFIX,
                }
            return _default
        except Exception as _e:
            if _attempt == 0 and "fun_prefix" in str(_e):
                try:
                    _setup_branding_db()
                except Exception:
                    pass
                continue
            return _default
    return _default


async def set_global_branding(**kwargs):
    """Set global default branding (guild_id = 0)."""
    valid = {"branding_name", "embed_color", "embed_thumbnail", "embed_banner"}
    data = {k: v for k, v in kwargs.items() if k in valid}
    if not data:
        return
    async with aiosqlite.connect('db/branding.db') as db:
        await db.execute(
            "INSERT OR IGNORE INTO guild_branding (guild_id) VALUES (0)"
        )
        for key, value in data.items():
            await db.execute(
                f"UPDATE guild_branding SET {key} = ? WHERE guild_id = 0",
                (value,)
            )
        await db.commit()


async def reset_branding(guild_id: int):
    """Delete a guild's branding row so it reverts to global/default."""
    async with aiosqlite.connect('db/branding.db') as db:
        await db.execute("DELETE FROM guild_branding WHERE guild_id = ?", (guild_id,))
        await db.commit()


async def get_branding(guild_id: int) -> dict:
    """Get branding for a guild, merging per-field with global then hardcoded defaults.

    Priority per field: guild-specific value → global default (guild_id=0) → hardcoded.
    A guild that has only set some fields will still inherit the rest from global, so
    any change to global customization automatically propagates to guilds that haven't
    overridden that specific field.

    Self-healing: if the fun_prefix column is missing (e.g. right after a Neon
    restore overwrites the DB), the migration is applied automatically and the
    query is retried once rather than crashing the bot.
    """
    for _attempt in range(2):
        try:
            async with aiosqlite.connect('db/branding.db') as db:
                async with db.execute(
                    "SELECT branding_name, embed_color, embed_thumbnail, embed_banner, fun_prefix "
                    "FROM guild_branding WHERE guild_id = ?",
                    (guild_id,)
                ) as cursor:
                    guild_row = await cursor.fetchone()

                async with db.execute(
                    "SELECT branding_name, embed_color, embed_thumbnail, embed_banner, fun_prefix "
                    "FROM guild_branding WHERE guild_id = 0"
                ) as cursor:
                    global_row = await cursor.fetchone()
            break  # success
        except Exception as _e:
            if _attempt == 0 and "fun_prefix" in str(_e):
                # Column missing — run the migration and retry once.
                try:
                    _setup_branding_db()
                except Exception:
                    pass
                continue
            # On second attempt or unrelated error return safe defaults.
            return {
                "branding_name":   DEFAULT_BRANDING,
                "embed_color":     DEFAULT_COLOR,
                "embed_thumbnail": None,
                "embed_banner":    None,
                "fun_prefix":      DEFAULT_FUN_PREFIX,
            }
    else:
        guild_row = None
        global_row = None

    g  = guild_row  or (None, None, None, None, None)
    gl = global_row or (None, None, None, None, None)

    def _pick(guild_val, global_val, hardcoded):
        """First non-null, non-empty value wins. Integer 0 is treated as valid."""
        if guild_val is not None and guild_val != "":
            return guild_val
        if global_val is not None and global_val != "":
            return global_val
        return hardcoded

    return {
        "branding_name":   _pick(g[0], gl[0], DEFAULT_BRANDING),
        "embed_color":     _pick(g[1], gl[1], DEFAULT_COLOR),
        "embed_thumbnail": _pick(g[2], gl[2], None),
        "embed_banner":    _pick(g[3], gl[3], None),
        "fun_prefix":      _pick(g[4], gl[4], DEFAULT_FUN_PREFIX),
    }


async def set_branding(guild_id: int, **kwargs):
    valid = {"branding_name", "embed_color", "embed_thumbnail", "embed_banner"}
    data = {k: v for k, v in kwargs.items() if k in valid}
    if not data:
        return
    async with aiosqlite.connect('db/branding.db') as db:
        await db.execute(
            "INSERT OR IGNORE INTO guild_branding (guild_id) VALUES (?)", (guild_id,)
        )
        for key, value in data.items():
            await db.execute(
                f"UPDATE guild_branding SET {key} = ? WHERE guild_id = ?",
                (value, guild_id)
            )
        await db.commit()


async def get_guild_profile(guild_id: int) -> dict:
    async with aiosqlite.connect('db/branding.db') as db:
        async with db.execute(
            "SELECT display_name, bio, avatar_url, banner_url "
            "FROM guild_profile WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "display_name": row[0],
                    "bio":          row[1],
                    "avatar_url":   row[2],
                    "banner_url":   row[3],
                }
            return {"display_name": None, "bio": None, "avatar_url": None, "banner_url": None}


async def set_guild_profile(guild_id: int, **kwargs):
    valid = {"display_name", "bio", "avatar_url", "banner_url"}
    data = {k: v for k, v in kwargs.items() if k in valid}
    if not data:
        return
    async with aiosqlite.connect('db/branding.db') as db:
        await db.execute(
            "INSERT OR IGNORE INTO guild_profile (guild_id) VALUES (?)", (guild_id,)
        )
        for key, value in data.items():
            await db.execute(
                f"UPDATE guild_profile SET {key} = ? WHERE guild_id = ?",
                (value, guild_id)
            )
        await db.commit()


async def get_custom_activity() -> dict | None:
    """Return the saved custom bot activity dict {type, name}, or None if not set."""
    _type_map = {
        "playing":   discord.ActivityType.playing,
        "watching":  discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "streaming": discord.ActivityType.streaming,
    }
    async with aiosqlite.connect('db/branding.db') as db:
        async with db.execute(
            "SELECT activity_type, activity_name FROM bot_activity WHERE id = 0"
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0] and row[1]:
                atype = _type_map.get(row[0].lower())
                if atype:
                    return {"type": atype, "name": row[1]}
    return None


async def set_custom_activity(activity_type: str, activity_name: str):
    """Persist a custom bot activity so it survives restarts."""
    async with aiosqlite.connect('db/branding.db') as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_activity (id, activity_type, activity_name) "
            "VALUES (0, ?, ?)",
            (activity_type.lower().strip(), activity_name),
        )
        await db.commit()


async def clear_custom_activity():
    """Clear the persisted custom activity so the rotating status resumes."""
    async with aiosqlite.connect('db/branding.db') as db:
        await db.execute("DELETE FROM bot_activity WHERE id = 0")
        await db.commit()


def parse_color(value: str):
    """Parse a hex color string like #FFD700, FFD700, or 0xFFD700 to int."""
    value = value.strip().lstrip('#').lstrip('0x').lstrip('0X')
    try:
        return int(value, 16)
    except ValueError:
        return None


def color_to_hex(color_int: int) -> str:
    return f"#{color_int:06X}"
