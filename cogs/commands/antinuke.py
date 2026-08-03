import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.Tools import *
from utils.branding import DEFAULT_BRANDING, get_branding


class Antinuke(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self.bot.loop.create_task(self.initialize_db())

  async def initialize_db(self):
    self.db = await aiosqlite.connect('db/anti.db')
    await self.db.execute('''
        CREATE TABLE IF NOT EXISTS antinuke (
            guild_id INTEGER PRIMARY KEY,
            status BOOLEAN
        )
    ''')
    await self.db.commit()


  @commands.hybrid_command(name='antinuke', aliases=['antiwizz', 'anti'], help="Enables/Disables Anti-Nuke Module in the server")
  
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 4, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def antinuke(self, ctx, option: str = None):
    guild_id = ctx.guild.id
    pre=ctx.prefix

    async with self.db.execute('SELECT status FROM antinuke WHERE guild_id = ?', (guild_id,)) as cursor:
      row = await cursor.fetchone()

    async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

    is_owner = ctx.author.id == ctx.guild.owner_id
    if not is_owner and not check:
      embed = discord.Embed(title="❌ Access Denied",
                color=0xFF0000,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
      return await ctx.send(embed=embed)

    is_activated = row[0] if row else False

    if option is None:
      embed = discord.Embed(
        title=f'🛡️ {DEFAULT_BRANDING} Security',
        description="**Antinuke Defense Mode** — Protect your server from harmful admin actions with smart automated security protocols.\n\n"
            "**Core Functionalities**\n"
            "• Auto-ban malicious admin activities instantly.\n"
            "• Whitelist protection for trusted users.\n"
            "• Live monitoring of admin actions.\n"
            "• Rapid threat detection & neutralization.\n\n"
            "**Configuration Panel**\n"
            "✅ Enable Protection: `antinuke enable`\n"
            "❌ Disable Protection: `antinuke disable`",
        color=0xFF0000
      )      
      embed.set_thumbnail(url=self.bot.user.display_avatar.url)
      embed.set_footer(text=f"{DEFAULT_BRANDING} — Your 24/7 Security Partner.", icon_url=self.bot.user.display_avatar.url)
      await ctx.send(embed=embed)

    elif option.lower() == 'enable':
      if is_activated:
        embed = discord.Embed(
          description=f'**Security Settings For {ctx.guild.name}**\nYour server __**already has Antinuke enabled.**__\n\nCurrent Status: ✅ Enabled\nTo Disable use `antinuke disable`',
          color=0xFF0000
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)
      else:
        
        setup_embed = discord.Embed(
          title="Antinuke Setup 😄",
          description="✅ | Initializing Quick Setup!",
          color=0xFF0000
        )
        setup_message = await ctx.send(embed=setup_embed)

        
        if not ctx.guild.me.guild_permissions.administrator:
          setup_embed.description += "\n❌ | **Ops! It seems I Don't Have Administrator Perm To enable antinuke**."
          await setup_message.edit(embed=setup_embed)
          return

        await asyncio.sleep(1)
        setup_embed.description += "\n✅ Checking bot role position for optimal configuration..."
        await setup_message.edit(embed=setup_embed)

        await asyncio.sleep(1)
        # Resolve guild branding name for the protection role
        try:
          _b = await get_branding(ctx.guild.id)
          _bname = _b.get("branding_name") or DEFAULT_BRANDING
        except Exception:
          _bname = DEFAULT_BRANDING

        setup_embed.description += f"\n✅ | Crafting and configuring the {_bname} Supreme role..."
        await setup_message.edit(embed=setup_embed)
        
        try:
          role = await ctx.guild.create_role(
            name=f"{_bname} Supreme™",
            color=0xFF0000,
            permissions=discord.Permissions(administrator=True),
            hoist=False,
            mentionable=False,
            reason="Antinuke setup Role Creation"
          )
          await ctx.guild.me.add_roles(role)
        except discord.Forbidden:
          setup_embed.description += "\n❌ | **Uh oh! I don't Have perms to enable antinuke**."
          await setup_message.edit(embed=setup_embed)
          return
        except discord.HTTPException as e:
          setup_embed.description += f"\n❌ | **Uh: HTTPException: {e}\nCheck Guild Audit Logs**."
          await setup_message.edit(embed=setup_embed)
          return

        await asyncio.sleep(1)
        setup_embed.description += f"\n✅| Ensuring precise placement of the {_bname} Supreme™ role..."
        await setup_message.edit(embed=setup_embed)
        try:
          await ctx.guild.edit_role_positions(positions={role: 1})
        except discord.Forbidden:
          setup_embed.description += "\n❌ | Ops! I don't have sufficient perms to move role."
          await setup_message.edit(embed=setup_embed)
          return
        except discord.HTTPException as e:
          setup_embed.description += f"\n❌ | Setup failed: HTTPException: {e}."
          await setup_message.edit(embed=setup_embed)
          return

        await asyncio.sleep(1)
        setup_embed.description += "\n✅ | Safeguarding your changes..."
        await setup_message.edit(embed=setup_embed)

        await asyncio.sleep(1)
        setup_embed.description += "\n✅ | Activating the Antinuke Modules for enhanced security...!!"
        await setup_message.edit(embed=setup_embed)

        await self.db.execute('INSERT OR REPLACE INTO antinuke (guild_id, status) VALUES (?, ?)', (guild_id, True))
        await self.db.commit()

        await asyncio.sleep(1)
        await setup_message.delete()

        embed = discord.Embed(
          description=f"**Security Settings For {ctx.guild.name} **\n\nTip: For optimal functionality of the AntiNuke Module, please ensure that my role has **Administration** permissions and is positioned at the **Top** of the roles list\n\n⚙️ __**Modules Enabled**__\n>>> ✅ **Anti Ban**\n✅ **Anti Kick**\n✅ **Anti Bot**\n✅ **Anti Channel Create**\n✅ **Anti Channel Delete**\n✅ **Anti Channel Update**\n✅ **Anti Everyone/Here**\n✅ **Anti Role Create**\n✅ **Anti Role Delete**\n✅ **Anti Role Update**\n✅ **Anti Member Update**\n✅ **Anti Guild Update**\n✅ **Anti Integration**\n✅ **Anti Webhook Create**\n✅ **Anti Webhook Delete**\n✅ **Anti Webhook Update**",
          color=0xFF0000
        )

        embed.add_field(name='', value=">>> ✅ **Anti Prune**\n✅ **Auto Recovery**")

        embed.set_author(name=f"{_bname} Antinuke", icon_url=self.bot.user.display_avatar.url)

        embed.set_footer(text=f"Successfully Enabled Antinuke for this server | Powered by {_bname}", icon_url=self.bot.user.display_avatar.url)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Show Punishment Type", custom_id="show_punishment"))

        await ctx.send(embed=embed, view=view)

    elif option.lower() == 'disable':
      if not is_activated:
        embed = discord.Embed(
          description=f'**Security Settings For {ctx.guild.name}**\nUhh, looks like your server hasn\'t enabled Antinuke.\n\nCurrent Status: ❌ Disabled\n\nTo Enable use `antinuke enable`',
          color=0xFF0000
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
      else:
        await self.db.execute('DELETE FROM antinuke WHERE guild_id = ?', (guild_id,))
        await self.db.commit()
        embed = discord.Embed(
          description=f'**Security Settings For {ctx.guild.name}**\nSuccessfully disabled Antinuke for this server.\n\nCurrent Status: ❌ Disabled\n\nTo Enable use `antinuke enable`',
          color=0xFF0000
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
      await ctx.send(embed=embed)
    else:
      embed = discord.Embed(
        description='Invalid option. Please use `enable` or `disable`.',
        color=0xFF0000
      )
      await ctx.send(embed=embed)


  @commands.Cog.listener()
  async def on_interaction(self, interaction: discord.Interaction):
    if interaction.data.get('custom_id') == 'show_punishment':
    
      embed = discord.Embed(
        title="Punishment Types for Changes Made by Unwhitelisted Admins/Mods",
        description=(
          "**Anti Ban:** Ban\n"
          "**Anti Kick:** Ban\n"
          "**Anti Bot:** Ban the bot Inviter\n"
          "**Anti Channel Create/Delete/Update:** Ban\n"
          "**Anti Everyone/Here:** Remove the message & 1 hour timeout\n"
          "**Anti Role Create/Delete/Update:** Ban\n"
          "**Anti Member Update:** Ban\n"
          "**Anti Guild Update:** Ban\n"
          "**Anti Integration:** Ban\n"
          "**Anti Webhook Create/Delete/Update:** Ban\n"
          "**Anti Prune:** Ban\n"
          "**Auto Recovery:** Automatically recover damaged channels, roles, and settings\n\n"
          "Note: In the case of member updates, action will be taken only if the role contains dangerous permissions such as Ban Members, Administrator, Manage Guild, Manage Channels, Manage Roles, Manage Webhooks, or Mention Everyone"
        ),
        color=0xFF0000
      )
      embed.set_footer(text="These punishment types are fixed and assigned as required to ensure guild security/protection", icon_url=self.bot.user.display_avatar.url)
      await interaction.response.send_message(embed=embed, ephemeral=True)
