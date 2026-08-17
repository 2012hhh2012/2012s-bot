import discord
from discord.ext import commands
from ..base import BaseCommand

class DogCommand(BaseCommand):
    """Dog command to fetch random dog images"""
    
    @property
    def command_name(self) -> str:
        return "dog"
    
    @property
    def description(self) -> str:
        return "Fetch a random dog image"

    @commands.command(name="dog")
    async def dog(self, ctx):
        """Fetch a random dog image"""
        session = getattr(self.bot, 'session', None)
        if not session:
            return await ctx.reply("❌ HTTP session not available.")
            
        async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
            if resp.status == 200:
                data = await resp.json()
                image_url = data["message"]
                embed = discord.Embed(title="🐶 Woof! Here's a random dog:")
                embed.set_image(url=image_url)
                await ctx.reply(embed=embed)
            else:
                await ctx.reply("😢 Couldn't fetch a dog right now...")

    @discord.app_commands.command(name="dog", description="Fetch a random dog image")
    async def slash_dog(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        session = getattr(self.bot, 'session', None)
        if not session:
            return await interaction.followup.send("❌ HTTP session not available.")
            
        async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
            if resp.status == 200:
                data = await resp.json()
                image_url = data["message"]
                embed = discord.Embed(title="🐶 Woof! Here's a random dog:")
                embed.set_image(url=image_url)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("😢 Couldn't fetch a dog right now...")

async def setup(bot):
    await bot.add_cog(DogCommand(bot))
