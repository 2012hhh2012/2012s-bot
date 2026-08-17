import discord
from discord.ext import commands
from discord import app_commands
from ..base import BaseCommand

from mcstatus import JavaServer, BedrockServer
import asyncio

class MCPingCommand(BaseCommand):
    """Get the status of a Minecraft server."""

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    @property
    def command_name(self) -> str:
        return "mc-ping"
    
    @property
    def description(self) -> str:
        return "Get the status of a Minecraft server"

    # Prefix command
    @commands.command(name="mc-ping", aliases=["mcstatus", "mcping", "mc-status"])
    async def mc_ping(self, ctx, server_type: str = None, address: str = None, port: int = None):
        """
        Get the status of a Minecraft server (Java or Bedrock).
        """
        await self._send_server_status(ctx, server_type, address, port, is_slash=False)

    # Slash command
    @app_commands.command(name="mc-ping", description="Get the status of a Minecraft server")
    @app_commands.describe(
        server_type="The server type (Java or Bedrock)",
        address="The server address (e.g., mc.hypixel.net or geo.hivebedrock.network)",
        port="The server port (Java default: 25565, Bedrock default: 19132)"
    )
    @app_commands.choices(server_type=[
        app_commands.Choice(name="Java Edition", value="java"),
        app_commands.Choice(name="Bedrock Edition", value="bedrock")
    ])
    async def mc_ping_slash(
        self, 
        interaction: discord.Interaction, 
        server_type: str, 
        address: str, 
        port: int = None
    ):
        """Slash command version of mc-ping."""
        await interaction.response.defer(thinking=True)
        await self._send_server_status(interaction, server_type, address, port, is_slash=True)

    async def _send_server_status(self, ctx_or_interaction, server_type: str, address: str, port: int = None, is_slash: bool = False):
        """Shared logic for both prefix and slash commands."""
        
        # Helper to send messages
        async def reply(content=None, embed=None, ephemeral=False):
            if is_slash:
                if content and embed:
                    await ctx_or_interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
                elif embed:
                    await ctx_or_interaction.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    await ctx_or_interaction.followup.send(content=content, ephemeral=ephemeral)
            else:
                if embed:
                    await ctx_or_interaction.reply(embed=embed, ephemeral=ephemeral)
                else:
                    await ctx_or_interaction.reply(content=content, ephemeral=ephemeral)
        
        # Validate server_type
        if not server_type or server_type.lower() not in ["java", "bedrock"]:
            embed = discord.Embed(
                title="❌ Invalid Server Type",
                description="Please specify `java` or `bedrock`.\n\n**Examples:**\n`!mc-ping java mc.hypixel.net`\n`!mc-ping bedrock geo.hivebedrock.network 19132`",
                color=discord.Color.red()
            )
            await reply(embed=embed, ephemeral=True)
            return
        
        server_type = server_type.lower()
        
        # Validate address
        if not address or address.strip() == "":
            embed = discord.Embed(
                title="❌ Missing Server Address",
                description=f"Please provide a server address.\n\n**Example:** `!mc-ping {server_type} mc.hypixel.net`",
                color=discord.Color.red()
            )
            await reply(embed=embed, ephemeral=True)
            return
        
        # Set default ports
        if port is None:
            port = 19132 if server_type == "bedrock" else 25565
        
        # Build display address
        display_address = f"{address}:{port}"
        
        # Send loading message
        if is_slash:
            await ctx_or_interaction.edit_original_response(content=f"🔄 Pinging `{display_address}` ({server_type.upper()})...")
        else:
            loading_msg = await ctx_or_interaction.reply(f"🔄 Pinging `{display_address}` ({server_type.upper()})...")
        
        try:
            if server_type == "bedrock":
                # Bedrock Edition
                server = BedrockServer(address, port)
                loop = asyncio.get_event_loop()
                status = await loop.run_in_executor(None, server.status)
                
                embed = discord.Embed(
                    title=f"🟢 **{display_address}** (Bedrock)",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                # MOTD - Bedrock has different MOTD handling
                motd = getattr(status, 'motd', 'Minecraft Bedrock Server')
                if hasattr(motd, 'to_plain'):
                    motd_text = motd.to_plain()
                elif isinstance(motd, str):
                    motd_text = motd
                else:
                    motd_text = str(motd)
                embed.description = motd_text[:200]
                
                # FIXED: Use players.online / players.max
                embed.add_field(
                    name="👥 Players",
                    value=f"**{status.players.online}** / **{status.players.max}**",
                    inline=True
                )
                embed.add_field(
                    name="📡 Ping",
                    value=f"**{int(status.latency)}ms**",
                    inline=True
                )
                
                # FIXED: Use version.name
                version_name = getattr(status.version, 'name', 'Unknown') if hasattr(status, 'version') else 'Unknown'
                embed.add_field(
                    name="⚙️ Version",
                    value=version_name[:50],
                    inline=False
                )
                
                # Bedrock-specific brand field (often shows "Bedrock" or server software)
                if hasattr(status, 'brand') and status.brand:
                    embed.add_field(name="🏷️ Brand", value=status.brand, inline=True)
                
                # Map name (if available)
                if hasattr(status, 'map') and status.map:
                    embed.add_field(name="🗺️ Map", value=status.map, inline=True)
                
                # Gamemode (if available)
                if hasattr(status, 'gamemode') and status.gamemode:
                    embed.add_field(name="🎮 Gamemode", value=status.gamemode, inline=True)
                
                embed.set_footer(text="Bedrock Edition Server")
                
            else:
                # Java Edition
                server = JavaServer(address, port)
                loop = asyncio.get_event_loop()
                status = await loop.run_in_executor(None, server.status)
                
                embed = discord.Embed(
                    title=f"🟢 **{display_address}** (Java)",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                # MOTD
                motd_lines = []
                if status.motd:
                    try:
                        motd_plain = status.motd.to_plain() if hasattr(status.motd, 'to_plain') else str(status.motd)
                        motd_lines = [line for line in motd_plain.split('\n') if line.strip()]
                    except:
                        motd_lines = []
                
                if motd_lines:
                    embed.description = motd_lines[0][:200]
                
                # Basic stats
                embed.add_field(
                    name="👥 Players",
                    value=f"**{status.players.online}** / **{status.players.max}**",
                    inline=True
                )
                embed.add_field(
                    name="📡 Ping",
                    value=f"**{int(status.latency)}ms**",
                    inline=True
                )
                embed.add_field(
                    name="⚙️ Version",
                    value=status.version.name[:50] if status.version.name else "Unknown",
                    inline=False
                )
                
                # Player list for Java
                if status.players.online > 0 and status.players.sample:
                    player_names = ", ".join([p.name for p in status.players.sample[:10]])
                    if status.players.online > 10:
                        player_names += f" and **{status.players.online - 10}** more..."
                    embed.add_field(name="🎮 Online Players", value=player_names, inline=False)
                
                # Second line of MOTD
                if len(motd_lines) > 1:
                    embed.add_field(name="📝 MOTD", value=motd_lines[1][:100], inline=False)
                
                embed.set_footer(text="Java Edition Server")
            
            # Send the result
            if is_slash:
                await ctx_or_interaction.edit_original_response(content=None, embed=embed)
            else:
                await loading_msg.edit(content=None, embed=embed)
            
        except Exception as e:
            error_msg = str(e)
            
            # Provide friendlier error messages
            if "timed out" in error_msg.lower():
                friendly_error = "Connection timed out. The server might be offline or firewall blocking the port."
            elif "refused" in error_msg.lower():
                friendly_error = "Connection refused. The server might not be running or is on a different port."
            elif "invalid" in error_msg.lower():
                friendly_error = "Invalid server address format."
            else:
                friendly_error = error_msg[:200]
            
            embed = discord.Embed(
                title=f"🔴 **{display_address}** ({server_type.upper()})",
                description=f"Server is **offline** or unreachable.\n```\n{friendly_error}\n```",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add helpful tip for Bedrock
            if server_type == "bedrock" and port == 19132:
                embed.add_field(name="💡 Tip", value="Make sure the server has **Query** enabled in its `server.properties` file. Some Bedrock servers don't respond to status pings.", inline=False)
            
            embed.set_footer(text="Check the address and port, then try again")
            
            if is_slash:
                await ctx_or_interaction.edit_original_response(content=None, embed=embed)
            else:
                await loading_msg.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(MCPingCommand(bot))