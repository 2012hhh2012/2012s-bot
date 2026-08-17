import discord
from discord.ext import commands
from ..base import BaseCommand
from config import config

class ConfigInfoCommand(BaseCommand):
    """Config info command to display current bot configuration"""
    
    @property
    def command_name(self) -> str:
        return "config"
    
    @property
    def description(self) -> str:
        return "Display current bot configuration"

    @commands.command(name="config", aliases=["cfg", "settings"])
    @commands.has_permissions(administrator=True)
    async def config_info(self, ctx):
        """Display current bot configuration (Admin only)"""
        embed = discord.Embed(
            title="🔧 Bot Configuration",
            description="Current configuration settings from environment variables",
            color=discord.Color.blue()
        )
        
        # AI Models
        embed.add_field(
            name="🤖 AI Models",
            value=f"**Gemini**: {config.GEMINI_MODEL}\n"
                  f"**Groq**: {config.GROQ_MODEL}\n"
                  f"**OpenAI**: {config.OPENAI_MODEL}",
            inline=True
        )
        
        # Rate Limits
        embed.add_field(
            name="⚡ Rate Limits",
            value=f"**Gemini**: {config.GEMINI_SEMAPHORE_LIMIT} concurrent\n"
                  f"**Groq**: {config.GROQ_SEMAPHORE_LIMIT} concurrent\n"
                  f"**Global**: {config.GLOBAL_SEMAPHORE_LIMIT} concurrent",
            inline=True
        )
        
        # Cooldowns
        embed.add_field(
            name="⏱️ Cooldowns",
            value=f"**Gemini**: {config.GEMINI_COOLDOWN}s\n"
                  f"**Llama**: {config.LLAMA_COOLDOWN}s\n"
                  f"**Default**: {config.DEFAULT_COOLDOWN}s",
            inline=True
        )
        
        # File Limits
        embed.add_field(
            name="📁 File Limits",
            value=f"**Max File Size**: {config.get_file_size_mb()}MB\n"
                  f"**Max Message**: {config.MAX_MESSAGE_LENGTH} chars\n"
                  f"**Max Embed**: {config.MAX_EMBED_CHARS} chars",
            inline=True
        )
        
        # Thread Settings
        embed.add_field(
            name="🧵 Thread Settings",
            value=f"**Inactivity Limit**: {config.THREAD_INACTIVITY_LIMIT}min\n"
                  f"**Max History**: {config.MAX_THREAD_HISTORY} msgs\n"
                  f"**Cleanup Interval**: {config.CLEANUP_INTERVAL}min",
            inline=True
        )
        
        # Bot Settings
        embed.add_field(
            name="🤖 Bot Settings",
            value=f"**Prefixes**: {', '.join(config.BOT_PREFIXES)}\n"
                  f"**Status**: {config.BOT_STATUS_TYPE}\n"
                  f"**Activity**: {config.BOT_STATUS_NAME}",
            inline=True
        )
        
        # API Status
        api_status = []
        if config.GEMINI_API_KEY:
            api_status.append("✅ Gemini")
        else:
            api_status.append("❌ Gemini")
            
        if config.GROQ_API_KEY:
            api_status.append("✅ Groq")
        else:
            api_status.append("❌ Groq")
            
        if config.GENIUS_ACCESS_TOKEN:
            api_status.append("✅ Genius")
        else:
            api_status.append("❌ Genius")
        
        embed.add_field(
            name="🔑 API Keys",
            value="\n".join(api_status),
            inline=False
        )
        
        embed.set_footer(text="All settings are configurable via .env file")
        await ctx.reply(embed=embed)

    @discord.app_commands.command(name="config", description="Display current bot configuration")
    async def slash_config_info(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        
        embed = discord.Embed(
            title="🔧 Bot Configuration",
            description="Current configuration settings from environment variables",
            color=discord.Color.blue()
        )
        
        # AI Models
        embed.add_field(
            name="🤖 AI Models",
            value=f"**Gemini**: {config.GEMINI_MODEL}\n"
                  f"**Groq**: {config.GROQ_MODEL}\n"
                  f"**OpenAI**: {config.OPENAI_MODEL}",
            inline=True
        )
        
        # Rate Limits
        embed.add_field(
            name="⚡ Rate Limits",
            value=f"**Gemini**: {config.GEMINI_SEMAPHORE_LIMIT} concurrent\n"
                  f"**Groq**: {config.GROQ_SEMAPHORE_LIMIT} concurrent\n"
                  f"**Global**: {config.GLOBAL_SEMAPHORE_LIMIT} concurrent",
            inline=True
        )
        
        # Cooldowns
        embed.add_field(
            name="⏱️ Cooldowns",
            value=f"**Gemini**: {config.GEMINI_COOLDOWN}s\n"
                  f"**Llama**: {config.LLAMA_COOLDOWN}s\n"
                  f"**Default**: {config.DEFAULT_COOLDOWN}s",
            inline=True
        )
        
        # File Limits
        embed.add_field(
            name="📁 File Limits",
            value=f"**Max File Size**: {config.get_file_size_mb()}MB\n"
                  f"**Max Message**: {config.MAX_MESSAGE_LENGTH} chars\n"
                  f"**Max Embed**: {config.MAX_EMBED_CHARS} chars",
            inline=True
        )
        
        # Thread Settings
        embed.add_field(
            name="🧵 Thread Settings",
            value=f"**Inactivity Limit**: {config.THREAD_INACTIVITY_LIMIT}min\n"
                  f"**Max History**: {config.MAX_THREAD_HISTORY} msgs\n"
                  f"**Cleanup Interval**: {config.CLEANUP_INTERVAL}min",
            inline=True
        )
        
        # Bot Settings
        embed.add_field(
            name="🤖 Bot Settings",
            value=f"**Prefixes**: {', '.join(config.BOT_PREFIXES)}\n"
                  f"**Status**: {config.BOT_STATUS_TYPE}\n"
                  f"**Activity**: {config.BOT_STATUS_NAME}",
            inline=True
        )
        
        # API Status
        api_status = []
        if config.GEMINI_API_KEY:
            api_status.append("✅ Gemini")
        else:
            api_status.append("❌ Gemini")
            
        if config.GROQ_API_KEY:
            api_status.append("✅ Groq")
        else:
            api_status.append("❌ Groq")
            
        if config.GENIUS_ACCESS_TOKEN:
            api_status.append("✅ Genius")
        else:
            api_status.append("❌ Genius")
        
        embed.add_field(
            name="🔑 API Keys",
            value="\n".join(api_status),
            inline=False
        )
        
        embed.set_footer(text="All settings are configurable via .env file")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ConfigInfoCommand(bot))
