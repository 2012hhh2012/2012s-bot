import asyncio
import discord
from discord.ext import commands
import json
from google import genai
from datetime import datetime, timezone
from ..base import BaseCommand
import os
from datetime import timedelta

class TranslateWithGeminiCommand(BaseCommand):
    """Command to translate text using Gemini AI"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.gemini_client = getattr(bot, 'gemini_client')
        self.gemini_model = getattr(bot, 'gemini_model')
        self.ai_semaphore = getattr(bot, 'ai_semaphore')
        self.user_cooldowns = getattr(bot, 'user_cooldowns', {})
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
    
    @property
    def command_name(self) -> str:
        return "translate_with_gemini"
    
    @property
    def description(self) -> str:
        return "Translate text using Google Gemini AI"

    def check_cooldown(self, user_id: int, command_name: str, cooldown_seconds: int = 2):
        """Check if user is on cooldown"""
        key = f"{user_id}_{command_name}"
        now = datetime.now(timezone.utc)
        
        if key in self.user_cooldowns:
            cooldown_end = self.user_cooldowns[key]
            if cooldown_end > now:
                return False, cooldown_end
        
        self.user_cooldowns[key] = now + timedelta(seconds=cooldown_seconds)
        return True, None

    def get_system_prompt(self, target_language: str) -> str:
        return f"""
            You're a translator, follow the instructions below.
            Detect the language of the text and translate it to {target_language}.
            Then rate how confident you are in the translation (0-100).

            If the target language is misspelled or not exact, auto-correct it to a valid language name. 
            If the text cannot be translated (e.g., slang, Gen Z words, onomatopoeia, or non-language input), 
            still respond politely and provide a meaningful explanation in the translation field (don't respond too long).

            Respond **only** in this exact JSON and in valid raw JSON (ABSOLUTELY NO markdown, NO code blocks):

            {{
            "detected_language": "<language name or mixed (tell languages name if mixed)>",
            "target_language_normalized": "<corrected target language name>",
            "translation": "<translated text or friendly explanation>",
            "confidence": <number between 0 and 100>
            }}

            good, now do your job.
        """

    @discord.app_commands.command(name="translate-with-gemini", description="Translate a message using Google Gemini")
    @discord.app_commands.describe(
        message="The message to translate",
        target_language="The target language to translate to"
    )
    async def slash_translate_with_gemini(self, interaction: discord.Interaction, message: str, target_language: str = "English"):
        if self.ai_toggle_users.get(str(interaction.user.id)) and not self.ai_toggle_users[str(interaction.user.id)]["toggle"]:
            return await interaction.response.send_message("❌ AI commands are disabled for you.", ephemeral=True)
        
        if not message:
            return await interaction.response.send_message("❌ Please provide a message to translate.", ephemeral=True)
        
        await interaction.response.defer(thinking=True)

        system_prompt = self.get_system_prompt(target_language)
        prompt = f"""
            target_language: {target_language}.
            Text: "{message}"
        """
        
        # check cooldown
        allowed, cooldown_end = self.check_cooldown(interaction.user.id, "gemini", cooldown_seconds=2)

        if not allowed:
            timestamp = int(cooldown_end.timestamp())
            time_left = (cooldown_end - datetime.now(timezone.utc)).total_seconds()
            return await interaction.followup.send(f"⏳ Cooldown! Try again in <t:{timestamp}:R>", delete_after=time_left + 1)
        
        start_time = datetime.now()

        try:
            async with self.ai_semaphore:
                response = await asyncio.to_thread(
                            self.gemini_client.models.generate_content,
                            model=self.gemini_model,
                            contents=prompt,
                            config=genai.types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                tools=[{"google_search": {} }]
                            )
                        )
            
        except Exception as e:
            return await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
        
        raw = response.text

        if not raw:
            return await interaction.followup.send("⚠️ Gemini returned an empty response, the prompt may contain bad words.", ephemeral=True)

        # parse response
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            # if gemini doesn't reply perfectly formatted JSON
            return await interaction.followup.send(f"❌ Gemini returned an invalid response. Error: {e}", ephemeral=True)
        
        detected_language = data["detected_language"]
        target_language_normalized = data["target_language_normalized"]
        translation = data["translation"]
        confidence = data["confidence"]
        elapsed = (datetime.now() - start_time).total_seconds()

        embed = discord.Embed(
            title=f"🌐 Translation ({detected_language} → {target_language_normalized})",
            color=discord.Color.blurple()
        )

        embed.add_field(name="📝 Original Prompt", value=f"{message}", inline=False)
        embed.add_field(name="💬 Translation / Comment", value=f"{translation}", inline=False)

        embed.add_field(name="💯 Confidence", value=f"{confidence}%", inline=True)
        embed.add_field(name="⚡ Response Time", value=f"{elapsed:.2f}s", inline=True)
        embed.set_footer(text="Powered by Gemini AI")

        await interaction.followup.send(embed=embed)

# Context menu must be defined outside the class  
@discord.app_commands.context_menu(name="Translate with gemini")
async def context_translate_with_gemini(interaction: discord.Interaction, message: discord.Message):
    if interaction.client.ai_toggle_users.get(str(interaction.user.id)) and not interaction.client.ai_toggle_users[str(interaction.user.id)]["toggle"]:
        return await interaction.response.send_message("❌ AI commands are disabled for you.", ephemeral=True)
    
    if not message.content:
        return await interaction.response.send_message("❌ This message has no text to translate.", ephemeral=True)
    
    # Get cog instance to use slash command functionality
    cog = interaction.client.get_cog("TranslateWithGeminiCommand")
    if not cog:
        return await interaction.response.send_message("❌ Translation service not available.", ephemeral=True)
    
    await cog.slash_translate_with_gemini(interaction, message.content, "English")

async def setup(bot):
    await bot.add_cog(TranslateWithGeminiCommand(bot))
    bot.tree.add_command(context_translate_with_gemini)
