import discord
from discord.ext import commands
from ..base import BaseCommand

class HelloCommand(BaseCommand):
    """Command to say hello"""
    
    @property
    def command_name(self) -> str:
        return "greet"
    
    @property
    def description(self) -> str:
        return "Say hello to the bot"

    @commands.command(name="greet", aliases=["hello", "hi"])
    async def greet(self, ctx):
        """Greet the bot"""
        await ctx.reply(f"Hello {ctx.author.mention}! 👋")

    @discord.app_commands.command(name="greet", description="Greet the bot")
    async def slash_greet(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Hello {interaction.user.mention}! 👋")

async def setup(bot):
    await bot.add_cog(HelloCommand(bot))
