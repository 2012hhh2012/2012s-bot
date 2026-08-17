import asyncio
import discord
from discord.ext import commands
from google.cloud import firestore
from ..base import BaseCommand

class DoJCommand(BaseCommand):
    """Command to do j"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.database = getattr(bot, 'database')
        self.j_count = getattr(bot, 'j_count', 0)
        bot.j_count = self.j_count
    
    @property
    def command_name(self) -> str:
        return "do_j"
    
    @property
    def description(self) -> str:
        return "Do j"

    @commands.command(name="do-j", aliases=["doj", "do j", "j"])
    async def do_j(self, ctx):
        """Do j"""
        doc_ref = self.database.collection("do j").document("j count")
        await asyncio.to_thread(doc_ref.update, {"j": firestore.Increment(1)})

        self.j_count += 1
        
        await ctx.reply(f"did j {self.j_count} times")

    @discord.app_commands.command(name="do-j", description="Do j")
    async def slash_do_j(self, interaction: discord.Interaction):
        doc_ref = self.database.collection("do j").document("j count")
        await asyncio.to_thread(doc_ref.update, {"j": firestore.Increment(1)})

        self.j_count += 1
        
        await interaction.response.send_message(f"did j {self.j_count} times")

async def setup(bot):
    await bot.add_cog(DoJCommand(bot))
