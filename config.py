"""
Configuration management for the Discord bot.
This module provides easy access to environment variables with proper defaults.
"""

import os
from typing import Union

class Config:
    """Configuration class to manage all bot settings from environment variables"""
    
    # Discord Settings
    DISCORD_TOKEN = os.getenv("DISCORD9_TOKEN")
    OWNER_IDS = [int(i) for i in os.getenv("OWNER_IDS", "0").split(",")]
    TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", "0"))
    DEBUG_CHANNEL_ID = int(os.getenv("DEBUG_CHANNEL_ID", "0"))
    BOT_PREFIXES = [p.strip() for p in os.getenv("BOT_PREFIXES", "b?,b!,2012?,2012!").split(",")]
    
    # AI API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY2")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
    MESSA_AI_API_URL = os.getenv("MESSA_AI_API_URL")
    MESSA_AI_API_KEY = os.getenv("MESSA_AI_API_KEY")
    NEUVI_API_URL = os.getenv("NEUVI_API_URL")
    NEUVI_API_TOKEN = os.getenv("NEUVI_API_TOKEN")
    GPT_SYSTEM_INSTRUCTION = os.getenv("GPT_SYSTEM_INSTRUCTION", "")
    DEEPSEEK_SYSTEM_INSTRUCTION = os.getenv("DEEPSEEK_SYSTEM_INSTRUCTION", "")
    HUNYUAN_SYSTEM_INSTRUCTION = os.getenv("HUNYUAN_SYSTEM_INSTRUCTION", "")
    HUNYUAN_T1_SYSTEM_INSTRUCTION = os.getenv("HUNYUAN_T1_SYSTEM_INSTRUCTION", "")
    QWEN_SYSTEM_INSTRUCTION = os.getenv("QWEN_SYSTEM_INSTRUCTION", "")
    QWEN_OMNI_SYSTEM_INSTRUCTION = os.getenv("QWEN_OMNI_SYSTEM_INSTRUCTION", "")
    GLM_SYSTEM_INSTRUCTION = os.getenv("GLM_SYSTEM_INSTRUCTION", "")
    KIMI_SYSTEM_INSTRUCTION = os.getenv("KIMI_SYSTEM_INSTRUCTION", "You are a helpful assistant (｡♥‿♥｡)")
    CLAUDE_SYSTEM_INSTRUCTION = os.getenv("CLAUDE_SYSTEM_INSTRUCTION", "You are a helpful assistant.")
    
    # AI Model Settings
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_MAX_TOKENS = 4096
    GEMINI_TEMPERATURE = 0.7
    
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_MAX_TOKENS = 4096
    GROQ_TEMPERATURE = 0.7

    CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b")
    CEREBRAS_MAX_TOKENS = 4096
    CEREBRAS_TEMPERATURE = 0.7
    
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MAX_TOKENS = 4096
    OPENAI_TEMPERATURE = 0.7
    
    # Rate Limiting & Semaphores
    AI_SEMAPHORE_LIMIT = 30
    
    # Command Cooldown (seconds)
    COOLDOWN = 5
    GEMINI_COOLDOWN = 5
    LLAMA_COOLDOWN = 10
    
    # File & Message Limits
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    MAX_MESSAGE_LENGTH = 1990
    MAX_EMBED_CHARS = 4000
    MAX_THREAD_HISTORY = 50
    
    # Thread & Cleanup Settings
    THREAD_INACTIVITY_LIMIT = 20  # minutes
    CLEANUP_INTERVAL = 1  # minutes
    
    # External Services
    GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
    
    # Custom Emojis & UI
    LOADING_EMOJI = "<a:loading3:1426096957427814480>"
    JOIN_EMOJI = "<:join:1439639604977340517>"
    LEFT_EMOJI = "<:left:1439639654654803988>"
    BOT_STATUS_TYPE = os.getenv("BOT_STATUS_TYPE", "watching")
    BOT_STATUS_NAME = os.getenv("BOT_STATUS_NAME", "my modular code 😎")
    BOT_STATUS_STATE = os.getenv("BOT_STATUS_STATE", "Now organized with individual command files!")
    
    # Database Configuration
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
    FIREBASE_DATABASE_ID = os.getenv("FIREBASE_DATABASE_ID", "(default)")
    FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")

    
    @classmethod
    def get_file_size_mb(cls) -> int:
        """Get max file size in MB"""
        return cls.MAX_FILE_SIZE // (1024 * 1024)
    
    @classmethod
    def validate_required_keys(cls) -> list[str]:
        """Validate that all required environment variables are set"""
        missing_keys = []
        
        required_keys = [
            ("DISCORD9_TOKEN", cls.DISCORD_TOKEN),
            ("GEMINI_API_KEY", cls.GEMINI_API_KEY),
            ("GROQ_API_KEY", cls.GROQ_API_KEY),
            ("FIREBASE_PROJECT_ID", cls.FIREBASE_PROJECT_ID),
            ("FIREBASE_CREDENTIALS", cls.FIREBASE_CREDENTIALS),
        ]
        
        for key_name, key_value in required_keys:
            if not key_value:
                missing_keys.append(key_name)
        
        return missing_keys
    
    @classmethod
    def print_config_summary(cls):
        """Print a summary of current configuration"""
        print("🔧 Bot Configuration Summary:")
        print(f"   Discord Token: {'✅ Set' if cls.DISCORD_TOKEN else '❌ Missing'}")
        print(f"   Gemini API: {'✅ Set' if cls.GEMINI_API_KEY else '❌ Missing'}")
        print(f"   Groq API: {'✅ Set' if cls.GROQ_API_KEY else '❌ Missing'}")
        print(f"   Gemini Model: {cls.GEMINI_MODEL}")
        print(f"   Groq Model: {cls.GROQ_MODEL}")
        print(f"   Max File Size: {cls.get_file_size_mb()}MB")
        print(f"   Gemini Cooldown: {cls.GEMINI_COOLDOWN}s")
        print(f"   Llama Cooldown: {cls.LLAMA_COOLDOWN}s")
        print(f"   Bot Prefixes: {', '.join(cls.BOT_PREFIXES)}")
        
        missing = cls.validate_required_keys()
        if missing:
            print(f"❌ Missing required keys: {', '.join(missing)}")
        else:
            print("✅ All required configuration keys are set!")

# Create a global config instance
config = Config()

# Convenience functions for backward compatibility
def get_env_int(key: str, default: int) -> int:
    """Get environment variable as integer with default"""
    return int(os.getenv(key, str(default)))

def get_env_float(key: str, default: float) -> float:
    """Get environment variable as float with default"""
    return float(os.getenv(key, str(default)))

def get_env_bool(key: str, default: bool) -> bool:
    """Get environment variable as boolean with default"""
    return os.getenv(key, str(default)).lower() in ('true', '1', 'yes', 'on')

def get_env_list(key: str, default: str, separator: str = ",") -> list[str]:
    """Get environment variable as list with default"""
    return [item.strip() for item in os.getenv(key, default).split(separator)]
