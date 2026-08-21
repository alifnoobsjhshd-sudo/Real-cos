"""
utils/log_bridge.py — Shared helper for antinuke/automod to send logs to the
main Logging cog (logging.py / jsondb/logging_config.json).

Usage:
    from utils.log_bridge import send_antinuke_log, send_automod_log

    await send_antinuke_log(bot, guild, title="Anti-Ban Triggered",
                            description="...", executor=executor, target=user)
    await send_automod_log(bot, guild, rule="Anti Spam",
                           user=member, channel=channel, action="Muted 12 min")
"""
from __future__ import annotations
import discord
from datetime import datetime


async def send_antinuke_log(
    bot,
    guild: discord.Guild,
    title: str,
    description: str = "",
    executor: discord.Member | discord.User | None = None,
    target: discord.Member | discord.User | None = None,
    color: int = 0xFF0000,
):
    """Send an antinuke action to the main member_moderation log channel."""
    try:
        log_cog = bot.get_cog("Logging")
        if not log_cog:
            return
        from utils.emojis import e as _e
        embed = discord.Embed(
            title=f"{_e('zSafe') or '🛡️'}  {title}",
            description=description,
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Server", value=guild.name, inline=True)
        if executor:
            embed.add_field(name="Executor", value=f"{executor.mention} (`{executor}`)", inline=True)
        if target:
            embed.add_field(name="Target", value=f"{target.mention} (`{target}`)", inline=True)
            embed.set_thumbnail(url=getattr(target.display_avatar, "url", ""))
        embed.set_footer(text=f"Antinuke • Guild ID: {guild.id}")
        await log_cog._send_log(guild, "member_moderation", embed)
    except Exception:
        pass


async def send_automod_log(
    bot,
    guild: discord.Guild,
    rule: str,
    user: discord.Member,
    channel: discord.TextChannel | None = None,
    action: str = "",
    reason: str = "",
    color: int = 0xFF0000,
):
    """Send an automod action to the main member_moderation log channel."""
    try:
        log_cog = bot.get_cog("Logging")
        if not log_cog:
            return
        from utils.emojis import e as _e
        embed = discord.Embed(
            title=f"{_e('zmodule') or '🤖'}  Automod — {rule}",
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="User", value=f"{user.mention} (`{user}`)", inline=True)
        if channel:
            embed.add_field(name="Channel", value=channel.mention, inline=True)
        if action:
            embed.add_field(name="Action", value=action, inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=getattr(user.display_avatar, "url", ""))
        embed.set_footer(text=f"Automod • User ID: {user.id}")
        await log_cog._send_log(guild, "member_moderation", embed)
    except Exception:
        pass
