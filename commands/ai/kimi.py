import discord
from discord.ext import commands
from typing import Optional
from datetime import datetime, timezone, timedelta

from ..base import BaseCommand
from config import config


class KimiCommand(BaseCommand):
    """Command for interacting with the Kimi service."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        # self.base_url = (config.NEUVI_API_URL or "").rstrip("/")
        # self.system_prompt = config.KIMI_SYSTEM_INSTRUCTION
        # self.endpoint = f"{self.base_url}/2012/kimi" if self.base_url else None
        # self.custom_token = config.NEUVI_API_TOKEN
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        self.messa_ai_client = bot.messa_ai_client

    @property
    def command_name(self) -> str:
        return "kimi"

    @property
    def description(self) -> str:
        return "Generate a response (with false) using the Kimi service"

    # async def _generate_response(self, message: str, user_id: str, name: str) -> Optional[str]:
    async def _generate_response(self, message: str) -> Optional[str]:
        async with self.ai_semaphore:
            completion = await self.messa_ai_client.chat.completions.create(
                model="Kimi K2 Thinking",
                seed=0,
                messages=[
                    {"role": "user", "content": message}
                ]
            )

            return completion.choices[0].message.content
        
        # if not self.endpoint:
        #     raise RuntimeError("NEUVI_API_URL is not configured on the bot.")

        # session = getattr(self.bot, "session", None)
        # if session is None:
        #     raise RuntimeError("HTTP session is not available on the bot.")

        # payload = {
        #     "name": name,
        #     "message": message,
        #     "user_id": user_id,
        #     "system_prompt": self.system_prompt,
        #     "thinking": False,
        #     "search": True,
        #     "model": "k2",
        #     "stream": False
        # }

        # headers = {"Authorization": self.custom_token} if self.custom_token else {}

        # async with self.ai_semaphore:
        #     async with session.post(self.endpoint, json=payload, headers=headers) as response:
        #         if response.status != 200:
        #             text = await response.text()
        #             raise RuntimeError(f"Kimi API returned {response.status}: {text}")

        #         data = await response.json()

        #         content = data.get("response") or data.get("content") or data.get("message")
        #         thinking = data.get("thinking_content") or data.get("thinking")

        #         if not content and not thinking:
        #              pass
                
        #         final_text = ""
        #         if thinking:
        #             lines = thinking.splitlines()
        #             prefixed_thinking_lines = []
        #             for line in lines:
        #                 if line.strip():
        #                     prefixed_thinking_lines.append(f"-# {line}")
        #                 else:
        #                     prefixed_thinking_lines.append("")
                    
        #             final_text = "\n".join(prefixed_thinking_lines)
        #             if content:
        #                 final_text += f"\n\n{content}"
        #         else:
        #             final_text = content if content else str(data)

        #         return final_text.strip()

    @commands.command(name="kimi")
    async def kimi(self, ctx: commands.Context, *, prompt: str):
        """Generate a Kimi response."""
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
            return await ctx.reply("❌ Please provide a prompt for Kimi.")

        try:
            async with ctx.typing():
                result = await self._generate_response(prompt)
        except Exception as exc:  # pylint: disable=broad-except
            return await ctx.reply(f"❌ Kimi request failed: {exc}")

        messages = self.split_message(result)
        if not messages:
            return await ctx.reply("⚠️ Kimi returned an empty response.")

        await ctx.reply(messages[0])
        for message in messages[1:]:
            await ctx.send(message)

    @discord.app_commands.command(name="kimi", description="Generate a response using the Kimi service")
    @discord.app_commands.describe(prompt="The prompt to send to Kimi")
    async def slash_kimi(self, interaction: discord.Interaction, prompt: str):
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
            result = await self._generate_response(prompt)
        except Exception as exc:  # pylint: disable=broad-except
            return await interaction.followup.send(f"❌ Kimi request failed: {exc}", ephemeral=True)

        messages = self.split_message(result)
        if not messages:
            return await interaction.followup.send("⚠️ Kimi returned an empty response.")

        for message in messages:
            await interaction.followup.send(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(KimiCommand(bot))
