import discord
from discord.ext import commands
import asyncio
import os
from google import genai
from google.genai.types import Part
from datetime import datetime, timezone, timedelta
from config import config
from ..base import BaseCommand

class GeminiCommand(BaseCommand):
    """Gemini AI command for asking questions"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.gemini_client = getattr(bot, 'gemini_client', None)
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        self.max_file_size = getattr(bot, 'max_file_size', 20971520)
        self.max_message_length = getattr(bot, 'max_message_length', 1990)
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
    
    @property
    def command_name(self) -> str:
        return "gemini"
    
    @property
    def description(self) -> str:
        return "Ask Google Gemini AI a question"
    
    def split_message(self, text: str, limit: int = None):
        """Split long text into chunks"""
        if limit is None:
            limit = self.max_message_length
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
    
    async def run_gemini(self, interaction: discord.Interaction, prompt: str, attachment: discord.Attachment = None):
        if self.ai_toggle_users.get(str(interaction.user.id)) and self.ai_toggle_users[str(interaction.user.id)]["toggle"] == False:
            return await interaction.response.send_message("AI features are disabled for you.", ephemeral=True)
        
        await interaction.response.defer(thinking=True)
        try:
            if not os.getenv("GEMINI_API_KEY"):
                return await interaction.followup.send("Gemini API key is not configured on the bot.", ephemeral=True)
            
            contents = [prompt or "See the files:"]

            if attachment:
                if attachment.size > self.max_file_size:
                    max_mb = self.max_file_size // (1024 * 1024)
                    return await interaction.followup.send(f"❌ File **{attachment.filename}** is too large. Please keep files under {max_mb}MB.", ephemeral=True)
                
                data = await attachment.read()
                mime_type = attachment.content_type
                        
                if mime_type and mime_type.startswith("text/"):
                    mime_type = 'text/plain'
                else:
                    mime_type = mime_type or "application/octet-stream"

                attachment_part = Part.from_bytes(
                    data=data,
                    mime_type=mime_type
                )
                contents.append(attachment_part)

            async with self.ai_semaphore:
                response = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model=self.gemini_model,
                    contents=contents,
                    config=genai.types.GenerateContentConfig(
                            tools=[{"google_search": {} }]
                        )
                )

            output = getattr(response, "text", "") or ""
            output = output.strip()

            if not output:
                return await interaction.followup.send("⚠️ Gemini returned an empty response.", ephemeral=True)

            chunks = self.split_message(output)
            if not chunks:
                return await interaction.followup.send("⚠️ Gemini returned content that couldn't be sent.", ephemeral=True)

            for chunk in chunks:
                await asyncio.sleep(0.5)
                await interaction.followup.send(chunk)

        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error: {e}")
            except Exception:
                import logging
                logging.exception("Failed to send Gemini error message.")

    @commands.command(name="gemini", aliases=["g","google"])
    async def gemini(self, ctx, *,prompt):
        """
        Ask Google Gemini (2.5 Flash) a question
        """
        now = datetime.now(timezone.utc)
        user_id = ctx.author.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.GEMINI_COOLDOWN):
                return await ctx.reply(f"⏳ Please wait {config.GEMINI_COOLDOWN} seconds between requests.")
        self.bot.user_cooldowns[user_id] = now

        if self.ai_toggle_users.get(str(ctx.author.id)) and self.ai_toggle_users[str(ctx.author.id)]["toggle"] == False:
            return await ctx.reply("AI features are disabled for you.")

        if not prompt and not ctx.message.attachments:
            return await ctx.reply("❌ Please provide a prompt.")
        
        if not os.getenv("GEMINI_API_KEY"):
            return await ctx.reply("Gemini API key is not configured on the bot.")

        contents = [prompt or "See the files:"]
        attachment = ctx.message.attachments[0] if ctx.message.attachments else None

        if attachment:
            if attachment.size > self.max_file_size:
                max_mb = self.max_file_size // (1024 * 1024)
                return await ctx.reply(f"❌ File **{attachment.filename}** is too large. Please keep files under {max_mb}MB.")

            data = await attachment.read()
            mime_type = attachment.content_type

            if mime_type and mime_type.startswith("text/"):
                mime_type = 'text/plain'
            else:
                mime_type = mime_type or "application/octet-stream"

            attachment_part = Part.from_bytes(
                data=data,
                mime_type=mime_type
            )
            contents.append(attachment_part)

        async with ctx.typing():
            try:
                async with self.ai_semaphore:
                    response = await asyncio.to_thread(
                        self.gemini_client.models.generate_content,
                        model=self.gemini_model,
                        contents=contents,
                        config=genai.types.GenerateContentConfig(
                            tools=[{"google_search": {} }]
                        )
                    )

                output = getattr(response, "text", "") or ""
                output = output.strip()

                if not output:
                    return await ctx.reply("⚠️ Gemini returned an empty response.")

                chunks = self.split_message(output)
                if not chunks:
                    return await ctx.reply("⚠️ Gemini returned content that couldn't be sent.")

                await ctx.reply(chunks[0])
                for chunk in chunks[1:]:
                    await asyncio.sleep(0.5)
                    await ctx.send(chunk)

            except Exception as e:
                await ctx.reply(f"❌ Error: {e}")

    @discord.app_commands.command(name="gemini", description="Ask Google Gemini (2.5 Flash) a question")
    @discord.app_commands.describe(prompt="The question to ask")
    async def slash_gemini(self, interaction: discord.Interaction, prompt: str, attachment: discord.Attachment=None):
        now = datetime.now(timezone.utc)
        user_id = interaction.user.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.GEMINI_COOLDOWN):
                return await interaction.response.send_message(f"⏳ Please wait {config.GEMINI_COOLDOWN} seconds between requests.", ephemeral=True)
        self.bot.user_cooldowns[user_id] = now
        
        await self.run_gemini(interaction, prompt, attachment)

# Context menu must be defined outside the class  
@discord.app_commands.context_menu(name="Ask Gemini")
async def context_ask_gemini(interaction: discord.Interaction, message: discord.Message):
    cog = interaction.client.get_cog("GeminiCommand")
    if not cog:
        return await interaction.response.send_message("❌ Gemini service not available.", ephemeral=True)
    
    now = datetime.now(timezone.utc)
    user_id = interaction.user.id
    if user_id in cog.bot.user_cooldowns:
        last_used = cog.bot.user_cooldowns[user_id]
        if now - last_used < timedelta(seconds=config.GEMINI_COOLDOWN):
            return await interaction.response.send_message(f"⏳ Please wait {config.GEMINI_COOLDOWN} seconds between requests.", ephemeral=True)
    cog.bot.user_cooldowns[user_id] = now
    
    await cog.run_gemini(interaction, message.content, message.attachments[0] if message.attachments else None)

async def setup(bot):
    await bot.add_cog(GeminiCommand(bot))
    bot.tree.add_command(context_ask_gemini)
