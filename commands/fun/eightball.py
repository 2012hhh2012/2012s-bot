import discord
import random
from discord.ext import commands
from ..base import BaseCommand

class EightBallCommand(BaseCommand):
    """Magic 8-Ball command to answer your questions"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.responses = [
            # Positive
            "It is certain.",
            "It is decidedly so.",
            "Without a doubt.",
            "Yes definitely.",
            "You may rely on it.",
            "As I see it, yes.",
            "Most likely.",
            "Outlook good.",
            "Yes.",
            "Signs point to yes.",
            # Neutral
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
            # Negative
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful."
        ]

    @property
    def command_name(self) -> str:
        return "8ball"
    
    @property
    def description(self) -> str:
        return "Ask the Magic 8-Ball a question"

    def _get_embed(self, question: str, user: discord.User | discord.Member) -> discord.Embed:
        answer = random.choice(self.responses)
        
        # Determine color based on answer type
        if answer in self.responses[:10]: # Positive
            color = discord.Color.green()
        elif answer in self.responses[10:15]: # Neutral
            color = discord.Color.gold()
        else: # Negative
            color = discord.Color.red()

        embed = discord.Embed(
            title="🎱 Magic 8-Ball",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Question:", value=question, inline=False)
        embed.add_field(name="Answer:", value=f"**{answer}**", inline=False)
        embed.set_footer(text=f"Asked by {user.display_name}", icon_url=user.display_avatar.url)
        return embed

    @commands.command(name="8ball", aliases=["eightball", "8b"])
    async def eightball(self, ctx, *, question: str):
        """Ask the Magic 8-Ball a question"""
        embed = self._get_embed(question, ctx.author)
        await ctx.reply(embed=embed)

    @discord.app_commands.command(name="8ball", description="Ask the Magic 8-Ball a question")
    @discord.app_commands.describe(question="The question to ask the Magic 8-Ball")
    async def slash_8ball(self, interaction: discord.Interaction, question: str):
        """Ask the Magic 8-Ball a question"""
        embed = self._get_embed(question, interaction.user)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(EightBallCommand(bot))
