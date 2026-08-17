import discord
from discord.ext import commands
import logging
from ..base import BaseCommand

class KickCommand(BaseCommand):
    """Kick command for removing members from the server"""
    
    @property
    def command_name(self) -> str:
        return "kick"
    
    @property
    def description(self) -> str:
        return "Kick a member from the server"
    
    async def do_kick(self, member: discord.Member, reason: str = "no reason lmao"):
        try:
            await member.kick(reason=reason)
            return f"✅ Kicked {member.mention}. Reason: {reason}"
        except Exception as e:
            logging.exception("Kick failed")
            return f"❌ Error: {str(e)}"

    @commands.command(name="kick", aliases=["getout"])
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member = None, *, reason="no reason lmao"):
        """
        Kick a member

        Parameters
        ----------
        member : discord.Member
            The member to kick
        reason : str, optional
            The reason for the kick (optional)
        """
        if not member:
            return await ctx.reply("❌ Please provide a member to kick.")
        
        if member.top_role >= ctx.author.top_role:
            return await ctx.reply("❌ You cannot kick someone with a role equal to or higher than yours.")

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.reply("❌ I can't kick this member, their role is higher than mine")
        
        if ctx.author == member:
            return await ctx.reply("❌ You can't kick yourself.")
        
        msg = await self.do_kick(member, reason)
        await ctx.reply(msg)

    @discord.app_commands.command(name="kick", description="Kick a member")
    @discord.app_commands.describe(
        member="The member to kick",
        reason="The reason for the kick"
    )
    async def slash_kick(self, interaction: discord.Interaction, member: discord.Member, reason: str="no reason lmao"):
        if not interaction.user.guild_permissions.kick_members:
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            
        
        if not interaction.guild.me.guild_permissions.kick_members:
            return await interaction.response.send_message("❌ I don't have permission to kick members.", ephemeral=True)

        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot kick someone with a role equal to or higher than yours.", ephemeral=True)
        
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ I can't kick this member, their role is higher than mine", ephemeral=True)
        
        if interaction.user == member:
            return await interaction.response.send_message("❌ You can't kick yourself.", ephemeral=True)
        
        msg = await self.do_kick(member, reason)
        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(KickCommand(bot))
