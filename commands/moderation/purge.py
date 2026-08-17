import discord
from discord.ext import commands
from ..base import BaseCommand

class PurgeCommand(BaseCommand):
    """Purge command for deleting multiple messages"""
    
    @property
    def command_name(self) -> str:
        return "purge"
    
    @property
    def description(self) -> str:
        return "Delete multiple messages at once"

    @commands.command(name="purge", aliases=["clear","delete"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """
        Purge messages
        
        Parameters
        ----------
        amount : int
            The amount of messages to purge
        """
        await ctx.message.add_reaction(self.loading_emoji)
        deleted = await ctx.channel.purge(limit=amount + 1)
        if len(deleted) - 1 == 0:
            await ctx.send("❌ No messages deleted.", delete_after=2)
        else:
            await ctx.send(f"✅ Purged {len(deleted)-1} messages.", delete_after=2)

    @discord.app_commands.command(name="purge", description="Purge messages")
    @discord.app_commands.describe(amount="The amount of messages to purge")
    async def slash_purge(self, interaction: discord.Interaction, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        
        if not interaction.guild.me.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ I don't have permission to delete messages.", ephemeral=True)
        
        await interaction.response.defer(thinking=True)
        deleted = await interaction.channel.purge(limit=amount + 1)
        if len(deleted) - 1 == 0:
            await interaction.response.send_message("❌ No messages deleted.", delete_after=2)
        else:
            await interaction.channel.send(f"✅ Purged {len(deleted)-1} messages.", delete_after=2)

async def setup(bot):
    await bot.add_cog(PurgeCommand(bot))
