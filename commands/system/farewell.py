import discord
import asyncio
from discord.ext import commands
from ..base import BaseCommand
import random

class FarewellChannelManagement(BaseCommand):
    """Commands to manage farewell channel"""
    def __init__(self, bot):
        super().__init__(bot)
        self.database = getattr(bot, 'database')
        self.farewell_channels_data = getattr(bot, 'farewell_channels_data', {})
        bot.farewell_channels_data = self.farewell_channels_data
        self.left_emoji = getattr(bot, 'left_emoji', ':wave:')

    @property
    def command_name(self) -> str:
        return "farewell-channel-management"

    @property
    def description(self) -> str:
        return "Commands to manage farewell channel"
    
    def get_farewell_message(self, member):
        messages_list = [
            f"Aww, you're leaving us {member.mention}? Okay, but don't forget us when you're famous",
            f"It was nice having you around, {member.mention}! Come back soon, please?",
            f"You'll be deeply missed... but not as much as your memes {member.mention}!",
            f"Later, friend, {member.mention}! May the internet be ever in your favor",
            f"Don't let the door hit you on the way out... just kidding, we'll miss you {member.mention}!",
            f"Peace out, {member.mention}! May your next server be less chaotic than ours",
            f"Sad to see you go, {member.mention}! Take care",
            f"Bye for now, {member.mention}! Stay awesome",
            f"See you later, {member.mention}! We'll miss you",
            f"Goodbye, {member.mention}! We'll miss you",
            f"You were an amazing part of our community... we'll miss your presence {member.mention}!"
        ]

        return random.choice(messages_list)
    
    @commands.command(name="set-farewell-channel", aliases=["sfc", "set-farewell", "sf"])
    @commands.has_permissions(manage_channels=True)
    async def set_farewell_channel(self, ctx, channel: discord.TextChannel = None):
        """
        Set a channel to send farewell message to

        Parameters
        ----------
        channel : discord.TextChannel
            The channel to set as the farewell channel
        """
        doc_ref = self.database.collection("farewell channels data").document(str(ctx.guild.id))

        if channel:
            await asyncio.to_thread(doc_ref.set, {"channel id": channel.id})
            self.farewell_channels_data[str(ctx.guild.id)] = {"channel id": channel.id}
            await ctx.reply(f"Farewell channel set to {channel.mention}")
        else:
            await asyncio.to_thread(doc_ref.set, {"channel id": ctx.channel.id})
            self.farewell_channels_data[str(ctx.guild.id)] = {"channel id": ctx.channel.id}
            await ctx.reply(f"Farewell channel set to {ctx.channel.mention}")

    @commands.command(name="remove-farewell-channel", aliases=["rfc", "remove-farewell", "rf"])
    @commands.has_permissions(manage_channels=True)
    async def remove_farewell_channel(self, ctx):
        """Remove the farewell channel"""
        doc_ref = self.database.collection("farewell channels data").document(str(ctx.guild.id))

        await asyncio.to_thread(doc_ref.delete)
        if str(ctx.guild.id) in self.farewell_channels_data:
            del self.farewell_channels_data[str(ctx.guild.id)]
            
        await ctx.reply("Farewell channel removed")

    @discord.app_commands.command(name="set-farewell-channel", description="Set a channel to send farewell message to")
    @discord.app_commands.describe(channel="The channel to set as the farewell channel")
    async def slash_set_farewell_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        doc_ref = self.database.collection("farewell channels data").document(str(interaction.guild.id))

        if channel:
            await asyncio.to_thread(doc_ref.set, {"channel id": channel.id})
            self.farewell_channels_data[str(interaction.guild.id)] = {"channel id": channel.id}
            await interaction.response.send_message(f"Farewell channel set to {channel.mention}")
        else:
            await asyncio.to_thread(doc_ref.set, {"channel id": interaction.channel.id})
            self.farewell_channels_data[str(interaction.guild.id)] = {"channel id": interaction.channel.id}
            await interaction.response.send_message(f"Farewell channel set to {interaction.channel.mention}")

    @discord.app_commands.command(name="remove-farewell-channel", description="Remove the farewell channel")
    async def slash_remove_farewell_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        doc_ref = self.database.collection("farewell channels data").document(str(interaction.guild.id))

        await asyncio.to_thread(doc_ref.delete)
        if str(interaction.guild.id) in self.farewell_channels_data:
            del self.farewell_channels_data[str(interaction.guild.id)]
            
        await interaction.response.send_message("Farewell channel removed")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if str(member.guild.id) in self.farewell_channels_data:
            channel_id = self.farewell_channels_data[str(member.guild.id)]["channel id"]
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(f"{self.left_emoji} {self.get_farewell_message(member)}")
            
async def setup(bot):
    await bot.add_cog(FarewellChannelManagement(bot))