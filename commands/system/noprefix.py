import discord
import asyncio
from discord.ext import commands
from ..base import BaseCommand

class NoPrefixCommand(BaseCommand):
    """Command to manage no-prefix users"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.database = getattr(bot, 'database')
        # Always use bot's no_prefix_users dictionary directly
        if not hasattr(bot, 'no_prefix_users'):
            bot.no_prefix_users = {}
    
    @property
    def no_prefix_users(self):
        """Get the bot's no_prefix_users dictionary"""
        return self.bot.no_prefix_users
    
    @property
    def command_name(self) -> str:
        return "noprefix"
    
    @property
    def description(self) -> str:
        return "Manage no-prefix users"
    
    async def _update_database(self, user_id, action):
        """Update the database with the new no-prefix user list"""
        try:
            doc_ref = self.database.collection("bot_settings").document("no_prefix_users")
            await asyncio.to_thread(doc_ref.set, {"users": self.no_prefix_users})
        except Exception as e:
            print(f"Error updating no-prefix database: {e}")
    
    @commands.command(name="noprefix", aliases=["nopf"])
    async def noprefix(self, ctx):
        """Toggle no-prefix"""
        if not self.database:
            await ctx.reply("❌ Database not available")
            return
            
        user_id = str(ctx.author.id)
        
        # Check if user is already in the list
        if user_id in self.no_prefix_users:
            # Remove user (second time)
            del self.no_prefix_users[user_id]
            await self._update_database(user_id, "remove")
            await ctx.reply(f"✅ Removed <@{user_id}> from no-prefix list")
        else:
            # Add user (first time)
            self.no_prefix_users[user_id] = True
            await self._update_database(user_id, "add")
            await ctx.reply(f"✅ Added <@{user_id}> to no-prefix list")
    
    @discord.app_commands.command(name="noprefix", description="Toggle no-prefix mode")
    async def slash_noprefix(self, interaction: discord.Interaction):
        """Toggle no-prefix"""
        if not self.database:
            await interaction.response.send_message("❌ Database not available", ephemeral=True)
            return
        
        user_id = str(interaction.user.id)
        
        # Check if user is already in the list
        if user_id in self.no_prefix_users:
            # Remove user (second time)
            del self.no_prefix_users[user_id]
            await self._update_database(user_id, "remove")
            await interaction.response.send_message(f"✅ Removed {interaction.user.mention} from no-prefix list")
        else:
            # Add user (first time)
            self.no_prefix_users[user_id] = True
            await self._update_database(user_id, "add")
            await interaction.response.send_message(f"✅ Added {interaction.user.mention} to no-prefix list")

async def setup(bot):
    await bot.add_cog(NoPrefixCommand(bot))
