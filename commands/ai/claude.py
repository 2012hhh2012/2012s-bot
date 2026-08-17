import discord
from discord.ext import commands
from typing import Optional
from datetime import datetime, timezone, timedelta

from ..base import BaseCommand
from config import config


class ClaudeCommand(BaseCommand):
    """Command for interacting with the Claude service."""

    def __init__(self, bot: commands.Bot):
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        super().__init__(bot)
        self.base_url = (config.NEUVI_API_URL or "").rstrip("/")
        self.system_prompt = config.CLAUDE_SYSTEM_INSTRUCTION
        self.endpoint = f"{self.base_url}/2012/claude" if self.base_url else None
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        self.custom_token = config.NEUVI_API_TOKEN

    @property
    def command_name(self) -> str:
        return "claude"

    @property
    def description(self) -> str:
        return "Generate a response using the Claude service"

    async def _generate_response(self, message: str, user_id: str, name: str) -> Optional[str]:
        if not self.endpoint:
            raise RuntimeError("NEUVI_API_URL is not configured on the bot.")

        session = getattr(self.bot, "session", None)
        if session is None:
            raise RuntimeError("HTTP session is not available on the bot.")

        payload = {
            "name": name,
            "message": message,
            "user_id": user_id,
            "system_prompt": self.system_prompt,
            "stream": False
        }

        headers = {}
        if self.custom_token:
            headers["Authorization"] = self.custom_token

        async with self.ai_semaphore:
            async with session.post(self.endpoint, json=payload, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    raise RuntimeError(f"Claude API returned {response.status}: {text}")

                data = await response.json()
                
                # Assuming standard response format 'response' or 'content'
                content = data.get("response") or data.get("content") or data.get("message")
                
                if not content:
                     # If we can't parse it well, just return the string representation for debugging
                     # or if data is just the message
                     pass
                
                return content if content else str(data)

    @commands.command(name="claude")
    async def claude(self, ctx: commands.Context, *, prompt: str):
        """Generate a Claude response."""
        now = datetime.now(timezone.utc)
        user_id = ctx.author.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.COOLDOWN):
                return await ctx.reply(f"⏳ Please wait {config.COOLDOWN} seconds between requests.")
        self.bot.user_cooldowns[user_id] = now

        if self.ai_toggle_users.get(str(ctx.author.id)) and self.ai_toggle_users[str(ctx.author.id)]["toggle"] == False:
            return await ctx.reply("AI features are disabled for you.")
        
        if not prompt:
            return await ctx.reply("❌ Please provide a prompt for Claude.")

        try:
            async with ctx.typing():
                result = await self._generate_response(prompt, user_id=str(ctx.author.id), name=ctx.author.name)
        except Exception as exc:  # pylint: disable=broad-except
            return await ctx.reply(f"❌ Claude request failed: {exc}")

        messages = self.split_message(result)
        if not messages:
            return await ctx.reply("⚠️ Claude returned an empty response.")

        await ctx.reply(messages[0])
        for message in messages[1:]:
            await ctx.send(message)

    @discord.app_commands.command(name="claude", description="Generate a response using the Claude service")
    @discord.app_commands.describe(prompt="The prompt to send to Claude")
    async def slash_claude(self, interaction: discord.Interaction, prompt: str):
        now = datetime.now(timezone.utc)
        user_id = interaction.user.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.COOLDOWN):
                return await interaction.response.send_message(f"⏳ Please wait {config.COOLDOWN} seconds between requests.", ephemeral=True)
        self.bot.user_cooldowns[user_id] = now

        if self.ai_toggle_users.get(str(interaction.user.id)) and self.ai_toggle_users[str(interaction.user.id)]["toggle"] == False:
            return await interaction.response.send_message("AI features are disabled for you.", ephemeral=True)
        
        await interaction.response.defer(thinking=True)

        try:
            result = await self._generate_response(prompt, user_id=str(interaction.user.id), name=interaction.user.name)
        except Exception as exc:  # pylint: disable=broad-except
            return await interaction.followup.send(f"❌ Claude request failed: {exc}", ephemeral=True)

        messages = self.split_message(result)
        if not messages:
            return await interaction.followup.send("⚠️ Claude returned an empty response.")

        for message in messages:
            await interaction.followup.send(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClaudeCommand(bot))
