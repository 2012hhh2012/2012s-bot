import discord
from discord.ext import commands
import aiohttp
from ..base import BaseCommand

class CatCommand(BaseCommand):
    """Cat command to fetch random cat images"""
    
    @property
    def command_name(self) -> str:
        return "cat"
    
    @property
    def description(self) -> str:
        return "Fetch a random cat image"

    @commands.command(name="cat")
    async def cat(self, ctx):
        """Fetch a random cat image"""
        session = getattr(self.bot, 'session', None)
        if not session:
            return await ctx.reply("❌ HTTP session not available.")
            
        async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
            if resp.status == 200:
                data = await resp.json()
                image_url = data[0]["url"]
                embed = discord.Embed(title="🐱 Meow! Here's a random cat:")
                embed.set_image(url=image_url)
                await ctx.reply(embed=embed)
            else:
                await ctx.reply("😿 Couldn't fetch a cat right now...")

    @discord.app_commands.command(name="cat", description="Fetch a random cat image")
    async def slash_cat(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        session = getattr(self.bot, 'session', None)
        if not session:
            return await interaction.followup.send("❌ HTTP session not available.")
            
        async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
            if resp.status == 200:
                data = await resp.json()
                image_url = data[0]["url"]
                embed = discord.Embed(title="🐱 Meow! Here's a random cat:")
                embed.set_image(url=image_url)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("😿 Couldn't fetch a cat right now...")

async def setup(bot):
    await bot.add_cog(CatCommand(bot))
