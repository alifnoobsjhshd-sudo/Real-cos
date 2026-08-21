"""
utils/supabase_client.py
────────────────────────
Centralised Supabase client for the CodeX / Zyrox bot.

Usage anywhere in the bot:
    from utils.supabase_client import get_supabase

    sb = get_supabase()
    data = sb.table("my_table").select("*").execute()

Never cache the client object across awaits — always call get_supabase() fresh.

Secrets required (add in Replit Secrets tab or Render Environment):
    SUPABASE_URL   — e.g. https://xyzxyz.supabase.co
    SUPABASE_KEY   — your project's anon key (or service-role key for admin ops)
"""

import os
from supabase import create_client, Client

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
_SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()


def get_supabase() -> Client:
    """
    Return a fresh Supabase client.

    Raises RuntimeError if the required environment variables are missing so
    the error is obvious rather than a silent auth failure.
    """
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        raise RuntimeError(
            "Supabase is not configured. "
            "Set SUPABASE_URL and SUPABASE_KEY in the Replit Secrets tab "
            "(or your Render environment variables)."
        )
    return create_client(_SUPABASE_URL, _SUPABASE_KEY)


# ── Convenience wrappers ──────────────────────────────────────────────────────

async def sb_select(table: str, filters: dict | None = None) -> list[dict]:
    """
    Fetch all rows from *table*, optionally filtered by column=value pairs.

    Example:
        rows = await sb_select("guilds", {"guild_id": str(ctx.guild.id)})
    """
    sb = get_supabase()
    query = sb.table(table).select("*")
    if filters:
        for col, val in filters.items():
            query = query.eq(col, val)
    response = query.execute()
    return response.data or []


async def sb_upsert(table: str, row: dict, on_conflict: str = "id") -> list[dict]:
    """
    Insert *row* into *table*, or update it if a row with the same
    *on_conflict* column value already exists.

    Example:
        await sb_upsert("guilds", {"id": str(guild.id), "prefix": ">"}, on_conflict="id")
    """
    sb = get_supabase()
    response = sb.table(table).upsert(row, on_conflict=on_conflict).execute()
    return response.data or []


async def sb_delete(table: str, filters: dict) -> list[dict]:
    """
    Delete rows from *table* matching all column=value pairs in *filters*.

    Example:
        await sb_delete("warns", {"guild_id": str(guild.id), "user_id": str(user.id)})
    """
    sb = get_supabase()
    query = sb.table(table).delete()
    for col, val in filters.items():
        query = query.eq(col, val)
    response = query.execute()
    return response.data or []
