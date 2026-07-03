import discord
from discord.ext import commands

# --- AUTHORIZED STAFF IDs ---
# In the list below, add the Discord User IDs of the staff members
# you want to grant permission to use this command.
# Example: authorized_staff_ids = [123456789012345678, 987654321098765432]

authorized_staff_ids = [
    1263404140965396555, # Add the first staff member's ID here
    870179991462236170, # Add the second staff member's ID here
    # You can add as many staff IDs as you need
]

class StaffDMCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dmstaff")
    async def dm_staff(self, ctx, member: discord.Member, *, message: str):
        """Allows authorized staff to DM a user through the bot."""

        # Step 1: Check if the command author is an authorized staff member
        if ctx.author.id not in authorized_staff_ids:
            await ctx.reply("❌ You do not have permission to use this command.")
            return

        # Step 2: Create an embed to send to the target user
        try:
            embed = discord.Embed(
                title="📢 A Message from the Staff Team",
                description=message,
                color=0xFF0000 # Color changed to red as requested
            )
            # This footer mentions the name of the staff member who sent the DM
            embed.set_footer(text=f"This message was sent by {ctx.author.name}.")

            await member.send(embed=embed)
            
            # Step 3: Send a confirmation message back to the staff member
            await ctx.reply(f"✅ Your message has been successfully sent to **{member.name}**.")

        except discord.Forbidden:
            # This error occurs if the user has DMs disabled or has blocked the bot
            await ctx.reply(f"❌ Could not send the message. **{member.name}** may have their DMs disabled.")
        except Exception as e:
            # Handle any other potential errors
            await ctx.reply(f"🤔 Something went wrong. Error: {e}")
            print(f"Error in dmstaff command: {e}")


# This setup function is required to load the cog into your main bot file
async def setup(bot):
    await bot.add_cog(StaffDMCog(bot))
