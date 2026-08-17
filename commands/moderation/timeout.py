import discord
from discord.ext import commands
from datetime import timedelta
import logging
from ..base import BaseCommand

class TimeoutCommand(BaseCommand):
    """Timeout command for moderating members"""
    
    @property
    def command_name(self) -> str:
        return "timeout"
    
    @property
    def description(self) -> str:
        return "Timeout a member for a specified duration"
    
    async def do_timeout(self, member: discord.Member, minutes: int, reason: str = "no reason lmao"):
        try:
            duration = timedelta(minutes=minutes)
            await member.timeout(duration, reason=reason)
            return f"✅ Timed out {member.mention} for {minutes} minutes. Reason: {reason}"
        except Exception as e:
            logging.exception("Timeout failed")
            return f"❌ Error: {str(e)}"

    @commands.command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member = None, minutes: int = None, *, reason="no reason lmao"):
        """
        Timeout a member

        Parameters
        ----------
        member : discord.Member
            The member to timeout
        minutes : int
            The duration of the timeout in minutes
        reason : str, optional
            The reason for the timeout
        """
        if not member:
            return await ctx.reply("❌ Please provide a member to timeout.")
        
        if member.top_role >= ctx.author.top_role:
            return await ctx.reply("❌ You cannot timeout someone with a role equal to or higher than yours.")

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.reply("❌ I can't mute this member, their role is higher than mine")
        
        if not minutes:
            return await ctx.reply("❌ Please provide a timeout duration in minutes.")
        
        if ctx.author == member:
            return await ctx.reply("❌ You can't timeout yourself.")

        msg = await self.do_timeout(member, minutes, reason)
        await ctx.reply(msg)

    @discord.app_commands.command(name="timeout", description="Timeout a member")
    @discord.app_commands.describe(
        member="The member to timeout",
        minutes="The number of minutes to timeout",
        reason="The reason for the timeout"
    )
    async def slash_timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str="no reason lmao"):
        if not interaction.user.guild_permissions.mute_members:
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot timeout someone with a role equal to or higher than yours.", ephemeral=True)
        
        if not interaction.guild.me.guild_permissions.mute_members:
            return await interaction.response.send_message("❌ I don't have permission to timeout members.", ephemeral=True)
        
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ I can't mute this member, their role is higher than mine", ephemeral=True)
        
        if interaction.user == member:
            return await interaction.response.send_message("❌ You can't timeout yourself.", ephemeral=True)
        
        msg = await self.do_timeout(member, minutes, reason)
        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(TimeoutCommand(bot))
