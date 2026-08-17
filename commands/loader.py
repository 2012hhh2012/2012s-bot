import os
import importlib
import logging
from pathlib import Path

class CommandLoader:
    """Utility class to dynamically load all command files"""
    
    def __init__(self, bot):
        self.bot = bot
        self.commands_dir = Path(__file__).parent
        self.loaded_commands = []
    
    async def load_all_commands(self):
        """Load all command files from all subdirectories"""
        command_groups = ['moderation', 'ai', 'fun', 'utility', 'music', 'system']
        
        for group in command_groups:
            group_path = self.commands_dir / group
            if group_path.exists() and group_path.is_dir():
                await self._load_group(group)
    
    async def _load_group(self, group_name):
        """Load all commands from a specific group"""
        group_path = self.commands_dir / group_name
        
        for file_path in group_path.glob('*.py'):
            if file_path.name.startswith('__'):
                continue
                
            command_name = file_path.stem
            module_path = f"commands.{group_name}.{command_name}"
            
            try:
                await self.bot.load_extension(module_path)
                self.loaded_commands.append(module_path)
                print(f"✅ Loaded {group_name}/{command_name}")
            except Exception as e:
                print(f"❌ Failed to load {group_name}/{command_name}: {e}")
                logging.exception(f"Failed to load command {module_path}")
    
    async def reload_all_commands(self):
        """Reload all loaded commands"""
        for module_path in self.loaded_commands:
            try:
                await self.bot.reload_extension(module_path)
                print(f"🔄 Reloaded {module_path}")
            except Exception as e:
                print(f"❌ Failed to reload {module_path}: {e}")
    
    async def unload_all_commands(self):
        """Unload all loaded commands"""
        for module_path in self.loaded_commands:
            try:
                await self.bot.unload_extension(module_path)
                print(f"🗑️ Unloaded {module_path}")
            except Exception as e:
                print(f"❌ Failed to unload {module_path}: {e}")
        
        self.loaded_commands.clear()
