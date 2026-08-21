import discord
from discord.ext import commands

class QR(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="qr",
        aliases=["qrcode"],
        help="Sends a QR code image.",
        with_app_command=True
    )
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def qr(self, ctx):
        embed = discord.Embed(
            title="Payment Platform",
            description="Here's you can pay UPI With Below QR",
            color=discord.Color.blurple()
        )
        embed.set_image(url="https://media.discordapp.net/attachments/1370705419659378718/1387729401122263060/GooglePay_QR.png?ex=687f5cb7&is=687e0b37&hm=01f1e74525cdb6229361dac47d49807aeb9908ac9abf6b95850be1cbe718e9f3&")
        await ctx.reply(embed=embed)

    @qr.error
    async def qr_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ You must be an **administrator** to use this command.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"⏳ You're on cooldown. Try again in `{round(error.retry_after, 1)}s`.")
        else:
            await ctx.reply(f"⚠️ An error occurred: `{str(error)}`")

# Required for bot.load_extension()
async def setup(bot):
    await bot.add_cog(QR(bot))
