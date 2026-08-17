import discord
from discord.ext import commands
import logging
from ..base import BaseCommand

class UntimeoutCommand(BaseCommand):
    """Untimeout command for removing timeouts from members"""
    
    @property
    def command_name(self) -> str:
        return "untimeout"
    
    @property
    def description(self) -> str:
        return "Remove timeout from a member"
    
    async def do_untimeout(self, member: discord.Member, reason: str = "no reason lmao"):
        try:
            await member.timeout(None, reason=reason)
            return f"✅ Untimed out {member.mention}. Reason: {reason}"
        except Exception as e:
            logging.exception("Untimeout failed")
            return f"❌ Error: {str(e)}"

    @commands.command(name="untimeout")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member = None, *, reason="no reason lmao"):
        """
        Untimeout a member

        Parameters
        ----------
        member : discord.Member
            The member to untimeout
        reason : str, optional
            The reason for the untimeout (optional)
        """
        if not member:
            return await ctx.reply("❌ Please provide a member to untimeout.")
        
        msg = await self.do_untimeout(member, reason)
        await ctx.reply(msg)

    @discord.app_commands.command(name="untimeout", description="Untimeout a member")
    @discord.app_commands.describe(
        member="The member to untimeout",
        reason="The reason for the untimeout"
    )
    async def slash_untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str="no reason lmao"):
        if not interaction.user.guild_permissions.mute_members:
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            
        if not interaction.guild.me.guild_permissions.mute_members:
            return await interaction.response.send_message("❌ I don't have permission to untimeout members.", ephemeral=True)
         
        msg = await self.do_untimeout(member, reason)
        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(UntimeoutCommand(bot))
