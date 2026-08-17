import discord
from discord.ext import commands
from ..base import BaseCommand

class AvatarCommand(BaseCommand):
    """Avatar command to get user profile pictures"""
    
    @property
    def command_name(self) -> str:
        return "avatar"
    
    @property
    def description(self) -> str:
        return "Get the avatar of a user"

    @commands.command(name="avatar", aliases=["pfp"])
    async def avatar(self, ctx, user: discord.User = None):
        """Get the avatar of a user"""
        user = user or ctx.author
        embed = discord.Embed(title=f"{user.name}'s profile picture", color=discord.Color.blurple())
        embed.set_image(url=user.display_avatar.url)
        embed.set_footer(text=f"URL: {user.display_avatar.url}")
        await ctx.reply(embed=embed)

    @discord.app_commands.command(name="avatar", description="Get the avatar of a user")
    @discord.app_commands.describe(user="The user to get the avatar of")
    async def slash_avatar(self, interaction: discord.Interaction, user: discord.User=None):
        user = user or interaction.user
        embed = discord.Embed(title=f"Avatar of {user.name}", color=discord.Color.blurple())
        embed.set_image(url=user.display_avatar.url)
        embed.set_footer(text=f"URL: {user.display_avatar.url}")
        await interaction.response.send_message(embed=embed)

# Context menu must be defined outside the class  
@discord.app_commands.context_menu(name="Get avatar")
async def context_get_avatar(interaction: discord.Interaction, user: discord.User):
    embed = discord.Embed(title=f"Avatar of {user.name}", color=discord.Color.blurple())
    embed.set_image(url=user.display_avatar.url)
    embed.set_footer(text=f"URL: {user.display_avatar.url}")
    await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AvatarCommand(bot))
    bot.tree.add_command(context_get_avatar)
