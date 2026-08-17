import discord
from discord.ext import commands
import logging
from ..base import BaseCommand

class UnbanCommand(BaseCommand):
    """Unban command for removing bans from users"""
    
    @property
    def command_name(self) -> str:
        return "unban"
    
    @property
    def description(self) -> str:
        return "Unban a user from the server"
    
    async def do_unban(self, guild: discord.Guild, member: discord.User, reason: str = "no reason lmao"):
        try:
            await guild.unban(member, reason=reason)
            return f"✅ Unbanned {member.mention}. Reason: {reason}"
        except Exception as e:
            logging.exception("Unban failed")
            return f"❌ Error: {str(e)}"

    @commands.command(name="unban", aliases=["unbye"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User = None, *, reason="no reason lmao"):
        """
        Unban a member

        Parameters
        ----------
        user : discord.User
            The member to unban
        reason : str, optional
            The reason for the unban (optional)
        """
        if not user:
            return await ctx.reply("❌ Please provide a member to unban.")
        
        msg = await self.do_unban(ctx.guild, user, reason)
        await ctx.reply(msg)

    @discord.app_commands.command(name="unban", description="Unban a member")
    @discord.app_commands.describe(
        member="The member to unban",
        reason="The reason for the unban"
    )
    async def slash_unban(self, interaction: discord.Interaction, member: discord.User, reason: str="no reason lmao"):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ I don't have permission to unban members.", ephemeral=True)
        
        msg = await self.do_unban(interaction.guild, member, reason)
        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(UnbanCommand(bot))
