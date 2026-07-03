import discord
import psutil
import sys
import os
import time
import aiosqlite
import datetime
from discord import Embed
from discord.ext import commands
from discord.ui import View, Select
from utils.Tools import *
import wavelink

# Dynamically analyze codebase
def analyze_codebase(path="."):
    total_files = total_lines = total_words = 0
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith((".py", ".js", ".json", ".ts", ".html", ".css", ".env", ".txt")):
                total_files += 1
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        total_lines += len(lines)
                        total_words += sum(len(line.split()) for line in lines)
                except:
                    continue
    return total_files, total_lines, total_words

class StatsDropdown(Select):
    def __init__(self, ctx, bot, embeds):
        self.ctx = ctx
        self.bot = bot
        self.embeds = embeds

        options = [
            discord.SelectOption(label="System Info", emoji="<:zyrox_system:1448949359159939143>", description="System usage and performance."),
            discord.SelectOption(label="General Info", emoji="<:zyrox_global:1448949370539217026>", description="General Informations About Bot."),
            discord.SelectOption(label="Team Info", emoji="<:codebase:1448951697853386826>", description="Bot creators and team."),
            discord.SelectOption(label="Code Info", emoji="<:zyrox_search:1448949381436014662>", description="Stats of bot's source files."),
        ]

        super().__init__(placeholder="Zyrox Statistics.", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Only the command invoker can use this menu.", ephemeral=True)

        embed = self.embeds[self.values[0]]
        await interaction.response.edit_message(embed=embed)

class StatsDropdownView(View):
    def __init__(self, ctx, bot, embeds):
        super().__init__(timeout=None)
        self.add_item(StatsDropdown(ctx, bot, embeds))

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.total_songs_played = 0
        self.command_usage_count = 0
        self.bot.loop.create_task(self.setup_database())

    async def setup_database(self):
        async with aiosqlite.connect("db/stats.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)")
            await db.commit()

            async with db.execute("SELECT value FROM stats WHERE key = 'total_songs_played'") as cursor:
                row = await cursor.fetchone()
                self.total_songs_played = row[0] if row else 0

            async with db.execute("SELECT value FROM stats WHERE key = 'command_usage_count'") as cursor:
                row = await cursor.fetchone()
                self.command_usage_count = row[0] if row else 0

    def format_number(self, num):
        if num < 1000:
            return str(num)
        elif num < 1_000_000:
            return f"{num / 1_000:.4f}k"
        elif num < 1_000_000_000:
            return f"{num / 1_000_000:.2f}M"
        else:
            return f"{num / 1_000_000_000:.2f}B"

    @commands.hybrid_command(name="stats", aliases=["botstats", "statistics", "botinfo"], help="Shows the bot's information.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def stats(self, ctx):
        
        loading_embed = discord.Embed(title="", description="<a:loading:1448949404185657354> **Generating Zyrox Statistics...**", color=0x00000)
        loading_msg = await ctx.reply(embed=loading_embed)
        # Uptime & formatting
        uptime = str(datetime.timedelta(seconds=int(round(time.time() - self.start_time))))
        total_users = sum(g.member_count for g in self.bot.guilds if g.member_count)
        wsping = round(self.bot.latency * 1000, 2)
        slash_cmds = len(self.bot.tree.get_commands())
        all_cmds = len(set(self.bot.walk_commands()))
        formatted_uses = self.format_number(self.command_usage_count)
        cpu_usage = psutil.cpu_percent(interval=None)
        ram_usage = psutil.virtual_memory().percent
        
        
        quick_embed = Embed(title="Zyrox Stats Panel", color=0xFF0000)
        quick_embed.add_field(name="<:zyroxthunder:1448949415200034907> Quick Overview", value=f"**Servers : {len(self.bot.guilds)}\nUsers : {total_users}\nUptime : {uptime}**")
        quick_embed.set_thumbnail(url=ctx.me.display_avatar.url)
        quick_embed.set_footer(text="Use dropdown menu to view detailed stats.")

        # System Embed
        system_embed = Embed(title=" System Stats", color=0xFF0000)
        system_embed.add_field(name="Hardware",
                               value=f"** Cpu Usage : {cpu_usage}%\n Ram Usage : {ram_usage}%**", inline=False)
        system_embed.add_field(name="Software", value=f"** Python :  {sys.version_info.major}.{sys.version_info.minor}\n D.py : {discord.__version__}**")
        system_embed.set_thumbnail(url=ctx.me.display_avatar.url)
        system_embed.set_footer(text="Devloped By Zyrox Development™", icon_url="https://cdn.discordapp.com/avatars/1396114795102470196/198b9bc616ec574f6fd2f7121a1d3abc.png?size=1024")

        # General Embed
        general_embed = Embed(title="General Stats", description=f"**Uptime**: `{uptime}`", color=0xFF0000)
        general_embed.add_field(name="Server Stats",
                                value=(
                                    f"**Guilds : {len(self.bot.guilds)}\n Users : {total_users}**"
                                ),
                                inline=False)
        general_embed.add_field(name="Commands Stats", value=f"** Total CMDS : {all_cmds}\n Slash CMDS : {slash_cmds}**")
      #  general_embed.add_field(name="Latency", value=f"```[ Bot ]: {round(sh.latency * 800)}ms\n[ Database ]: 0.5ms```")
        general_embed.set_thumbnail(url=ctx.me.display_avatar.url)
        general_embed.set_footer(text="Devloped By Zyrox Development™", icon_url="https://cdn.discordapp.com/avatars/1396114795102470196/198b9bc616ec574f6fd2f7121a1d3abc.png?size=1024")

        # Team Embed
        team_embed = Embed(title="Team Stats",
                           description="`There is only one person Who Made Me, Thanks To Him ❤️.`", color=0xFF0000)
        team_embed.add_field(name="Main Owner",
                             value="**[01]. [. Evil ! Rexy .](https://discord.com/users/870179991462236170)**", inline=False)
        team_embed.set_footer(text="Developed By Zyrox Development™", icon_url="https://cdn.discordapp.com/avatars/1396114795102470196/198b9bc616ec574f6fd2f7121a1d3abc.png?size=1024")
        team_embed.set_thumbnail(url=ctx.me.display_avatar.url)

        # Code Analysis Embed
        files, lines, words = analyze_codebase(".")
        code_embed = Embed(title="Code Stats",
                           color=0xFF0000)
        code_embed.add_field(name="Codebase Overview",
                             value=f"""**\n Files : {files}\n Lines : {lines}\n Words : {words}**""",
                             inline=False)
        code_embed.set_footer(text="Developed By Zyrox Development™", icon_url="https://cdn.discordapp.com/avatars/1396114795102470196/198b9bc616ec574f6fd2f7121a1d3abc.png?size=1024")
        code_embed.set_thumbnail(url=ctx.me.display_avatar.url)

        embeds = {
            "System Info": system_embed,
            "General Info": general_embed,
            "Team Info": team_embed,
            "Code Info": code_embed
        }

        view = StatsDropdownView(ctx, self.bot, embeds)
        await loading_msg.edit(embed=quick_embed, view=view)
        #await loading_msg.delete()

async def setup(bot):
    await bot.add_cog(Stats(bot))
