import discord
from discord.ext import commands
import json
import os
import asyncio
from utils.branding import DEFAULT_BRANDING
from utils.emojis import e as _e

def CROSS():   return _e("zcross")   or "❌"
def TICK():    return _e("ztick")    or "✅"
def WARNING(): return _e("zwarning") or "⚠️"
def BOOK():    return _e("zmodule")  or "📕"
def PLAY():    return _e("zplay")    or "▶️"
def PAUSE():   return _e("zpause")   or "⏸️"
def STOP():    return _e("musicstop_icons") or "⏹️"
def NEXT():    return _e("zplus")    or "➕"
def BACK():    return _e("zback")    or "◀️"
def ARROW():   return _e("zArrow")   or "➡️"
def PIN():     return _e("zpin")     or "💬"
def STAR():    return _e("starr")    or "⭐"

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "db/counting.json"
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump({}, f)
        with open(self.data_file, 'r') as f:
            self.counting_data = json.load(f)

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.counting_data, f, indent=4)

    def is_enabled(self, guild_id):
        guild_id = str(guild_id)
        return self.counting_data.get(guild_id, {}).get("enabled", False)

    async def not_enabled_embed(self, ctx):
        embed = discord.Embed(
            title=f"{BOOK()} Counting Settings For {ctx.guild.name}",
            color=0xFF0000
        )
        embed.add_field(name="Current Status", value=f"{CROSS()} Disabled", inline=False)
        embed.add_field(name="How to Enable", value="Use `counting enable` to enable counting.", inline=False)
        embed.set_footer(text=f"Powered By {DEFAULT_BRANDING} Development™")
        await ctx.send(embed=embed)

    async def send_help_embed(self, ctx):
        embed = discord.Embed(
            title=f"{BOOK()} Counting Commands",
            description="Manage and control the counting game settings.",
            color=0xFF0000
        )
        embed.add_field(name="counting enable/disable", value="Enable or Disable counting in server", inline=False)
        embed.add_field(name="counting channel #channel", value="Set counting channel", inline=False)
        embed.add_field(name="counting config reset/continue", value="Set reset mode on mistake", inline=False)
        embed.add_field(name="counting reset", value="Reset counting back to 0", inline=False)
        embed.add_field(name="counting stats", value="View current counting stats", inline=False)
        embed.set_footer(text=f"Powered By {DEFAULT_BRANDING} Development™")
        await ctx.send(embed=embed)

    @commands.group(name="counting", invoke_without_command=True)
    async def counting(self, ctx):
        if not self.is_enabled(ctx.guild.id):
            await self.not_enabled_embed(ctx)
        else:
            await self.send_help_embed(ctx)

    @counting.command(name="enable")
    @commands.has_permissions(manage_channels=True)
    async def enable(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id not in self.counting_data:
            self.counting_data[guild_id] = {"enabled": True, "channel": None, "count": 0, "reset_on_fail": False}
        else:
            self.counting_data[guild_id]["enabled"] = True
        self.save_data()
        await ctx.send(f"{TICK()} Counting has been Enabled!")

    @counting.command(name="disable")
    @commands.has_permissions(manage_channels=True)
    async def disable(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id not in self.counting_data:
            await self.not_enabled_embed(ctx)
            return
        self.counting_data[guild_id]["enabled"] = False
        self.save_data()
        await ctx.send(f"{STOP()} Counting has been Disabled!")

    @counting.command(name="channel")
    @commands.has_permissions(manage_channels=True)
    async def channel(self, ctx, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        if not self.is_enabled(guild_id):
            await self.not_enabled_embed(ctx)
            return
        self.counting_data[guild_id]["channel"] = channel.id
        self.save_data()
        await ctx.send(f"{PIN()} Counting channel set to {channel.mention}")

    @counting.command(name="config")
    @commands.has_permissions(manage_channels=True)
    async def config(self, ctx, mode: str):
        guild_id = str(ctx.guild.id)
        if not self.is_enabled(guild_id):
            await self.not_enabled_embed(ctx)
            return
        if mode.lower() in ["reset", "true", "on"]:
            self.counting_data[guild_id]["reset_on_fail"] = True
            msg = f"{TICK()} Counting will now reset on mistakes."
        elif mode.lower() in ["continue", "false", "off"]:
            self.counting_data[guild_id]["reset_on_fail"] = False
            msg = f"{TICK()} Counting will now continue on mistakes."
        else:
            await ctx.send(f"{CROSS()} Invalid mode! Use `reset` or `continue`.")
            return
        self.save_data()
        await ctx.send(msg)

    @counting.command(name="reset")
    @commands.has_permissions(manage_channels=True)
    async def reset(self, ctx):
        guild_id = str(ctx.guild.id)
        if not self.is_enabled(guild_id):
            await self.not_enabled_embed(ctx)
            return
        self.counting_data[guild_id]["count"] = 0
        self.save_data()
        await ctx.send(f"{NEXT()} Counting has been reset to 0!")

    @counting.command(name="stats")
    async def stats(self, ctx):
        guild_id = str(ctx.guild.id)
        if not self.is_enabled(guild_id):
            await self.not_enabled_embed(ctx)
            return
        data = self.counting_data[guild_id]
        channel = ctx.guild.get_channel(data["channel"]) if data["channel"] else None
        embed = discord.Embed(title=f"{BOOK()} Counting Stats", color=0xFF0000)
        embed.add_field(name="Current Count", value=str(data["count"]), inline=False)
        embed.add_field(name="Channel", value=channel.mention if channel else "Not Set", inline=False)
        embed.add_field(name="Reset on Mistake", value=str(data["reset_on_fail"]), inline=False)
        embed.set_footer(text=f"Powered By {DEFAULT_BRANDING} Development™")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        guild_id = str(message.guild.id)
        if guild_id not in self.counting_data:
            return

        data = self.counting_data[guild_id]
        if not data.get("enabled", False):
            return

        if message.channel.id != data.get("channel"):
            return

        content = message.content.strip()

        if not content.isdigit():
            msg = await message.channel.send(f"{WARNING()} Alphabet not allowed!")
            await asyncio.sleep(3)
            await msg.delete()
            await message.delete()
            return

        number = int(content)
        expected_number = data.get("count", 0) + 1

        if number != expected_number:
            msg = await message.channel.send(f"{CROSS()} Wrong number entered! Expected number is **{expected_number}**")
            await asyncio.sleep(3)
            await msg.delete()
            await message.delete()
            if data.get("reset_on_fail", False):
                self.counting_data[guild_id]["count"] = 0
                self.save_data()
            return

        # Correct number
        self.counting_data[guild_id]["count"] = number
        self.save_data()
def setup(bot):
    bot.add_cog(Counting(bot))