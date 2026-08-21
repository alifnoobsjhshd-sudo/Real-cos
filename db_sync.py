"""
db_sync.py — SQLite ↔ Neon PostgreSQL persistence layer

Stores every .db file as a binary blob in a Neon table so data
survives Render redeploys.  All existing aiosqlite code is untouched.

Environment variable required:
    NEON_DATABASE_URL  — Neon connection string (postgresql://...)
"""

import asyncio
import os
import glob
import signal
import asyncpg

# ── Config ─────────────────────────────────────────────────────────────────────

NEON_URL = os.getenv("NEON_DATABASE_URL", "").strip()

# Directories / files to back up (relative to repo root, which is cwd at startup)
_DB_GLOBS = [
    "db/*.db",
    "j2c_data.db",
    "rr.db",
    "branding.db",
    "data/emoji_store.json",
]

# How often to auto-save (seconds)
SYNC_INTERVAL = 60  # 1 minute — short enough that a crash loses very little data

# ── Internal helpers ────────────────────────────────────────────────────────────

def _all_files() -> list[str]:
    """Expand globs → sorted list of existing local paths."""
    paths = []
    for pattern in _DB_GLOBS:
        paths.extend(glob.glob(pattern))
    return sorted(set(paths))


async def _get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(NEON_URL, min_size=1, max_size=3, ssl="require")


async def _ensure_table(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sqlite_backups (
                filename   TEXT PRIMARY KEY,
                data       BYTEA NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)


# ── Public API ──────────────────────────────────────────────────────────────────

async def restore_from_neon():
    """
    Download all backed-up DB files from Neon and write them to disk.
    Called once at startup before the bot connects.
    """
    if not NEON_URL:
        return

    try:
        pool = await _get_pool()
        await _ensure_table(pool)

        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT filename, data FROM sqlite_backups")

        restored = 0
        for row in rows:
            path: str = row["filename"]
            data: bytes = row["data"]
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            restored += 1

        await pool.close()
        print(f"[db_sync] ✓ Restored {restored} file(s) from Neon.")
    except Exception as e:
        print(f"[db_sync] Warning: could not restore from Neon — {e}")


async def save_to_neon():
    """
    Upload all local DB files to Neon.
    Safe to call at any time (upserts, never truncates).
    """
    if not NEON_URL:
        return

    files = _all_files()
    if not files:
        return

    try:
        pool = await _get_pool()
        await _ensure_table(pool)

        saved = 0
        async with pool.acquire() as conn:
            for path in files:
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    await conn.execute("""
                        INSERT INTO sqlite_backups (filename, data, updated_at)
                        VALUES ($1, $2, NOW())
                        ON CONFLICT (filename) DO UPDATE
                            SET data = EXCLUDED.data,
                                updated_at = NOW()
                    """, path, data)
                    saved += 1
                except Exception as fe:
                    print(f"[db_sync] Warning: could not save {path} — {fe}")

        await pool.close()
        print(f"[db_sync] ✓ Saved {saved}/{len(files)} file(s) to Neon.")
    except Exception as e:
        print(f"[db_sync] Warning: could not save to Neon — {e}")


async def _sync_loop():
    """Background task: save every SYNC_INTERVAL seconds."""
    while True:
        await asyncio.sleep(SYNC_INTERVAL)
        await save_to_neon()


def start_sync_loop(bot_loop: asyncio.AbstractEventLoop):
    """
    Schedule the background sync task and register a SIGTERM handler
    so a final save runs before Render kills the container.
    Called from on_ready after the bot is up.
    """
    if not NEON_URL:
        print("[db_sync] NEON_DATABASE_URL not set — persistence disabled.")
        return

    bot_loop.create_task(_sync_loop())

    # Render sends SIGTERM before killing the process — save on the way out.
    def _on_sigterm(*_):
        print("[db_sync] SIGTERM received — saving databases to Neon …")
        future = asyncio.run_coroutine_threadsafe(save_to_neon(), bot_loop)
        try:
            future.result(timeout=20)
            print("[db_sync] Final save complete.")
        except Exception as e:
            print(f"[db_sync] Final save error: {e}")
        raise SystemExit(0)

    try:
        signal.signal(signal.SIGTERM, _on_sigterm)
    except (OSError, ValueError):
        pass  # Can't set signal outside main thread — that's fine
