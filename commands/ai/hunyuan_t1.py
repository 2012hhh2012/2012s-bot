import discord
from discord.ext import commands
from typing import Optional
from datetime import datetime, timezone, timedelta

from ..base import BaseCommand
from config import config


class HunyuanT1Command(BaseCommand):
    """Command for interacting with the custom Hunyuan T1 service."""

    def __init__(self, bot: commands.Bot):
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        super().__init__(bot)
        self.base_url = (config.NEUVI_API_URL or "").rstrip("/")
        # Using GPT system instruction as per hunyuan command
        self.system_prompt = config.HUNYUAN_T1_SYSTEM_INSTRUCTION
        self.endpoint = f"{self.base_url}/2012/hunyuan-t1" if self.base_url else None
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        self.custom_token = config.NEUVI_API_TOKEN

    @property
    def command_name(self) -> str:
        return "hunyuan-t1"

    @property
    def description(self) -> str:
        return "Generate a response using the custom Hunyuan T1 service"

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
                    raise RuntimeError(f"Hunyuan T1 API returned {response.status}: {text}")

                data = await response.json()
                content = data.get("response")
                thinking = data.get("thinking_content")

                if not content and not thinking:
                    raise RuntimeError("Hunyuan T1 API response did not include 'response' or 'thinking_content'.")

                # Process thinking content
                final_text = ""
                if thinking:
                    lines = thinking.splitlines()
                    prefixed_thinking_lines = []
                    for line in lines:
                        if line.strip():
                            prefixed_thinking_lines.append(f"-# {line}")
                        else:
                            prefixed_thinking_lines.append("")
                    
                    final_text = "\n".join(prefixed_thinking_lines)
                    if content:
                        final_text += f"\n\n{content}"
                else:
                    final_text = content

                return final_text.strip()

    @commands.command(name="hunyuan-t1", aliases=["t1", "hhh"])
    async def hunyuan_t1(self, ctx: commands.Context, *, prompt: str):
        """Generate a stateless Hunyuan T1 response."""
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
            return await ctx.reply("❌ Please provide a prompt for Hunyuan T1.")

        try:
            async with ctx.typing():
                result = await self._generate_response(prompt, user_id=str(ctx.author.id), name=ctx.author.name)
        except Exception as exc:  # pylint: disable=broad-except
            return await ctx.reply(f"❌ Hunyuan T1 request failed: {exc}")

        messages = self.split_message(result)
        if not messages:
            return await ctx.reply("⚠️ Hunyuan T1 returned an empty response.")

        await ctx.reply(messages[0])
        for message in messages[1:]:
            await ctx.send(message)

    @discord.app_commands.command(name="hunyuan-t1", description="Generate a response using the custom Hunyuan T1 service")
    @discord.app_commands.describe(prompt="The prompt to send to Hunyuan T1")
    async def slash_hunyuan_t1(self, interaction: discord.Interaction, prompt: str):
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
            return await interaction.followup.send(f"❌ Hunyuan T1 request failed: {exc}", ephemeral=True)

        messages = self.split_message(result)
        if not messages:
            return await interaction.followup.send("⚠️ Hunyuan T1 returned an empty response.")

        for message in messages:
            await interaction.followup.send(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(HunyuanT1Command(bot))
