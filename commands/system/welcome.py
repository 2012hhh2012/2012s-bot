import asyncio
import discord
from discord.ext import commands
from ..base import BaseCommand
import random

class WelcomeChannelManagement(BaseCommand):
    """Commands to manage welcome channel"""

    def __init__(self, bot):
        super().__init__(bot)
        self.database = getattr(bot, 'database')
        self.welcome_channels_data = getattr(bot, 'welcome_channels_data', {})
        bot.welcome_channels_data = self.welcome_channels_data
        self.join_emoji = getattr(bot, 'join_emoji', ':wave:')

    @property
    def command_name(self) -> str:
        return "welcome-channel-management"

    @property
    def description(self) -> str:
        return "Commands to manage welcome channel"
    
    def get_welcome_message(self, member):
        messages_list = [
            f"Welcome to the chaos, {member.mention}! We're glad you're here",
            f"New recruit alert! Welcome to the squad, {member.mention}!",
            f"Hello and welcome, {member.mention}! Please leave your sanity at the door",
            f"Welcome to our humble abode, {member.mention}! (Don't worry, we won't bite... hard)",
            f"Yay, another victim... err, member! Welcome to the server, {member.mention}!",
            f"Welcome to the most epic server in the universe (don't @ us), {member.mention}!",
            f"We've been expecting you... Welcome to the party, {member.mention}!",
            f"New face, who dis? Welcome to the server, friend! {member.mention}",
            f"Abandon all hope, ye who enter here... Just kidding, welcome to the server! We're happy to have you, {member.mention}",
            f"Welcome to the server, {member.mention}. We hope you bring a lot of fun and chaos to the party"
        ]

        return random.choice(messages_list)

    @commands.command(name="set-welcome-channel", aliases=["swc", "set-welcome", "sw"])
    @commands.has_permissions(manage_channels=True)
    async def set_joins_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Set a channel to send welcome message to

        Parameters
        ----------
        channel : discord.TextChannel
            The channel to set as the welcome channel
        """
        doc_ref = self.database.collection("welcome channels data").document(str(ctx.guild.id))

        if channel:
            await asyncio.to_thread(doc_ref.set, {"channel id": channel.id})
            self.welcome_channels_data[str(ctx.guild.id)] = {"channel id": channel.id}
            await ctx.reply(f"Welcome channel set to {channel.mention}")
        else:
            await asyncio.to_thread(doc_ref.set, {"channel id": ctx.channel.id})
            self.welcome_channels_data[str(ctx.guild.id)] = {"channel id": ctx.channel.id}
            await ctx.reply(f"Welcome channel set to {ctx.channel.mention}")

    @commands.command(name="remove-welcome-channel", aliases=["rwc", "remove-welcome", "rw"])
    @commands.has_permissions(manage_channels=True)
    async def remove_joins_channel(self, ctx):
        """Remove the welcome channel"""
        doc_ref = self.database.collection("welcome channels data").document(str(ctx.guild.id))

        await asyncio.to_thread(doc_ref.delete)
        if str(ctx.guild.id) in self.welcome_channels_data:
            del self.welcome_channels_data[str(ctx.guild.id)]
            
        await ctx.reply("Welcome channel removed")

    @discord.app_commands.command(name="set-welcome-channel", description="Set a channel to send welcome message to")
    @discord.app_commands.describe(channel="The channel to set as the welcome channel")
    async def slash_set_joins_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        doc_ref = self.database.collection("welcome channels data").document(str(interaction.guild_id))

        if channel:
            await asyncio.to_thread(doc_ref.set, {"channel id": channel.id})
            self.welcome_channels_data[str(interaction.guild_id)] = {"channel id": channel.id}
            await interaction.response.send_message(f"Welcome channel set to {channel.mention}")
        else:
            await asyncio.to_thread(doc_ref.set, {"channel id": interaction.channel.id})
            self.welcome_channels_data[str(interaction.guild_id)] = {"channel id": interaction.channel.id}
            await interaction.response.send_message(f"Welcome channel set to {interaction.channel.mention}")

    @discord.app_commands.command(name="remove-welcome-channel", description="Remove the welcome channel")
    async def slash_remove_joins_channel(self, interaction: discord.Interaction):
        doc_ref = self.database.collection("welcome channels data").document(str(interaction.guild_id))

        await asyncio.to_thread(doc_ref.delete)
        if str(interaction.guild_id) in self.welcome_channels_data:
            del self.welcome_channels_data[str(interaction.guild_id)]
            
        await interaction.response.send_message("Welcome channel removed")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if str(member.guild.id) in self.welcome_channels_data:
            channel_id = self.welcome_channels_data[str(member.guild.id)]["channel id"]
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(f"{self.join_emoji} {self.get_welcome_message(member)}")

async def setup(bot):
    await bot.add_cog(WelcomeChannelManagement(bot))
            