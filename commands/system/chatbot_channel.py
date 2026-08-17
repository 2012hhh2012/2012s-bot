import asyncio
import discord
from discord.ext import commands
from ..base import BaseCommand

class ChatbotChannelManagementCommand(BaseCommand):
    """Commands to manage chatbot thingy channels"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.database = getattr(bot, 'database')
        self.chatbot_thingy_data = getattr(bot, 'chatbot_thingy_data', {})
        bot.chatbot_thingy_data = self.chatbot_thingy_data
    
    @property
    def command_name(self) -> str:
        return "chatbot-channel-management"
    
    @property
    def description(self) -> str:
        return "Manage chatbot thingy channels"

    @commands.command(name="set-chatbot-thingy-channel", aliases=["sctc"])
    @commands.has_permissions(manage_channels=True)
    async def set_chatbot_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Set a channel to chat with chatbot thingy (will also delete the histories)

        Parameters
        ----------
        channel : discord.TextChannel
            The channel to set as the chatbot thingy channel
        """
        doc_ref = self.database.collection("chatbot thingy data").document(str(ctx.guild.id))

        if channel:
            await asyncio.to_thread(doc_ref.set, {"channel id": channel.id, "histories": []})
            self.chatbot_thingy_data[str(ctx.guild.id)] = {"channel id": channel.id, "histories": []}
            await ctx.reply(f"Chatbot thingy channel set to {channel.mention}")
        else:
            await asyncio.to_thread(doc_ref.set, {"channel id": ctx.channel.id, "histories": []})
            self.chatbot_thingy_data[str(ctx.guild.id)] = {"channel id": ctx.channel.id, "histories": []}
            await ctx.reply(f"Chatbot thingy channel set to {ctx.channel.mention}")

    @commands.command(name="remove-chatbot-thingy-channel", aliases=["rctc"])
    @commands.has_permissions(manage_channels=True)
    async def remove_chatbot_channel(self, ctx):
        """Remove the chatbot thingy channel (will also delete the histories)"""
        doc_ref = self.database.collection("chatbot thingy data").document(str(ctx.guild.id))

        await asyncio.to_thread(doc_ref.delete)
        if str(ctx.guild.id) in self.chatbot_thingy_data:
            del self.chatbot_thingy_data[str(ctx.guild.id)]
            
        await ctx.reply("Chatbot thingy channel removed")

    @discord.app_commands.command(name="set-chatbot-thingy-channel", description="Set a channel to chat with chatbot thingy")
    @discord.app_commands.describe(channel="The channel to set as the chatbot thingy channel")
    async def slash_set_chatbot_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        doc_ref = self.database.collection("chatbot thingy data").document(str(interaction.guild_id))

        if channel:
            await asyncio.to_thread(doc_ref.set, {"channel id": channel.id, "histories": []})
            self.chatbot_thingy_data[str(interaction.guild_id)] = {"channel id": channel.id, "histories": []}
            await interaction.response.send_message(f"Chatbot thingy channel set to {channel.mention}")
        else:
            await asyncio.to_thread(doc_ref.set, {"channel id": interaction.channel.id, "histories": []})
            self.chatbot_thingy_data[str(interaction.guild_id)] = {"channel id": interaction.channel.id, "histories": []}
            await interaction.response.send_message(f"Chatbot thingy channel set to {interaction.channel.mention}")

    @discord.app_commands.command(name="remove-chatbot-thingy-channel", description="Remove the chatbot thingy channel")
    async def slash_remove_chatbot_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        doc_ref = self.database.collection("chatbot thingy data").document(str(interaction.guild_id))

        await asyncio.to_thread(doc_ref.delete)
        if str(interaction.guild_id) in self.chatbot_thingy_data:
            del self.chatbot_thingy_data[str(interaction.guild_id)]

        await interaction.response.send_message("Chatbot thingy channel removed")

async def setup(bot):
    await bot.add_cog(ChatbotChannelManagementCommand(bot))
