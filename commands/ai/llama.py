import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timezone, timedelta
from config import config
from ..base import BaseCommand

class LlamaCommand(BaseCommand):
    """Llama AI command using Cerebras with Groq fallback"""
    
    def __init__(self, bot):
        super().__init__(bot)
        # Cerebras Setup
        self.cerebras_client = getattr(bot, 'cerebras_client', None)
        self.cerebras_model = getattr(bot, 'cerebras_model', None)

        # Messa AI Setup
        self.messa_ai_client = getattr(bot, 'messa_ai_client', None)
        self.messa_ai_model = "Llama 4 Scout"
        
        # Groq Setup
        self.groq_client = getattr(bot, 'groq_client', None)
        self.groq_model = getattr(bot, 'groq_model', None)
        
        # Shared Resources
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        self.max_message_length = getattr(bot, 'max_message_length', 1990)
        self.max_tokens = config.GROQ_MAX_TOKENS
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
    
    @property
    def command_name(self) -> str:
        return "llama"
    
    @property
    def description(self) -> str:
        return "Ask Llama AI a question (Cerebras/Groq)"
    
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
    
    @commands.command(name="llama", aliases=["groq", "l"])
    async def llama(self, ctx, *, prompt):
        """
        Ask Llama (3) a question.
        Tries Cerebras first, then falls back to Groq.
        """
        now = datetime.now(timezone.utc)
        user_id = ctx.author.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.LLAMA_COOLDOWN):
                return await ctx.reply(f"⏳ Please wait {config.LLAMA_COOLDOWN} seconds between requests.")
        self.bot.user_cooldowns[user_id] = now

        if self.ai_toggle_users.get(str(ctx.author.id)) and self.ai_toggle_users[str(ctx.author.id)]["toggle"] == False:
            return await ctx.reply("AI features are disabled for you.")
        
        if not prompt:
            return await ctx.reply("❌ Please provide a prompt.")
        
        async with ctx.typing():
            try:
                output = None
                finish_reason = None
                used_provider = "Cerebras"

                # Old Cerebras
                # if self.cerebras_client:
                #     try:
                #         async with self.ai_semaphore:                                                 
                #             response = await asyncio.to_thread(
                #                 self.cerebras_client.chat.completions.create,
                #                 model=self.cerebras_model,
                #                 messages=[{"role": "user", "content": prompt}],
                #                 max_tokens=self.max_tokens
                #             )
                #         output = response.choices[0].message.content.strip()
                #         finish_reason = response.choices[0].finish_reason
                #     except Exception as e:
                #         print(f"Cerebras error, falling back to Groq: {e}")
                
                # 1. Try Messa AI
                if self.messa_ai_client:
                    try:
                        async with self.ai_semaphore:
                            response = await asyncio.to_thread(
                                self.messa_ai_client.chat.completions.create,
                                model=self.messa_ai_model,
                                seed=0,
                                messages=[{"role": "user", "content": prompt}],
                                max_tokens=self.max_tokens
                            )
                        output = response.choices[0].message.content.strip()
                        finish_reason = response.choices[0].finish_reason
                    except Exception as e:
                        print(f"Messa AI error, falling back to Groq: {e}")

                # 2. Fallback to Groq if Messa AI failed or is missing
                if not output and self.groq_client:
                    used_provider = "Groq"
                    async with self.ai_semaphore:
                        response = await self.messa_ai_client.chat.completions.create(
                            model=self.messa_ai_model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=self.max_tokens
                        )
                    output = response.choices[0].message.content.strip()
                    finish_reason = response.choices[0].finish_reason
                
                if not output:
                    return await ctx.reply("⚠️ Llama returned empty response from all providers.")
                
                chunks = self.split_message(output)
                await ctx.reply(content=chunks[0])
                
                if len(chunks) > 1:
                    for chunk in chunks[1:]:
                        await asyncio.sleep(0.5)
                        await ctx.send(chunk)

                if finish_reason == "length":
                    await ctx.send(f"⚠️ *Response from {used_provider} cut off (hit token limit). Try shorter prompt*")
                        
            except Exception as e:
                if len(str(e)) > 2000:
                    await ctx.reply("An error occurred when running llama but it's too large to send")
                else:
                    await ctx.reply(f"❌ Error: {e}")

    @discord.app_commands.command(name="llama", description="Ask Llama (3) a question")
    @discord.app_commands.describe(prompt="The question to ask")
    async def slash_llama(self, interaction: discord.Interaction, prompt: str):
        now = datetime.now(timezone.utc)
        user_id = interaction.user.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.LLAMA_COOLDOWN):
                return await interaction.response.send_message(f"⏳ Please wait {config.LLAMA_COOLDOWN} seconds between requests.", ephemeral=True)
        self.bot.user_cooldowns[user_id] = now

        if self.ai_toggle_users.get(str(interaction.user.id)) and self.ai_toggle_users[str(interaction.user.id)]["toggle"] == False:
            return await interaction.response.send_message("AI features are disabled for you.", ephemeral=True)
        
        await interaction.response.defer(thinking=True)

        try:
            output = None
            finish_reason = None
            
            # Old Cerebras
            # if self.cerebras_client:
            #     try:
            #         async with self.ai_semaphore:
            #             response = await asyncio.to_thread(
            #                 self.cerebras_client.chat.completions.create,
            #                 model=self.cerebras_model,
            #                 messages=[{"role": "user", "content": prompt}],
            #                 max_tokens=self.max_tokens
            #             )
            #         output = response.choices[0].message.content.strip()
            #     except Exception as e:
            #         print(f"Cerebras slash error, falling back to Groq: {e}")

            # 1. Try Messa AI
            if self.messa_ai_client:
                try:
                    async with self.ai_semaphore:
                        response = await self.messa_ai_client.chat.completions.create(
                            model=self.messa_ai_model,
                            seed=0,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=self.max_tokens
                        )
                    output = response.choices[0].message.content.strip()
                except Exception as e:
                    print(f"Messa AI slash error, falling back to Groq: {e}")

            # 2. Fallback to Groq
            if not output and self.groq_client:
                async with self.ai_semaphore:
                    response = await asyncio.to_thread(
                        self.groq_client.chat.completions.create,
                            model=self.groq_model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=self.max_tokens
                        )
                output = response.choices[0].message.content.strip()
            
            if not output:
                return await interaction.followup.send("⚠️ Llama returned empty response from all providers.", ephemeral=True)
            
            chunks = self.split_message(output)
            for chunk in chunks:
                await asyncio.sleep(0.5)
                await interaction.followup.send(chunk)
                    
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(LlamaCommand(bot))
