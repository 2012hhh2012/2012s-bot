import discord
import random
from discord.ext import commands
from ..base import BaseCommand

class GayCommand(BaseCommand):
    """How gay are you? command with random results."""
    
    @property
    def command_name(self) -> str:
        return "gay"
    
    @property
    def description(self) -> str:
        return "Determine the gayness percentage of a user"

    def _get_embed(self, user: discord.User | discord.Member, percentage: int) -> discord.Embed:
        # Choose a rainbow-ish color or pink
        color = discord.Color.from_rgb(255, 105, 180) # Hot Pink
        if percentage > 80:
            color = discord.Color.from_rgb(255, 0, 255) # Magenta
        elif percentage < 20:
            color = discord.Color.from_rgb(255, 192, 203) # Pink
            
        embed = discord.Embed(
            title="🏳️‍🌈 Gay Rate Machine",
            description=f"{user.mention} is **{percentage}%** gay!",
            color=color
        )
        
        # Add a funny comment based on percentage
        if percentage == 0:
            comment = "Straight as an arrow. 📏"
        elif percentage < 25:
            comment = "Barely gay. 🤏"
        elif percentage < 50:
            comment = "A bit fruity. 🍎"
        elif percentage < 75:
            comment = "Quite the rainbow enjoyer. 🌈"
        elif percentage < 100:
            comment = "Extremely gay! ✨"
        else:
            comment = "100% GAY! You have achieved peak orientation. 🏳️‍🌈👑"
            
        embed.set_footer(text=comment)
        if user.display_avatar:
            embed.set_thumbnail(url=user.display_avatar.url)
            
        return embed

    @commands.command(name="gay", aliases=["gayrate", "howgay"])
    async def gay(self, ctx, target: discord.Member = None):
        """Check how gay someone is"""
        user = target or ctx.author
        percentage = random.randint(0, 100)
        embed = self._get_embed(user, percentage)
        await ctx.reply(embed=embed)

    @discord.app_commands.command(name="gay", description="Check how gay someone is")
    @discord.app_commands.describe(user="The user to check")
    async def slash_gay(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check how gay someone is"""
        target = user or interaction.user
        percentage = random.randint(0, 100)
        embed = self._get_embed(target, percentage)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(GayCommand(bot))
