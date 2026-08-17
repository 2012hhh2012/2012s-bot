import discord
from discord.ext import commands
from ..base import BaseCommand

class PingCommand(BaseCommand):
    """Ping command to check bot latency"""
    
    @property
    def command_name(self) -> str:
        return "ping"
    
    @property
    def description(self) -> str:
        return "Check the bot's latency"

    @commands.command(name="ping", aliases=["pong", "latency"])
    async def ping(self, ctx):
        """Ping the bot"""
        await ctx.reply(f"pong! {round(self.bot.latency * 1000)}ms")

    @discord.app_commands.command(name="ping", description="Ping the bot")
    async def slash_ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"pong! {round(self.bot.latency * 1000)}ms")

async def setup(bot):
    await bot.add_cog(PingCommand(bot))
