import discord
from discord.ext import commands
from ..base import BaseCommand

class AskBlurpCommand(BaseCommand):
    """Command that responds with Blurp status"""

    @property
    def command_name(self) -> str:
        return "ask-blurp"

    @property
    def description(self) -> str:
        return "Ask Blurp a question"

    @commands.command(name="ask-blurp", aliases=["blurp"])
    async def ask_blurp(self, ctx: commands.Context, *, question: str):
        """Respond that Blurp is unavailable"""
        await ctx.reply("Blurp is cooked")

    @discord.app_commands.command(name="ask-blurp", description="Ask Blurp to answer your question")
    async def slash_ask_blurp(self, interaction: discord.Interaction, question: str):
        await interaction.response.send_message("Blurp is cooked")

async def setup(bot: commands.Bot):
    await bot.add_cog(AskBlurpCommand(bot))
