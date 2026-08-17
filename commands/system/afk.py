import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from ..base import BaseCommand

class AFKCommand(BaseCommand):
    """AFK system for users to set away status"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.afk_users = getattr(bot, 'afk_users', {})
        bot.afk_users = self.afk_users
    
    @property
    def command_name(self) -> str:
        return "afk"
    
    @property
    def description(self) -> str:
        return "Set your AFK status"
    
    def format_duration(self, td: timedelta) -> str:
        """Convert timedelta to readable string"""
        total_seconds = int(td.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
            
        return " ".join(parts)

    @commands.command(name="afk")
    async def afk(self, ctx, *, reason="I'm away right now."):
        """
        Set your AFK status

        Parameters
        ----------
        reason : str, optional
            The reason for being AFK (optional)
        """
        user_id = ctx.author.id

        if user_id not in self.afk_users:
            self.afk_users[user_id] = {
                "reason": reason,
                "timestamp": datetime.now(timezone.utc),
                "pings": 0,
                "lock_message_id": ctx.message.id,
            }
            await ctx.reply(f"👋 **{ctx.author.mention}** is now AFK. Reason: **{reason}**")
        else:
            await ctx.reply(f"{ctx.author.mention}, you are already AFK! Returning..")
            afk_data = self.afk_users.pop(user_id)
            
            afk_timedelta = datetime.now(timezone.utc) - afk_data["timestamp"]
            afk_duration = self.format_duration(afk_timedelta)
                
            await ctx.reply(f"Welcome back, {ctx.author.mention}! You were AFK for **{afk_duration}**.")

    @discord.app_commands.command(name="afk", description="Set your AFK status")
    @discord.app_commands.describe(reason="The reason for being AFK")
    async def slash_afk(self, interaction: discord.Interaction, reason: str="I'm away right now."):
        user_id = interaction.user.id

        if user_id not in self.afk_users:
            self.afk_users[user_id] = {
                "reason": reason,
                "timestamp": datetime.now(timezone.utc),
                "pings": 0,
                "lock_message_id": None,
            }
            await interaction.response.send_message(f"👋 **{interaction.user.mention}** is now AFK. Reason: **{reason}**")
        else:
            await interaction.response.send_message(f"{interaction.user.mention}, you are already AFK! Type any message to return.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Ignore the command message that just set AFK
        user_entry = self.afk_users.get(message.author.id)
        if user_entry and user_entry.get("lock_message_id") == message.id:
            user_entry["lock_message_id"] = None
            return

        # Check mentions for AFK users
        for mentioned_user in message.mentions:
            if mentioned_user.id in self.afk_users and mentioned_user.id != message.author.id:
                self.afk_users[mentioned_user.id]["pings"] += 1
                afk_data = self.afk_users[mentioned_user.id]
                
                afk_timedelta = datetime.now(timezone.utc) - afk_data["timestamp"]
                afk_duration = self.format_duration(afk_timedelta)

                await message.reply(
                    f"**{mentioned_user.display_name}** is AFK: **{afk_data['reason']}** "
                    f"(Since: {afk_duration} ago)"
                )
                return

        # Check if user is returning from AFK
        user_id = message.author.id
        if user_id in self.afk_users:
            afk_data = self.afk_users.pop(user_id)
            
            afk_timedelta = datetime.now(timezone.utc) - afk_data["timestamp"]
            afk_duration = self.format_duration(afk_timedelta)

            ping_count = afk_data.get("pings", 0)
            if ping_count > 0:
                ping_message = f"and was pinged **{ping_count}** time{'s' if ping_count != 1 else ''}"
            else:
                ping_message = "and received no pings"
                
            await message.reply(f"Welcome back, {message.author.mention}! You were AFK for **{afk_duration}** {ping_message}.")

async def setup(bot):
    await bot.add_cog(AFKCommand(bot))
