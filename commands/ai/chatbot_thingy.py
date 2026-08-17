import asyncio
import discord
from discord.ext import commands
from google.genai.types import Part
from google import genai
from datetime import datetime, timezone, timedelta
from config import config
from ..base import BaseCommand


class ChatbotThingyCommand(BaseCommand): # Modified
    """Commands to interact with Chatbot Thingy using Gemini"""

    def __init__(self, bot):
        super().__init__(bot)
        self.gemini_client: genai.Client = getattr(bot, "gemini_client")
        self.gemini_model: str = getattr(bot, "gemini_model")
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})

    @property
    def command_name(self) -> str:
        return "chatbot-thingy"

    @property
    def description(self) -> str:
        return "Ask Chatbot Thingy a question"

    def _build_contents(self, prompt: str, attachments: list[discord.Attachment]):
        contents: list = [prompt or "See the files:"]
        for attachment in attachments:
            if attachment.size > self.max_file_size:
                raise ValueError(f"File {attachment.filename} is too large")
            data = asyncio.run_coroutine_threadsafe(attachment.read(), self.bot.loop).result()
            mime_type = attachment.content_type
            if mime_type and mime_type.startswith("text/"):
                mime_type = "text/plain"
            else:
                mime_type = mime_type or "application/octet-stream"
            contents.append(Part.from_bytes(data=data, mime_type=mime_type))
        return contents

    async def _generate_reply(self, contents):
        async with self.bot.ai_semaphore:
            response = await asyncio.to_thread(
                self.gemini_client.models.generate_content,
                model=self.gemini_model,
                contents=contents,
                config=genai.types.GenerateContentConfig(system_instruction=self._system_prompt(), tools=[{"google_search": {}}]),
            )
        return response.text

    def _system_prompt(self) -> str:
        return ("""You're a funny chatbot on discord named Chatbot Thingy that chat with the user,
your primary language is english, be casual, don't use characters like ', don't capitalize your words,
try to keep your response short enough so it's funny

you can see some structures like:
- username: message
that's the user's message, and:
- chatbot thingy: message
that's your message,
also you don't need to add \"chatbot thingy:\" at the start of your message,

follow the brackets and understand the context, only reply to the message which is requested.
Context format: [context: neuvi: ... assistant: ... 2012hhh2012: ... /end] reply to neuvi: hi
ok thats all, now goodluck!"""
        )

    @commands.command(name="chatbot-thingy", aliases=["ct", "chat", "chatbot_thingy"])
    async def chatbot_thingy(self, ctx: commands.Context, *, message: str):
        now = datetime.now(timezone.utc)
        user_id = ctx.author.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.COOLDOWN):
                return await ctx.reply(f"⏳ Please wait {config.COOLDOWN} seconds between requests.")
        self.bot.user_cooldowns[user_id] = now

        if self.ai_toggle_users.get(str(ctx.author.id)) and self.ai_toggle_users[str(ctx.author.id)]["toggle"] == False:
            return await ctx.reply("AI features are disabled for you.")
        
        if not message and not ctx.message.attachments:
            await ctx.reply("❌ Please provide a prompt.")
            return
        
        prompt = self._build_contents(f"{ctx.author.name}: {message}", ctx.message.attachments)

        async with ctx.typing():
            try:
                async with self.bot.ai_semaphore:
                    response = await asyncio.to_thread(
                        self.gemini_client.models.generate_content,
                        model=self.gemini_model,
                        contents=prompt,
                        config=genai.types.GenerateContentConfig(
                            system_instruction=self._system_prompt(), tools=[{"google_search": {}}]
                        ),
                    )
                text = response.text
                chunks = self.split_message(text)
                await ctx.reply(chunks[0])
                for chunk in chunks[1:]:
                    await asyncio.sleep(0.5)
                    await ctx.send(chunk)
            except Exception as exc:
                await ctx.reply(f"❌ Error: {exc}")

    @discord.app_commands.command(name="chatbot-thingy", description="Chat with Chatbot Thingy")
    async def slash_chatbot_thingy(
        self,
        interaction: discord.Interaction,
        message: str,
        attachment: discord.Attachment | None = None,
    ):
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

        prompt = self._build_contents(f"{interaction.user.name}: {message}", [attachment] if attachment else [])

        try:
            async with self.bot.ai_semaphore:
                response = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model=self.gemini_model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=self._system_prompt(), tools=[{"google_search": {}}]
                    ),
                )
            text = response.text
            chunks = self.split_message(text)
            for chunk in chunks:
                await asyncio.sleep(0.5)
                await interaction.followup.send(chunk)
        except Exception as exc:
            await interaction.followup.send(f"❌ Error: {exc}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatbotThingyCommand(bot))
