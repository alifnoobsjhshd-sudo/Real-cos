import os
os.system("")
# Pin working directory to the script's location so all relative DB paths always resolve correctly
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── Persistent disk support (Render / any host with ephemeral filesystem) ──────
# Set DATA_DIR env var to your Render persistent disk mount path (e.g. /data).
# All SQLite databases and the emoji store are symlinked there on startup so
# they survive redeploys — no other code needs to change.
import shutil as _shutil

_DATA_DIR = os.getenv("DATA_DIR", "").strip()
if _DATA_DIR:
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)

        def _migrate_dir(local: str, persistent: str):
            """
            Recursively copy local/ to persistent/ (first run only, non-destructive),
            then atomically replace local/ with a symlink to persistent/.
            Safe to call on every startup — idempotent once the symlink is in place.
            """
            # Already a symlink pointing to the right place — nothing to do.
            if os.path.islink(local):
                return

            os.makedirs(persistent, exist_ok=True)

            if os.path.isdir(local):
                # Copy everything recursively; don't overwrite files already on disk.
                for _root, _dirs, _files in os.walk(local):
                    _rel = os.path.relpath(_root, local)
                    _dst_root = os.path.join(persistent, _rel)
                    os.makedirs(_dst_root, exist_ok=True)
                    for _fname in _files:
                        _src_f = os.path.join(_root, _fname)
                        _dst_f = os.path.join(_dst_root, _fname)
                        if not os.path.exists(_dst_f):
                            _shutil.copy2(_src_f, _dst_f)
                # Atomic-ish replace: rename away, then symlink.
                _tmp = local + ".__migrate_bak__"
                os.rename(local, _tmp)
                try:
                    os.symlink(persistent, local)
                    _shutil.rmtree(_tmp, ignore_errors=True)
                except Exception:
                    # Roll back on failure so the bot can still start.
                    os.rename(_tmp, local)
                    raise
            elif not os.path.exists(local):
                os.symlink(persistent, local)

        def _migrate_file(local: str, persistent: str):
            """
            Copy single file to persistent/ (first run only), then replace with symlink.
            Idempotent — safe on every restart.
            """
            if os.path.islink(local):
                return  # already migrated
            if os.path.isfile(local):
                if not os.path.exists(persistent):
                    _shutil.copy2(local, persistent)
                # Atomic-ish replace.
                _tmp = local + ".__migrate_bak__"
                os.rename(local, _tmp)
                try:
                    os.symlink(persistent, local)
                    os.remove(_tmp)
                except Exception:
                    os.rename(_tmp, local)
                    raise
            elif not os.path.exists(local):
                os.symlink(persistent, local)

        _migrate_dir("db",   os.path.join(_DATA_DIR, "db"))
        _migrate_dir("data", os.path.join(_DATA_DIR, "data"))
        for _dbf in ["j2c_data.db", "rr.db"]:
            _migrate_file(_dbf, os.path.join(_DATA_DIR, _dbf))

        print(f"[DATA_DIR] Persistent storage linked → {_DATA_DIR}")
    except Exception as _data_err:
        print(f"[DATA_DIR] Warning: could not link persistent storage: {_data_err}")
# ───────────────────────────────────────────────────────────────────────────────
import asyncio
import traceback
from threading import Thread
from datetime import datetime
import random
import time
from db_sync import restore_from_neon, start_sync_loop

import aiohttp
import discord
from discord import Spotify
from discord.ext import commands, tasks

from core import Context
from core.Cog import Cog
from core.zyrox import zyrox
from utils.Tools import *
from utils.config import *

import jishaku
import cogs

os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

TOKEN = os.getenv("TOKEN")

# --- Configuration ---
# IMPORTANT: Replace these with your actual channel IDs.
SERVER_COUNT_CHANNEL_ID = 1419729255977189467  # Replace with your server count channel ID
USER_COUNT_CHANNEL_ID = 1419729283861184632    # Replace with your user count channel ID
LOG_CHANNEL_ID = 1396794297386532978 # Replace with the channel ID for join/leave logs


client = zyrox()
tree = client.tree

