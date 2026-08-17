import asyncio
import discord
from discord.ext import commands
from ..base import BaseCommand

class AIToggleCommand(BaseCommand):
    """Command to toggle AI features for users"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.database = getattr(bot, 'database')
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        bot.ai_toggle_users = self.ai_toggle_users
    
    @property
    def command_name(self) -> str:
        return "ai_toggle"
    
    @property
    def description(self) -> str:
        return "Toggle AI features on/off for yourself"

    @commands.command(name="ai-toggle", aliases=["at"])
    async def ai_toggle(self, ctx):
        """Toggle AI features on/off for yourself"""
        doc_ref = self.database.collection("ai toggle users").document(str(ctx.author.id))
        
        if self.ai_toggle_users.get(str(ctx.author.id)):
            if self.ai_toggle_users[str(ctx.author.id)]["toggle"] == True:
                await asyncio.to_thread(doc_ref.update, {"toggle": False})
                self.ai_toggle_users[str(ctx.author.id)] = {"toggle": False}
            else:
                await asyncio.to_thread(doc_ref.update, {"toggle": True})
                self.ai_toggle_users[str(ctx.author.id)] = {"toggle": True}
        else:
            await asyncio.to_thread(doc_ref.set, {"toggle": False})
            self.ai_toggle_users[str(ctx.author.id)] = {"toggle": False}

        await ctx.reply(f"AI toggled for {ctx.author.mention} to {'on' if self.ai_toggle_users[str(ctx.author.id)]['toggle'] == True else 'off'}")

    @discord.app_commands.command(name="ai-toggle", description="Toggle all AI features on/off for you")
    async def slash_ai_toggle(self, interaction: discord.Interaction):
        doc_ref = self.database.collection("ai toggle users").document(str(interaction.user.id))
        
        if self.ai_toggle_users.get(str(interaction.user.id)):
            if self.ai_toggle_users[str(interaction.user.id)]["toggle"] == True:
                await asyncio.to_thread(doc_ref.update, {"toggle": False})
                self.ai_toggle_users[str(interaction.user.id)] = {"toggle": False}
            else:
                await asyncio.to_thread(doc_ref.update, {"toggle": True})
                self.ai_toggle_users[str(interaction.user.id)] = {"toggle": True}
        else:
            await asyncio.to_thread(doc_ref.set, {"toggle": False})
            self.ai_toggle_users[str(interaction.user.id)] = {"toggle": False}
        
        await interaction.response.send_message(f"AI toggled for {interaction.user.mention} to {'on' if self.ai_toggle_users[str(interaction.user.id)]['toggle'] == True else 'off'}")

async def setup(bot):
    await bot.add_cog(AIToggleCommand(bot))
