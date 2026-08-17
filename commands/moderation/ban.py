import discord
from discord.ext import commands
import logging
from ..base import BaseCommand

class BanCommand(BaseCommand):
    """Ban command for permanently removing members from the server"""
    
    @property
    def command_name(self) -> str:
        return "ban"
    
    @property
    def description(self) -> str:
        return "Ban a member from the server"
    
    async def do_ban(self, member: discord.Member, reason: str = "no reason lmao"):
        try:
            await member.ban(reason=reason)
            return f"✅ Banned {member.mention}. Reason: {reason}"
        except Exception as e:
            logging.exception("Ban failed")
            return f"❌ Error: {str(e)}"

    @commands.command(name="ban", aliases=["bye"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member = None, *, reason="no reason lmao"):
        """
        Ban a member

        Parameters
        ----------
        member : discord.Member
            The member to ban
        reason : str, optional
            The reason for the ban (optional)
        """
        if not member:
            return await ctx.reply("❌ Please provide a member to ban.")
        
        if member.top_role >= ctx.author.top_role:
            return await ctx.reply("❌ You cannot ban someone with a role equal to or higher than yours.")
        
        if member.top_role >= ctx.guild.me.top_role:
            # return await ctx.reply("❌ I can't ban this member, their role is higher than mine")
            return await ctx.reply(f"Banning {member.mention}.. But it refused...")
        
        if ctx.author == member:
            return await ctx.reply("❌ You can't ban yourself.")
        
        msg = await self.do_ban(member, reason)
        await ctx.reply(msg)

    @discord.app_commands.command(name="ban", description="Ban a member")
    @discord.app_commands.describe(
        member="The member to ban",
        reason="The reason for the ban"
    )
    async def slash_ban(self, interaction: discord.Interaction, member: discord.Member, reason: str="no reason lmao"):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ You cannot ban someone with a role equal to or higher than yours.", ephemeral=True)
        
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ I can't ban this member, their role is higher than mine", ephemeral=True)
        
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ I don't have permission to ban members.", ephemeral=True)
        
        if interaction.user == member:
            return await interaction.response.send_message("❌ You can't ban yourself.", ephemeral=True)
        
        msg = await self.do_ban(member, reason)
        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(BanCommand(bot))
