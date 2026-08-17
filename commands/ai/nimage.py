import discord
from discord.ext import commands
from typing import Optional
import io
from datetime import datetime, timezone, timedelta

from ..base import BaseCommand
from config import config

class NimageCommand(BaseCommand):

    def __init__(self, bot: commands.Bot):
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        super().__init__(bot)
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        self.base_url = (config.NEUVI_API_URL or "").rstrip("/")
        self.endpoint = f"{self.base_url}/raw/image" if self.base_url else None
        self.custom_token = config.NEUVI_API_TOKEN
        self.nsfw_detetor_endpoint = "https://2012hhh2012-nsfw-detector.hf.space/detect"
        self.nsfw_host_channel_id = 1461381591019425853

    @property
    def command_name(self) -> str:
        return "nimage"

    @property
    def description(self) -> str:
        return "Generate an image using the custom Neuvi API image service"

    async def _generate_image(
            self,
            prompt: str,
            user_id: str,
            name: str
        ) -> io.BytesIO:
        if not self.endpoint:
            raise RuntimeError("NEUVI_API_URL is not configured on the bot.")

        session = getattr(self.bot, "session", None)
        if session is None:
            raise RuntimeError("HTTP session is not available on the bot.")

        payload = {
            "name": name,
            "prompt": prompt,
            "user_id": user_id
        }

        headers = {}
        if self.custom_token:
            headers["Authorization"] = f"Bearer {self.custom_token}"

        async with self.ai_semaphore:
            async with session.post(self.endpoint, json=payload, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    raise RuntimeError(f"Neuvi API returned {response.status}: {text}")
                else:
                    return io.BytesIO(await response.read())

    @commands.command(name="nimage", aliases=["ndraw", "ngenerate", "nimg", "n"])
    async def nimage(self, ctx: commands.Context, *, text: str):
        now = datetime.now(timezone.utc)
        user_id = ctx.author.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.COOLDOWN):
                return await ctx.reply(f"⏳ Please wait {config.COOLDOWN} seconds between requests.")
        self.bot.user_cooldowns[user_id] = now

        if self.ai_toggle_users.get(str(ctx.author.id)) and self.ai_toggle_users[str(ctx.author.id)]["toggle"] == False:
            return await ctx.reply("AI features are disabled for you.")
        
        prompt = text.strip()
        if not prompt:
            return await ctx.reply("❌ Please provide a prompt for nimage.")
        
        await ctx.message.add_reaction(self.loading_emoji)

        try:
            async with ctx.typing():
                result = await self._generate_image(prompt, user_id=str(ctx.author.id), name=ctx.author.name)
        except Exception as exc:
            await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
            return await ctx.reply(f"❌ Nimage request failed: {exc}")
        
        session = getattr(self.bot, "session", None)
        
        image_file = discord.File(result, filename="nimage.png")

        try:
            result.seek(0)
            async with session.post(self.nsfw_detetor_endpoint, data={"image": result}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    is_nsfw = data.get("is_nsfw", False)
                    if is_nsfw:
                        result.seek(0)
                        image_file = discord.File(result, filename="SPOILER_nimage.png", spoiler=True)
                        host_channel = self.bot.get_channel(self.nsfw_host_channel_id) or self.bot.get_channel(config.DEBUG_CHANNEL_ID)
                        if host_channel:
                            await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                            msg = await host_channel.send(
                                content=f"NSFW Image Log (Neuvi)\nPrompt: {prompt}\nUser: {ctx.author} ({ctx.author.id})",
                                file=image_file,
                                delete_after=300
                            )
                            url = msg.attachments[0].url
                            embed = discord.Embed(
                                title="⚠️ Image is NSFW",
                                description=f"Prompt: {prompt}\n\n**⚠️ This image is NSFW and may not be suitable for all audiences.\nYou can view it at [this link]({url}).**",
                                color=discord.Color.blurple()
                            )
                            return await ctx.reply(embed=embed)
                        
                        await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                        msg = await ctx.reply(file=image_file)
                        url = msg.attachments[0].url
                        embed = discord.Embed(
                            title="⚠️ Image is NSFW",
                            description=f"Prompt: {prompt}\n\n**⚠️ This image is NSFW and may not be suitable for all audiences.\nYou can view it at [this link]({url}).**",
                            color=discord.Color.blurple()
                        )
                        return await msg.edit(embed=embed, attachments=[])
        except Exception:
            pass

        result.seek(0)
        embed = discord.Embed(
            title="🎨🖌️ Here's your image:",
            description=f"Prompt: {prompt}",
            color=discord.Color.blurple()
        )
        embed.set_image(url="attachment://nimage.png")
        await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
        await ctx.reply(embed=embed, file=image_file)

    @discord.app_commands.command(name="nimage", description="Generate an image using the custom Neuvi API image service")
    @discord.app_commands.describe(prompt="The prompt to send to nimage")
    async def slash_nimage(
        self,
        interaction: discord.Interaction,
        prompt: str
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

        try:
            result = await self._generate_image(prompt, user_id=str(interaction.user.id), name=interaction.user.name)
        except Exception as exc:
            return await interaction.followup.send(f"❌ Nimage request failed: {exc}", ephemeral=True)

        result.seek(0)
        session = getattr(self.bot, "session", None)
        
        try:
            async with session.post(self.nsfw_detetor_endpoint, data={"image": result}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("is_nsfw", False):
                        result.seek(0)
                        image_file = discord.File(result, filename="SPOILER_nimage.png", spoiler=True)
                        host_channel = self.bot.get_channel(self.nsfw_host_channel_id) or self.bot.get_channel(config.DEBUG_CHANNEL_ID)
                        if host_channel:
                            msg = await host_channel.send(
                                content=f"NSFW Image Log (Slash Neuvi)\nPrompt: {prompt}\nUser: {interaction.user} ({interaction.user.id})",
                                file=image_file,
                                delete_after=300
                            )
                            url = msg.attachments[0].url
                            embed = discord.Embed(
                                title="⚠️ Image is NSFW",
                                description=f"Prompt: {prompt}\n\n**⚠️ This image is NSFW and may not be suitable for all audiences.\nYou can view it at [this link]({url}).**",
                                color=discord.Color.blurple()
                            )
                            return await interaction.followup.send(embed=embed)
                        
                        msg = await interaction.followup.send(file=image_file, wait=True)
                        url = msg.attachments[0].url
                        embed = discord.Embed(
                            title="⚠️ Image is NSFW",
                            description=f"Prompt: {prompt}\n\n**⚠️ This image is NSFW and may not be suitable for all audiences.\nYou can view it at [this link]({url}).**",
                            color=discord.Color.blurple()
                        )
                        return await interaction.followup.edit_message(msg.id, embed=embed, attachments=[])
        except Exception:
            pass

        result.seek(0)
        image_file = discord.File(result, filename="nimage.png")
        embed = discord.Embed(
            title="🎨🖌️ Here's your image:",
            description=f"Prompt: {prompt}",
            color=discord.Color.blurple()
        )
        embed.set_image(url="attachment://nimage.png")
        await interaction.followup.send(embed=embed, file=image_file)

async def setup(bot: commands.Bot):
    await bot.add_cog(NimageCommand(bot))
