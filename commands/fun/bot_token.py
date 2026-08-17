import discord
from discord.ext import commands
import secrets
from ..base import BaseCommand

class BotTokenCommand(BaseCommand):
    """Command to generate fake bot tokens"""
    
    @property
    def command_name(self) -> str:
        return "bot_token"
    
    @property
    def description(self) -> str:
        return "Generate a random fake bot token"

    async def generate_token(self):
        """Generate a fake Discord bot token"""
        # define a custom alphabet for base64 URL-safe encoding
        # it includes A-Z, a-z, 0-9, and the characters "-" and "_"
        
        # 1: fake bot id
        # the actual length of this segment varies based on the id length, but ~24 is a good look
        
        # 1. generate fake id Section (e.g., 24 random URL-safe characters)
        id_part_length = 24
        id_part = secrets.token_urlsafe(id_part_length)
        
        # 2. generate fake timestamp section (e.g., 6 random URL-safe characters)
        timestamp_part_length = 6
        timestamp_part = secrets.token_urlsafe(timestamp_part_length)
        
        # 3. generate fake HMAC signature (e.g., 27 random URL-safe characters)
        # this is the longest part and contains the most entropy
        signature_part_length = 27
        signature_part = secrets.token_urlsafe(signature_part_length)
        
        # assemble the final token string with dots
        fake_token = f"{id_part}.{timestamp_part}.{signature_part}"
        
        # standard length is typically around 59 characters. We can optionally adjust 
        # the lengths above to hit a target (e.g., 20.6.27 = 53 + 2 dots = 55)
        
        return fake_token

    @commands.command(name="bot-token", aliases=["token", "bot_token"])
    async def fake_bot_token(self, ctx):
        """Generate a fake bot token"""
        embed = discord.Embed(
            title="Here's your bot token:",
            description=await self.generate_token(),
            color=discord.Color.blurple()
        )
        await ctx.reply(embed=embed)

    @discord.app_commands.command(name="bot-token", description="Generate a random bot token")
    async def slash_fake_bot_token(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Here's your bot token:",
            description=await self.generate_token(),
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(BotTokenCommand(bot))
