import discord
from discord.ext import commands
from ..base import BaseCommand

class JokeCommand(BaseCommand):
    """Joke command to fetch random jokes"""
    
    @property
    def command_name(self) -> str:
        return "joke"
    
    @property
    def description(self) -> str:
        return "Get a random joke"

    @commands.command(name="joke")
    async def joke(self, ctx):
        """Get a random joke"""
        session = getattr(self.bot, 'session', None)
        if not session:
            return await ctx.reply("❌ HTTP session not available.")
            
        async with session.get("https://official-joke-api.appspot.com/random_joke") as resp:
            if resp.status == 200:
                data = await resp.json()

                joke_type = data["type"]
                setup = data["setup"]
                punchline = data["punchline"]

                embed = discord.Embed(
                    title="🤣 Here's a random joke:",
                    description=f"- {setup}\n- **{punchline}**",
                    color=discord.Color.blurple()
                )
                embed.set_footer(text=f"Type: {joke_type}")
                await ctx.reply(embed=embed)
            else:
                await ctx.reply("😢 Couldn't fetch a joke right now...")

    @discord.app_commands.command(name="joke", description="Get a random joke")
    async def slash_joke(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        session = getattr(self.bot, 'session', None)
        if not session:
            return await interaction.followup.send("❌ HTTP session not available.")
            
        async with session.get("https://official-joke-api.appspot.com/random_joke") as resp:
            if resp.status == 200:
                data = await resp.json()

                joke_type = data["type"]
                setup = data["setup"]
                punchline = data["punchline"]

                embed = discord.Embed(
                    title="🤣 Here's a random joke:",
                    description=f"- {setup}\n- **{punchline}**",
                    color=discord.Color.blurple()
                )
                embed.set_footer(text=f"Type: {joke_type}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("😢 Couldn't fetch a joke right now...")

async def setup(bot):
    await bot.add_cog(JokeCommand(bot))
