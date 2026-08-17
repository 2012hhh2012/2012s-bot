import discord
from discord.ext import commands
from ..base import BaseCommand

class EchoCommand(BaseCommand):
    """Echo command to repeat messages"""
    
    @property
    def command_name(self) -> str:
        return "echo"
    
    @property
    def description(self) -> str:
        return "Echo a message back"

    @commands.command(name="echo", aliases=["say"])
    async def echo(self, ctx, *, msg):
        """
        Echo a message

        Parameters
        ----------
        msg : str
            The message to echo
        """
        await ctx.reply(msg)

    @discord.app_commands.command(name="echo", description="Echo a message")
    @discord.app_commands.describe(msg="The message to echo")
    async def slash_echo(self, interaction: discord.Interaction, msg: str):
        await interaction.response.send_message(msg)

    @discord.app_commands.command(name="say", description="Echo a message")
    @discord.app_commands.describe(msg="The message to echo")
    async def slash_say(self, interaction: discord.Interaction, msg: str):
        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(EchoCommand(bot))
