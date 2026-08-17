import discord
from discord.ext import commands
from datetime import datetime, timezone
from ..base import BaseCommand

class ServerInfoCommand(BaseCommand):
    """Server info command to display server information"""
    
    @property
    def command_name(self) -> str:
        return "server_info"
    
    @property
    def description(self) -> str:
        return "Get information about the current server"

    @commands.command(name="server_info", aliases=["si"])
    async def server_info(self, ctx):
        """Get information about the server"""
        await ctx.message.add_reaction(self.loading_emoji)

        guild = ctx.guild
        
        creation_time = f"<t:{int(guild.created_at.timestamp())}:f>"
        
        total_members = guild.member_count
        online_members = len([m for m in guild.members if m.status == discord.Status.online and not m.bot])
        bots_count = len([m for m in guild.members if m.bot])
        
        features = ", ".join(guild.features).replace("_", " ").title() or "None"
        
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)

        embed = discord.Embed(
            title=f"🌐 Server Info: {guild.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Owner:", value=guild.owner.mention if guild.owner else "N/A", inline=True)
        embed.add_field(name="Server ID:", value=guild.id, inline=True)
        embed.add_field(name="Creation Date:", value=creation_time, inline=False)
        
        embed.add_field(name="Members:", value=f"👥 Total: **{total_members}**\n🟢 Online: **{online_members}**\n🤖 Bots: **{bots_count}**\n👤 Humans: **{total_members - bots_count}**", inline=True)
        
        embed.add_field(name="Channels:", value=f"💬 Text: **{text_channels}**\n🔊 Voice: **{voice_channels}**", inline=True)
        
        embed.add_field(name="Boosts:", value=f"Level **{guild.premium_tier}** ({guild.premium_subscription_count} boosts)", inline=True)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        if features != "None":
            embed.add_field(name="Server Features:", value=f"`{features}`", inline=False)
        
        await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
        await ctx.reply(embed=embed)

    @discord.app_commands.command(name="server_info", description="Get information about the server")
    async def slash_server_info(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        
        creation_time = f"<t:{int(guild.created_at.timestamp())}:f>"
        
        total_members = guild.member_count
        online_members = len([m for m in guild.members if m.status == discord.Status.online and not m.bot])
        bots_count = len([m for m in guild.members if m.bot])
        
        features = ", ".join(guild.features).replace("_", " ").title() or "None"
        
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)

        embed = discord.Embed(
            title=f"🌐 Server Info: {guild.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Owner:", value=guild.owner.mention if guild.owner else "N/A", inline=True)
        embed.add_field(name="Server ID:", value=guild.id, inline=True)
        embed.add_field(name="Creation Date:", value=creation_time, inline=False)
        
        embed.add_field(name="Members:", value=f"👥 Total: **{total_members}**\n🟢 Online: **{online_members}**\n🤖 Bots: **{bots_count}**\n👤 Humans: **{total_members - bots_count}**", inline=True)
        
        embed.add_field(name="Channels:", value=f"💬 Text: **{text_channels}**\n🔊 Voice: **{voice_channels}**", inline=True)
        
        embed.add_field(name="Boosts:", value=f"Level **{guild.premium_tier}** ({guild.premium_subscription_count} boosts)", inline=True)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        if features != "None":
            embed.add_field(name="Server Features:", value=f"`{features}`", inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ServerInfoCommand(bot))
