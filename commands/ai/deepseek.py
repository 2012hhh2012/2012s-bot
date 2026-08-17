import discord
from discord.ext import commands
from typing import Optional, AsyncGenerator
import json
import asyncio
from datetime import datetime, timezone, timedelta

from ..base import BaseCommand
from config import config


class DeepseekCommand(BaseCommand):
    """Command for interacting with the custom Deepseek service."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        # self.base_url = (config.NEUVI_API_URL or "").rstrip("/")
        # self.system_prompt = config.DEEPSEEK_SYSTEM_INSTRUCTION
        # self.endpoint = f"{self.base_url}/raw/deepseek" if self.base_url else None
        # self.custom_token = config.NEUVI_API_TOKEN
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        self.messa_ai_client = bot.messa_ai_client

    @property
    def command_name(self) -> str:
        return "deepseek"

    @property
    def description(self) -> str:
        return "Generate a response using the custom Deepseek service"

    # async def _generate_response(self, message: str, user_id: str, name: str) -> AsyncGenerator[str, None]:
    async def _generate_response(self, message: str) -> Optional[str]:
        # if not self.endpoint:
        #     raise RuntimeError("NEUVI_API_URL is not configured on the bot.")

        # session = getattr(self.bot, "session", None)
        # if session is None:
        #     raise RuntimeError("HTTP session is not available on the bot.")

        # payload = {
        #     "message": message,
        #     "user_id": user_id,
        #     "system_prompt": self.system_prompt,
        #     "search": True,
        #     "stream": True,
        #     "name": name
        # }

        # headers = {}
        # if self.custom_token:
        #     headers["Authorization"] = f"Bearer {self.custom_token}"

        async with self.ai_semaphore:
            completion = await self.messa_ai_client.chat.completions.create(
                model="DeepSeek V3",
                seed=0,
                messages=[
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            )

            return completion.choices[0].message.content
        
            # async with session.post(self.endpoint, json=payload, headers=headers) as response:
            #     if response.status != 200:
            #         text = await response.text()
            #         raise RuntimeError(f"Deepseek API returned {response.status}: {text}")

            #     full_content = ""
            #     buffer = ""
                
            #     while True:
            #         # Use readany() for the most immediate delivery of bytes
            #         raw_chunk = await response.content.readany()
            #         if not raw_chunk:
            #             break
                        
            #         buffer += raw_chunk.decode("utf-8", errors="ignore")
                    
            #         # Process all complete "data: " lines in the buffer
            #         while "data: " in buffer:
            #             # Find start of data: line
            #             start_idx = buffer.find("data: ")
            #             # Find end of line (next newline)
            #             end_idx = buffer.find("\n", start_idx)
                        
            #             if end_idx == -1:
            #                 # Partial line, stop and wait for more data
            #                 break
                            
            #             line = buffer[start_idx:end_idx].strip()
            #             # Remove processed part from buffer
            #             buffer = buffer[end_idx:].lstrip()
                        
            #             # Extract JSON content
            #             content_str = line[len("data: "):].strip()
            #             if not content_str or content_str == "[DONE]":
            #                 continue
                            
            #             try:
            #                 data = json.loads(content_str)
            #                 cc = data.get("content", "")
                            
            #                 # Fallback to standard OpenAI choices structure
            #                 if not cc and "choices" in data:
            #                     choices = data["choices"]
            #                     if choices and "delta" in choices[0]:
            #                         cc = choices[0]["delta"].get("content", "")
                            
            #                 if cc:
            #                     full_content += cc
            #                     yield self._clean_response(full_content)
            #             except json.JSONDecodeError:
            #                 continue

    # def _clean_response(self, text: str) -> str:
    #     """Strip analysis blocks, SEARCHING artifacts, and labels from the Deepseek output."""
    #     if not text:
    #         return text

    #     res = text.lstrip()
        
    #     # Remove SEARCHINGFINISHED / SEARCHING at start
    #     if res.upper().startswith("SEARCHINGFINISHED"):
    #         res = res[len("SEARCHINGFINISHED"):].lstrip()
    #     elif res.upper().startswith("SEARCHING"):
    #         # If it's just "SEARCHING" or similar, check if something comes after
    #         # If nothing comes after, it's still searching, so keep it hidden/empty
    #         # or if it's the start of the message, strip it
    #         temp = res[len("SEARCHING"):].lstrip()
    #         # If it was exactly "SEARCHING", return empty to keep thinking
    #         if not temp:
    #             return ""
    #         res = temp

    #     # Handle official model response markers
    #     marker_variants = ["**💬 Response:**", "💬 Response:"]
    #     for marker in marker_variants:
    #         if marker in res:
    #             _, remainder = res.split(marker, 1)
    #             return remainder.lstrip()
        
    #     return res

    # def _split_response_messages(self, text: str) -> list[str]:
    #     """Split response into Discord-safe chunks at newlines."""
    #     if not text:
    #         return []

    #     messages: list[str] = []
    #     for line in text.splitlines() or [text]:
    #         normalized = line if line else "\u200b"
    #         messages.extend(self.split_message(normalized))
    #     return messages

    @commands.command(name="deepseek", aliases=["ds", "d"])
    async def deepseek(self, ctx: commands.Context, *, prompt: str):
        """Generate a stateless Deepseek response."""
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
            return await ctx.reply("❌ Please provide a prompt for Deepseek.")
        
        try:
            async with ctx.typing():
                result = await self._generate_response(prompt)
        except Exception as exc:  # pylint: disable=broad-except
            return await ctx.reply(f"❌ Deepseek request failed: {exc}")

        messages = self.split_message(result)
        if not messages:
            return await ctx.reply("⚠️ Deepseek returned an empty response.")

        await ctx.reply(messages[0])
        for message in messages[1:]:
            await ctx.send(message)

        # reply_msg = await ctx.reply(f"{config.LOADING_EMOJI} Deepseek is thinking...")
        
        # full_result = ""
        # last_edit_time = 0
        
        # try:
        #     async for partial in self._generate_response(prompt, user_id=str(ctx.author.id), name=ctx.author.name):
        #         if not partial:
        #             continue
        #         full_result = partial
        #         now_loop = asyncio.get_event_loop().time()
        #         # Instant first byte, then 1.5s throttle to accumulate chunks
        #         if last_edit_time == 0 or (now_loop - last_edit_time >= 1.5):
        #             try:
        #                 content = full_result[:1990]
        #                 await reply_msg.edit(content=content)
        #                 last_edit_time = now_loop
        #             except discord.HTTPException:
        #                 pass
        # except Exception as exc:
        #     return await reply_msg.edit(content=f"❌ Deepseek request failed: {exc}")

        # if not full_result:
        #     return await reply_msg.edit(content="⚠️ Deepseek returned an empty response.")

        # messages = self.split_message(full_result)
        # if messages:
        #     await reply_msg.edit(content=messages[0])
        #     for message in messages[1:]:
        #         await ctx.send(message)

    @discord.app_commands.command(name="deepseek", description="Generate a response using the custom Deepseek service")
    @discord.app_commands.describe(prompt="The prompt to send to Deepseek")
    async def slash_deepseek(self, interaction: discord.Interaction, prompt: str):
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
            return await interaction.followup.send(f"❌ Deepseek request failed: {exc}", ephemeral=True)

        messages = self.split_message(result)
        if not messages:
            return await interaction.followup.send("⚠️ Deepseek returned an empty response.")

        for message in messages:
            await interaction.followup.send(message)
        
        # full_result = ""
        # last_edit_time = 0
        
        # try:
        #     async for partial in self._generate_response(prompt, user_id=str(interaction.user.id), name=interaction.user.name):
        #         if not partial:
        #             continue
        #         full_result = partial
        #         now_loop = asyncio.get_event_loop().time()
        #         # Instant first byte, then 1.5s throttle to accumulate chunks
        #         if last_edit_time == 0 or (now_loop - last_edit_time >= 1.5):
        #             try:
        #                 content = full_result[:1990]
        #                 await interaction.edit_original_response(content=content)
        #                 last_edit_time = now_loop
        #             except discord.HTTPException:
        #                 pass
        # except Exception as exc:
        #     return await interaction.followup.send(f"❌ Deepseek request failed: {exc}", ephemeral=True)

        # if not full_result:
        #     return await interaction.followup.send("⚠️ Deepseek returned an empty response.")

        # messages = self.split_message(full_result)
        # # Edit the deferred message with the first chunk
        # await interaction.edit_original_response(content=messages[0])
        # # Send subsequent chunks if any
        # for message in messages[1:]:
        #     await interaction.followup.send(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(DeepseekCommand(bot))
