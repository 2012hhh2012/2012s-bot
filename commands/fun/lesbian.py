import discord
import random
from discord.ext import commands
from ..base import BaseCommand

class LesbianCommand(BaseCommand):
    """How lesbian are you? command with random results."""
    
    @property
    def command_name(self) -> str:
        return "lesbian"
    
    @property
    def description(self) -> str:
        return "Determine the lesbianness percentage of a user"

    def _get_embed(self, user: discord.User | discord.Member, percentage: int) -> discord.Embed:
        # Lesbian flag colors (Orange to Pink)
        color = discord.Color.from_rgb(214, 41, 0) # Dark Orange
        if percentage > 80:
            color = discord.Color.from_rgb(163, 2, 98) # Dark Pink
        elif percentage > 60:
            color = discord.Color.from_rgb(213, 45, 126) # Medium Pink
        elif percentage > 40:
            color = discord.Color.from_rgb(255, 255, 255) # White
        elif percentage > 20:
            color = discord.Color.from_rgb(255, 154, 88) # Light Orange
            
        embed = discord.Embed(
            title="👩‍❤️‍👩 Lesbian Rate Machine",
            description=f"{user.mention} is **{percentage}%** lesbian!",
            color=color
        )
        
        # Add a funny comment based on percentage
        if percentage == 0:
            comment = "0%? No flannel for you. 🚫"
        elif percentage < 25:
            comment = "A tiny bit of girl in red is playing. 🎶"
        elif percentage < 50:
            comment = "Maybe just one U-Haul? 🚚"
        elif percentage < 75:
            comment = "Definitely likes iced coffee and cottagecore. ☕🌿"
        elif percentage < 100:
            comment = "Total lesbian vibes! ✨"
        else:
            comment = "100% LESBIAN! You have reached maximum Sapphic power. 👩‍❤️‍💋‍👩👑"
            
        embed.set_footer(text=comment)
        if user.display_avatar:
            embed.set_thumbnail(url=user.display_avatar.url)
            
        return embed

    @commands.command(name="lesbian", aliases=["lesrate", "howlesbian"])
    async def lesbian(self, ctx, target: discord.Member = None):
        """Check how lesbian someone is"""
        user = target or ctx.author
        percentage = random.randint(0, 100)
        embed = self._get_embed(user, percentage)
        await ctx.reply(embed=embed)

    @discord.app_commands.command(name="lesbian", description="Check how lesbian someone is")
    @discord.app_commands.describe(user="The user to check")
    async def slash_lesbian(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check how lesbian someone is"""
        target = user or interaction.user
        percentage = random.randint(0, 100)
        embed = self._get_embed(target, percentage)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(LesbianCommand(bot))
