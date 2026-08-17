import discord
from discord.ext import commands
from ..base import BaseCommand

class DeleteChannelCommand(BaseCommand):
    """Delete channel command for removing channels"""
    
    @property
    def command_name(self) -> str:
        return "delete-channel"
    
    @property
    def description(self) -> str:
        return "Delete the current channel"

    @commands.command(name="delete-channel", aliases=["delete_channel"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def delete_channel(self, ctx, *, reason="no reason lmao"):
        """
        Delete a channel

        Parameters
        ----------
        reason : str, optional
            The reason for the deletion (optional)
        """
        await ctx.channel.delete(reason=reason)
        await ctx.author.send(f"✅ Channel deleted in **{ctx.guild.name}**.")

    @discord.app_commands.command(name="delete-channel", description="Delete a channel")
    @discord.app_commands.describe(reason="The reason for the deletion")
    async def slash_delete_channel(self, interaction: discord.Interaction, reason: str="no reason lmao"):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        
        if not interaction.guild.me.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ I don't have permission to delete channels.", ephemeral=True)
        
        await interaction.channel.delete(reason=reason)
        await interaction.user.send(f"✅ Channel deleted in **{interaction.guild.name}**.")

async def setup(bot):
    await bot.add_cog(DeleteChannelCommand(bot))
