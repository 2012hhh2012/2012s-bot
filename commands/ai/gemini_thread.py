import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai.types import Part
from ..base import BaseCommand
from config import config

class GeminiThreadCommand(BaseCommand):
    """Command to create Gemini conversation threads"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.thread_histories = getattr(bot, 'thread_histories', {})
        bot.thread_histories = self.thread_histories
        self.gemini_client = getattr(bot, 'gemini_client', None)
        self.gemini_model = getattr(bot, 'gemini_model', None)
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        self.max_thread_history = getattr(bot, 'max_thread_history', 20)
        self.max_file_size = getattr(bot, 'max_file_size', 20971520)
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
    
    @property
    def command_name(self) -> str:
        return "gemini-thread"
    
    @property
    def description(self) -> str:
        return "Start a Gemini conversation thread"

    def split_message(self, text: str, limit: int = 1990):
        """Split long text into chunks"""
        chunks = []
        in_codeblock = False
        while len(text) > limit:
            split_at = text.rfind("\n", 0, limit)
            if split_at == -1 or split_at < limit // 2:
                split_at = limit
            chunk = text[:split_at]
            text = text[split_at:]
            if chunk.count("```") % 2 == 1:
                chunk += "\n```"
                in_codeblock = True
            else:
                in_codeblock = False
            chunks.append(chunk)
            if in_codeblock and not text.lstrip().startswith("```"):
                text = "```\n" + text.lstrip()
        if text:
            if in_codeblock:
                if not text.rstrip().endswith("```"):
                    text += "\n```"
                in_codeblock = False
            chunks.append(text)
        return chunks

    @commands.command(name="gemini-thread", aliases=["gt"])
    async def gemini_thread(self, ctx, *, name=None):
        """
        Start a Gemini thread
        """
        if self.ai_toggle_users.get(str(ctx.author.id)) and self.ai_toggle_users[str(ctx.author.id)]["toggle"] == False:
            return await ctx.reply("AI features are disabled for you.")
        
        if not name:
            name = f"{ctx.author.name}'s Gemini Thread"

        thread = await ctx.channel.create_thread(
            name=name,
            type=discord.ChannelType.private_thread
        )
        await thread.add_user(ctx.author)
        await thread.join()

        await ctx.reply(f"{ctx.author.mention} ✅ Your Gemini chat has started! Talk to me here: {thread.mention}")
        
        self.thread_histories[thread.id] = {
            "history": [],
            "last_activity": datetime.now(timezone.utc),
            "owner": ctx.author.id,
            "response_pending": False,
        }

        await thread.send(f"{ctx.author.mention} ✅ Your Gemini chat has started! Talk to me here.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        thread_data = self.thread_histories.get(message.channel.id)
        if not thread_data:
            return

        # Cooldown check
        now = datetime.now(timezone.utc)
        user_id = message.author.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.COOLDOWN):
                return await message.reply(f"⏳ Please wait {config.COOLDOWN} seconds between requests.")
        self.bot.user_cooldowns[user_id] = now

        if not self.gemini_client or not self.gemini_model:
            await message.reply("❌ Gemini service is not available right now.")
            return

        thread_data["last_activity"] = datetime.now(timezone.utc)

        if thread_data.get("response_pending"):
            await message.reply("⚠️ Gemini is currently processing your previous message. Please wait for a response before sending another message.")
            return

        if not message.content and not message.attachments:
            await message.reply("❌ Please send a message or attach a file for Gemini to process.")
            return

        contents = [message.content or "See the files:"]
        attachment_parts = []

        for attachment in message.attachments:
            if attachment.size > self.max_file_size:
                max_mb = self.max_file_size // (1024 * 1024)
                await message.reply(f"❌ File **{attachment.filename}** is too large. Please keep files under {max_mb}MB.")
                return

            try:
                data = await attachment.read()
            except Exception as exc:  # pylint: disable=broad-except
                await message.reply(f"❌ Failed to read attachment: {exc}")
                return

            mime_type = attachment.content_type or "application/octet-stream"
            if mime_type.startswith("text/"):
                mime_type = "text/plain"

            attachment_parts.append(
                Part.from_bytes(
                    data=data,
                    mime_type=mime_type
                )
            )

        contents.extend(attachment_parts)

        history_entry = f"User: {message.content}" if message.content else "User: [Attachment]"

        thread_history = thread_data.setdefault("history", [])
        thread_history.append(history_entry)
        if len(thread_history) > self.max_thread_history:
            thread_history[:] = thread_history[-self.max_thread_history:]

        thread_data["response_pending"] = True

        try:
            async with message.channel.typing():
                async with self.ai_semaphore:
                    response = await asyncio.to_thread(
                        self.gemini_client.models.generate_content,
                        model=self.gemini_model,
                        contents=thread_history + contents,
                        config=genai.types.GenerateContentConfig(
                            tools=[{"google_search": {}}]
                        )
                    )

            output = getattr(response, "text", "") or ""
            output = output.strip()

            if not output:
                await message.reply("⚠️ Gemini returned an empty response.")
                if thread_history:
                    thread_history.pop()
                return

            thread_history.append(f"Gemini: {output}")
            if len(thread_history) > self.max_thread_history:
                thread_history[:] = thread_history[-self.max_thread_history:]

            chunks = self.split_message(output)
            await message.reply(chunks[0])
            for chunk in chunks[1:]:
                await asyncio.sleep(0.5)
                await message.channel.send(chunk)

        except Exception as exc:  # pylint: disable=broad-except
            await message.channel.send(f"❌ Error: {exc}")
            if thread_history:
                thread_history.pop()
        finally:
            thread_data["response_pending"] = False

    @discord.app_commands.command(name="gemini-thread", description="Start a Gemini conversation thread")
    @discord.app_commands.describe(name="The name of the thread")
    async def slash_gemini_thread(self, interaction: discord.Interaction, name: str = None):
        if self.ai_toggle_users.get(str(interaction.user.id)) and self.ai_toggle_users[str(interaction.user.id)]["toggle"] == False:
            return await interaction.response.send_message("AI features are disabled for you.", ephemeral=True)
        
        if not name:
            name = f"{interaction.user.name}'s Gemini Thread"

        thread = await interaction.channel.create_thread(
            name=name,
            type=discord.ChannelType.private_thread
        )
        await thread.add_user(interaction.user)
        
        self.thread_histories[thread.id] = {
            "history": [],
            "last_activity": datetime.now(timezone.utc),
            "owner": interaction.user.id,
            "response_pending": False,
        }

        await interaction.response.send_message(f"✅ Your Gemini chat has started! Talk to me here: {thread.mention}")
        await thread.send(f"{interaction.user.mention} ✅ Your Gemini chat has started! Talk to me here.")

async def setup(bot):
    await bot.add_cog(GeminiThreadCommand(bot))
