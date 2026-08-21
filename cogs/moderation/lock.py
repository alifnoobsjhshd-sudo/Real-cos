import discord
from utils.emojis import e as _e
from discord.ext import commands

class Lock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.red()

    @commands.hybrid_command(
        name="lock",
        description="Locks a channel to prevent sending messages.",
        aliases=["lockchannel"]
    )
    # Using manage_channels is more appropriate for locking/unlocking
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock_command(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Locks the specified channel or the current one if none is provided."""
        
        # If no channel is specified, use the current channel
        channel = channel or ctx.channel
        
        # Check if the channel is already locked
        if not channel.permissions_for(ctx.guild.default_role).send_messages:
            embed = discord.Embed(
                description=f"**Channel: {channel.mention}\n{_e('ztick')} Status: Already Locked**",
                color=0xFF0000
            )
            #embed.set_author(name=f"{c", icon_url="")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
            return

        # Lock the channel — deny sending, reactions, and thread creation so
        # members also can't react or start threads in announcement-style channels.
        await channel.set_permissions(
            ctx.guild.default_role,
            send_messages=False,
            add_reactions=False,
            create_public_threads=False,
            create_private_threads=False,
        )

        # Create the confirmation embed
        embed = discord.Embed(
            title=f"{_e('lock')} Lockdown",
            description=f"{_e('ztick')} | Successfully Locked {channel.mention}",
            color=0xFF0000
        )
        #embed.set_author(name=f"Successfully Locked {channel.name}", icon_url="")
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        #embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        # Send the final message
        await ctx.send(embed=embed)

# Standard setup function to load the cog
async def setup(bot):
    await bot.add_cog(Lock(bot))
