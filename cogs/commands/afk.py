import discord
from discord.ext import commands
from discord import ui
import aiosqlite
import os
import time

# Your custom imports are kept for compatibility
from utils.Tools import blacklist_check, ignore_check

DB_PATH = "db/afk.db"
THEME_COLOR = 0xFF0000
from utils.branding import DEFAULT_BRANDING
FOOTER_TEXT = f"Powered by {DEFAULT_BRANDING}"

# --- View for Buttons ---
class AfkTypeView(ui.View):
    def __init__(self, author, timeout=60):
        super().__init__(timeout=timeout)
        self.author = author
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                f"Only **{self.author.display_name}** can use this button.", ephemeral=True)
            return False
        return True

    @ui.button(label="Global AFK", style=discord.ButtonStyle.primary)
    async def global_afk(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "global"
        await interaction.response.defer()
        self.stop()

    @ui.button(label="Local AFK", style=discord.ButtonStyle.success)
    async def local_afk(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "local"
        await interaction.response.defer()
        self.stop()

# --- Main AFK Cog ---
class afk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.theme_color = THEME_COLOR
        self.bot.loop.create_task(self.initialize_db())

    async def initialize_db(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS afk (
                    user_id INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    time INTEGER NOT NULL,
                    mentions INTEGER NOT NULL DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS afk_guild (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            await db.commit()

    async def time_formatter(self, seconds: float):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        parts = []
        if d > 0: parts.append(f"{d}d")
        if h > 0: parts.append(f"{h}h")
        if m > 0: parts.append(f"{m}m")
        if s > 0: parts.append(f"{s}s")
        return " ".join(parts) or "0s"

    # --- CORE LOGIC FIX #1 ---
    async def set_afk(self, user, afk_type, reason, current_guild=None):
        async with aiosqlite.connect(DB_PATH) as db:
            # First, clear any previous guild associations to prevent conflicts.
            await db.execute("DELETE FROM afk_guild WHERE user_id = ?", (user.id,))
            
            # Set the new AFK status.
            await db.execute(
                "INSERT OR REPLACE INTO afk (user_id, type, reason, time, mentions) VALUES (?, ?, ?, ?, 0)",
                (user.id, afk_type, reason, int(time.time()))
            )
            # Add new guild associations based on the type.
            if afk_type == "global":
                for g in self.bot.guilds:
                    if g.get_member(user.id):
                        await db.execute("INSERT OR IGNORE INTO afk_guild (user_id, guild_id) VALUES (?, ?)", (user.id, g.id))
            elif current_guild:
                await db.execute("INSERT OR IGNORE INTO afk_guild (user_id, guild_id) VALUES (?, ?)", (user.id, current_guild.id))
            
            await db.commit()

    # --- CORE LOGIC FIX #2 ---
    async def clear_afk(self, message):
        async with aiosqlite.connect(DB_PATH) as db:
            # Check if user is AFK in the guild where message was sent.
            cursor = await db.execute("SELECT 1 FROM afk_guild WHERE user_id = ? AND guild_id = ?", (message.author.id, message.guild.id))
            if not await cursor.fetchone():
                return  # Not AFK in this guild, so do nothing.

            # Get main AFK data.
            cursor = await db.execute("SELECT type, time, mentions FROM afk WHERE user_id = ?", (message.author.id,))
            afk_data = await cursor.fetchone()
            if not afk_data: return

            afk_type, afk_time, mentions = afk_data
            elapsed_time = await self.time_formatter(time.time() - afk_time)

            # Correctly clear AFK based on type.
            if afk_type == 'global':
                # If global, remove all AFK data for the user.
                await db.execute("DELETE FROM afk WHERE user_id = ?", (message.author.id,))
                await db.execute("DELETE FROM afk_guild WHERE user_id = ?", (message.author.id,))
            else:  # local
                # If local, only remove from this specific guild.
                await db.execute("DELETE FROM afk_guild WHERE user_id = ? AND guild_id = ?", (message.author.id, message.guild.id))
                # Check if they are AFK anywhere else.
                cursor_check = await db.execute("SELECT 1 FROM afk_guild WHERE user_id = ?", (message.author.id,))
                if not await cursor_check.fetchone():
                    # If not, remove their main AFK record.
                    await db.execute("DELETE FROM afk WHERE user_id = ?", (message.author.id,))
            
            await db.commit()
            
            # Send the welcome back embed.
            from utils.emojis import e as _e
            embed = discord.Embed(
                title=f"{message.author.display_name} Is Back!",
                description=f"{_e('ztick')} **AFK Removed**\n{_e('zcast')} **Mentions:** {mentions}\n{_e('ztimer')} **AFK Time:** {elapsed_time}",
                color=self.theme_color
            )
            embed.set_footer(text=FOOTER_TEXT, icon_url=self.bot.user.display_avatar.url)
            try:
                await message.reply(embed=embed, delete_after=10, mention_author=False)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # This will now correctly clear AFK status.
        await self.clear_afk(message)

        if not message.mentions:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            for mentioned in message.mentions:
                if mentioned.bot or mentioned.id == message.author.id:
                    continue

                cursor = await db.execute("SELECT 1 FROM afk_guild WHERE user_id = ? AND guild_id = ?", (mentioned.id, message.guild.id))
                if await cursor.fetchone():
                    cursor_main = await db.execute("SELECT reason, mentions FROM afk WHERE user_id = ?", (mentioned.id,))
                    afk_data = await cursor_main.fetchone()
                    if not afk_data: continue
                    
                    reason, mentions = afk_data
                    
                    await message.reply(embed=discord.Embed(description=f"**{mentioned.display_name}** is AFK: {reason}", color=self.theme_color), delete_after=10, mention_author=False)
                    
                    new_mentions = mentions + 1
                    await db.execute("UPDATE afk SET mentions = ? WHERE user_id = ?", (new_mentions, mentioned.id))
                    await db.commit()

                    dm_embed = discord.Embed(description=f"You were mentioned in **{message.guild.name}** by **{message.author}**", color=self.theme_color)
                    dm_embed.add_field(name="Total Mentions", value=str(new_mentions))
                    dm_embed.add_field(name="Jump to Message", value=f"[Click Here]({message.jump_url})")
                    dm_embed.set_footer(text=FOOTER_TEXT, icon_url=self.bot.user.display_avatar.url)
                    try:
                        await mentioned.send(embed=dm_embed)
                    except discord.Forbidden:
                        pass

    @commands.hybrid_command(name="afk", description="Set your AFK status with a reason (Global or Local).")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def afk(self, ctx: commands.Context, *, reason: str = "I am AFK"):
        if any(w in reason.lower() for w in ("discord.gg", "gg/")):
            from utils.emojis import e as _e
            return await ctx.send(embed=discord.Embed(description=f"{_e('zwarning')} Advertising is not allowed in AFK reasons.", color=self.theme_color), ephemeral=True)

        type_view = AfkTypeView(ctx.author)
        embed = discord.Embed(description="Select your preferred AFK type from the buttons below.", color=self.theme_color)
        embed.set_footer(text=FOOTER_TEXT, icon_url=self.bot.user.display_avatar.url)
        
        msg = await ctx.reply(embed=embed, view=type_view, mention_author=False)
        await type_view.wait()

        if not type_view.value:
            await msg.edit(content="Timed out.", embed=None, view=None)
            return

        # Now calls the fixed set_afk function
        await self.set_afk(ctx.author, type_view.value, reason, ctx.guild)
        
        from utils.emojis import e as _e
        confirm_embed = discord.Embed(
            title=f"{_e('ztick')} AFK Activated",
            description=f"**{_e('zcast')} You are now marked as {type_view.value.capitalize()} AFK.**\n{_e('zseed')} **Reason:** {reason}",
            color=self.theme_color
        )
        confirm_embed.set_footer(text=FOOTER_TEXT, icon_url=self.bot.user.display_avatar.url)
        await msg.edit(embed=confirm_embed, view=None)

async def setup(bot):
    await bot.add_cog(afk(bot))
