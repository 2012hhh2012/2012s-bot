import discord
from discord.ext import commands
from typing import Optional
from datetime import datetime, timezone, timedelta

from ..base import BaseCommand
from config import config


class QwenCommand(BaseCommand):
    """Command for interacting with the custom Qwen service."""

    def __init__(self, bot: commands.Bot):
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        super().__init__(bot)
        self.base_url = (config.NEUVI_API_URL or "").rstrip("/")
        self.system_prompt = config.QWEN_SYSTEM_INSTRUCTION
        self.endpoint = f"{self.base_url}/2012/qwen" if self.base_url else None
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        self.custom_token = config.NEUVI_API_TOKEN

    @property
    def command_name(self) -> str:
        return "qwen"

    @property
    def description(self) -> str:
        return "Generate a response using the custom Qwen service"

    async def _generate_response(self, message: str, user_id: str, name: str) -> Optional[str]:
        if not self.endpoint:
            raise RuntimeError("NEUVI_API_URL is not configured on the bot.")

        session = getattr(self.bot, "session", None)
        if session is None:
            raise RuntimeError("HTTP session is not available on the bot.")

        payload = {
            "message": message,
            "user_id": user_id,
            "system_prompt": self.system_prompt,
            "name": name
        }

        headers = {}
        if self.custom_token:
            headers["Authorization"] = f"Bearer {self.custom_token}"

        async with self.ai_semaphore:
            async with session.post(self.endpoint, json=payload, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    raise RuntimeError(f"Qwen API returned {response.status}: {text}")

                data = await response.json()
                content = data.get("response")
                if not content:
                    raise RuntimeError("Qwen API response did not include a 'response' field.")
                return content

    @commands.command(name="qwen")
    async def qwen(self, ctx: commands.Context, *, prompt: str):
        """Generate a stateless Qwen response."""
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
            return await ctx.reply("❌ Please provide a prompt for Qwen.")

        try:
            async with ctx.typing():
                result = await self._generate_response(prompt, user_id=str(ctx.author.id), name=ctx.author.name)
        except Exception as exc:  # pylint: disable=broad-except
            return await ctx.reply(f"❌ Qwen request failed: {exc}")

        messages = self.split_message(result)
        if not messages:
            return await ctx.reply("⚠️ Qwen returned an empty response.")

        await ctx.reply(messages[0])
        for message in messages[1:]:
            await ctx.send(message)

    @discord.app_commands.command(name="qwen", description="Generate a response using the custom Qwen service")
    @discord.app_commands.describe(prompt="The prompt to send to Qwen")
    async def slash_qwen(self, interaction: discord.Interaction, prompt: str):
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
            return await interaction.followup.send(f"❌ Qwen request failed: {exc}", ephemeral=True)

        messages = self.split_message(result)
        if not messages:
            return await interaction.followup.send("⚠️ Qwen returned an empty response.")

        for message in messages:
            await interaction.followup.send(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(QwenCommand(bot))
