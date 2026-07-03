import aiosqlite
import sqlite3

DEFAULT_BRANDING = "Sunlight"
DEFAULT_COLOR = 0xFFD700

# guild_id = 0 is used as the "global default" slot


def _setup_branding_db():
    conn = sqlite3.connect('db/branding.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS guild_branding (
            guild_id    INTEGER PRIMARY KEY,
            branding_name TEXT,
            embed_color   INTEGER,
            embed_thumbnail TEXT,
            embed_banner    TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS guild_profile (
            guild_id     INTEGER PRIMARY KEY,
            display_name TEXT,
            bio          TEXT,
            avatar_url   TEXT,
            banner_url   TEXT
        )
    ''')
    conn.commit()
    conn.close()


_setup_branding_db()


async def get_global_branding() -> dict:
    """Get global default branding (stored with guild_id = 0)."""
    async with aiosqlite.connect('db/branding.db') as db:
        async with db.execute(
            "SELECT branding_name, embed_color, embed_thumbnail, embed_banner "
            "FROM guild_branding WHERE guild_id = 0"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "branding_name": row[0] if row[0] else DEFAULT_BRANDING,
                    "embed_color":   row[1] if row[1] is not None else DEFAULT_COLOR,
                    "embed_thumbnail": row[2],
                    "embed_banner":    row[3],
                }
    return {
        "branding_name":   DEFAULT_BRANDING,
        "embed_color":     DEFAULT_COLOR,
        "embed_thumbnail": None,
        "embed_banner":    None,
    }


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
    """Get branding for a guild; falls back to global defaults then hardcoded defaults."""
    async with aiosqlite.connect('db/branding.db') as db:
        async with db.execute(
            "SELECT branding_name, embed_color, embed_thumbnail, embed_banner "
            "FROM guild_branding WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and any(v is not None for v in row):
                return {
                    "branding_name": row[0] if row[0] else DEFAULT_BRANDING,
                    "embed_color":   row[1] if row[1] is not None else DEFAULT_COLOR,
                    "embed_thumbnail": row[2],
                    "embed_banner":    row[3],
                }

    # Fall back to global defaults (guild_id = 0)
    return await get_global_branding()


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


def parse_color(value: str):
    """Parse a hex color string like #FFD700, FFD700, or 0xFFD700 to int."""
    value = value.strip().lstrip('#').lstrip('0x').lstrip('0X')
    try:
        return int(value, 16)
    except ValueError:
        return None


def color_to_hex(color_int: int) -> str:
    return f"#{color_int:06X}"