# --- Background Task for Stats ---
async def update_stats():
    """A background task to update server and user stats in channel names."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            servers = len(client.guilds)
            users = sum(guild.member_count for guild in client.guilds if guild.member_count is not None)
            
            server_channel = client.get_channel(SERVER_COUNT_CHANNEL_ID)
            user_channel = client.get_channel(USER_COUNT_CHANNEL_ID)
            
            if server_channel:
                await server_channel.edit(name=f"Servers: {servers}")
            
            if user_channel:
                await user_channel.edit(name=f"Users: {users}")
                
        except Exception as e:
            print(f"Error updating stats: {e}")
        
        await asyncio.sleep(600) # Update every 10 minutes

# --- Event Handlers ---
@client.event
async def on_ready():
    await client.wait_until_ready()
    
    print("""
        \033[1;31m
 ██████╗ ██████╗ ██████╗ ███████╗██╗  ██╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝╚██╗██╔╝
██║     ██║   ██║██║  ██║█████╗   ╚███╔╝ 
██║     ██║   ██║██║  ██║██╔══╝   ██╔██╗ 
╚██████╗╚██████╔╝██████╔╝███████╗██╔╝ ██╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
        \033[0m
       """)
    print("Loaded & Online!")
    print(f"Logged in as: {client.user}")
    print(f"Connected to: {len(client.guilds)} guilds")
    print(f"Connected to: {len(client.users)} users")
    try:
        synced = await client.tree.sync()
        all_commands = list(client.commands)
        print(f"Synced Total {len(all_commands)} Client Commands and {len(synced)} Slash Commands")
    except Exception as e:
        print(e)

    start_sync_loop(client.loop)
    client.loop.create_task(update_stats())


@client.event
async def on_guild_join(guild: discord.Guild):
    # Log when the bot joins a server
    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        from utils.branding import DEFAULT_BRANDING
        await log_channel.send(f"{DEFAULT_BRANDING} has been added to the server: **{guild.name}** (ID: `{guild.id}`)")

@client.event
async def on_command_completion(context: commands.Context) -> None:
    pass


# --- Utility Commands ---
@client.command(name='spotify')
async def spotify(ctx: Context, user: discord.Member = None):
    """Shows what a user is listening to on Spotify."""
    user = user or ctx.author
    spotify_activity = next((activity for activity in user.activities if isinstance(activity, Spotify)), None)

    if not spotify_activity:
        return await ctx.send(f"{user.name} is not listening to Spotify.")
    
    embed = discord.Embed(
        title=f"{user.name}'s Spotify",
        description=f"**Listening to:** {spotify_activity.title}",
        color=0x1DB954 # Spotify Green
    )
    embed.set_thumbnail(url=spotify_activity.album_cover_url)
    embed.add_field(name="Artist", value=spotify_activity.artist)
    embed.add_field(name="Album", value=spotify_activity.album)
    embed.set_footer(text=f"Song started at {spotify_activity.created_at.strftime('%H:%M')}")
    await ctx.send(embed=embed)


@client.command(name='makeinvite', aliases=['createinvite', 'makeinv'])
@commands.is_owner()
async def make_invite(ctx: Context, guild_id: int = None):
    """Creates an invite for a specified server (owner only)."""
    if guild_id is None:
        return await ctx.send("Please provide a Guild ID.")
        
    guild = client.get_guild(guild_id)
    if not guild:
        return await ctx.send("Invalid Guild ID. I am not in that server.")

    if guild.system_channel and guild.system_channel.permissions_for(guild.me).create_instant_invite:
        try:
            invite = await guild.system_channel.create_invite(max_age=0, max_uses=0, unique=True, reason="Owner requested invite.")
            return await ctx.send(f"Invite for **{guild.name}**:\n{invite.url}")
        except Exception:
            pass

    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).create_instant_invite:
            try:
                invite = await channel.create_invite(max_age=0, max_uses=0, unique=True, reason="Owner requested invite.")
                return await ctx.send(f"Invite for **{guild.name}** (from #{channel.name}):\n{invite.url}")
            except Exception:
                continue
                
    await ctx.send(f"I don't have 'Create Instant Invite' permission in any channel in **{guild.name}**.")


# --- Webhook Management Commands ---
@client.command(name='create_hook', aliases=['makehook'])
@commands.has_permissions(administrator=True)
async def create_hook(ctx: Context, *, name: str = None):
    """Creates a webhook in the current channel."""
    if name is None:
        return await ctx.send("Please provide a name for the webhook.")
    
    try:
        webhook = await ctx.channel.create_webhook(name=name, reason=f"Created by {ctx.author}")
        embed = discord.Embed(
            title="✅ Webhook Created",
            description=f"A webhook named **{webhook.name}** was created.",
            color=0xFF0000
        )
        await ctx.author.send(f"Webhook URL for **{webhook.name}** in **{ctx.channel.name}**:\n||{webhook.url}||", embed=embed)
        await ctx.send("Webhook created. I've sent the URL to your DMs.")
    except discord.Forbidden:
        await ctx.send("I don't have permission to create webhooks here.")
    except Exception:
        await ctx.send(f"Webhook created: **{webhook.name}**\n||{webhook.url}||\n(I could not DM you the URL.)")


@client.command(name='delete_hook', aliases=['delhook'])
@commands.has_permissions(administrator=True)
async def delete_hook(ctx: Context, webhook_url: str = None):
    """Deletes a webhook using its URL."""
    if webhook_url is None:
        return await ctx.send("Please provide the webhook URL to delete.")

    try:
        async with aiohttp.ClientSession() as session:
            webhook = await discord.Webhook.from_url(webhook_url, session=session)
            await webhook.delete(reason=f"Deleted by {ctx.author}")
        await ctx.send("✅ Webhook deleted successfully.")
    except (discord.NotFound, ValueError):
        await ctx.send("❌ Webhook not found or URL is invalid.")


@client.command(name='list_hooks', aliases=['hooks'])
@commands.has_permissions(administrator=True)
async def list_hooks(ctx: Context):
    """Lists all webhooks in the current channel."""
    try:
        webhooks = await ctx.channel.webhooks()
        if not webhooks:
            return await ctx.send("No webhooks found in this channel.")

        embed = discord.Embed(title=f"Webhooks in #{ctx.channel.name}", color=0xFF0000)
        description = "\n".join([f"**Name:** {wh.name} | **ID:** `{wh.id}`" for wh in webhooks])
        embed.description = description
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to view webhooks in this channel.")


# --- Game Command ---
@client.command()
async def reaction(ctx: Context):
    """See how fast you can react to the correct emoji."""
    emojis = ["🍪", "🎉", "🧋", "🍒", "🍑", "💸", "🌙", "💕"]
    correct_emoji = random.choice(emojis)
    random.shuffle(emojis)
    
    embed = discord.Embed(
        title="Reaction Test",
        description="I will show an emoji in a few seconds. Get ready to click it!",
        color=0xFF0000
    )
    message = await ctx.send(embed=embed)
    
    for emoji in emojis:
        await message.add_reaction(emoji)
        
    await asyncio.sleep(random.uniform(2.0, 7.0))
    
    embed.description = f"**GET THE {correct_emoji} EMOJI!**"
    await message.edit(embed=embed)
    start_time = time.time()

    def check(reaction, user):
        return (
            reaction.message.id == message.id
            and str(reaction.emoji) == correct_emoji
            and user == ctx.author
        )

    try:
        reaction, user = await client.wait_for("reaction_add", timeout=15.0, check=check)
        end_time = time.time()
        reaction_time = end_time - start_time
        
        embed.description = f"{user.mention} got the {correct_emoji} in **{reaction_time:.2f} seconds**!"
        await message.edit(embed=embed)
    except asyncio.TimeoutError:
        embed.description = "Timeout! You were too slow."
        await message.edit(embed=embed)


# --- Keep Alive Server ---
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    from utils.branding import DEFAULT_BRANDING
    return f"{DEFAULT_BRANDING} © 2025"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    server = Thread(target=run)
    server.start()

keep_alive()

# --- Main Bot Execution ---
async def main():
    if not TOKEN:
        print("\n" + "="*60)
        print("ERROR: Discord bot TOKEN is missing!")
        print("Go to the Secrets tab and add your bot token as TOKEN.")
        print("="*60 + "\n")
        return

    # Small startup delay — prevents hammering Discord's login endpoint
    # on rapid redeploys (which triggers the identify rate limit).
    await asyncio.sleep(5)

    async with client:
        await restore_from_neon()
        await client.load_extension("jishaku")
        try:
            await client.start(TOKEN)
        except discord.LoginFailure:
            print("\n" + "="*60)
            print("ERROR: Invalid bot TOKEN — login failed.")
            print("Check that TOKEN is set correctly in Render → Environment.")
            print("="*60 + "\n")
        except discord.HTTPException as e:
            if e.status == 429:
                # Rate limited on first login — exit cleanly.
                # Render will restart the service automatically, adding natural delay.
                print(f"[startup] Discord login rate-limited (HTTP 429). Exiting so Render can restart with delay...")
            else:
                raise

if __name__ == "__main__":
    asyncio.run(main())
