import discord
from discord.ext import commands
from typing import Optional
import io
import shlex
import random
from datetime import datetime, timezone, timedelta

from ..base import BaseCommand
from config import config

class ZimageCommand(BaseCommand):
    """Command for interacting with the pollinations zimage service."""

    def __init__(self, bot: commands.Bot):
        self.ai_semaphore = bot.ai_semaphore
        self.user_cooldowns = bot.user_cooldowns
        super().__init__(bot)
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        self.api_key = config.POLLINATIONS_API_KEY
        self.endpoint = "https://gen.pollinations.ai/image/"
        self.nsfw_detetor_endpoint = "https://2012hhh2012-nsfw-detector.hf.space/detect"
        self.nsfw_host_channel_id = 1461381591019425853

    @property
    def command_name(self) -> str:
        return "zimage"

    @property
    def description(self) -> str:
        return "Generate a image using the pollinations zimage service"

    async def _generate_image(
            self,
            prompt: str,
            width: int = 1024,
            height: int = 1024,
            seed: Optional[int] = None,
            negative_prompt: Optional[str] = "worst quality, blurry"
        ) -> tuple[Optional[io.BytesIO], int]:
        session = getattr(self.bot, "session", None)
        if session is None:
            raise RuntimeError("HTTP session is not available on the bot.")

        params = {
            "model": "zimage",
            "safe": "true",
            "width": width,
            "height": height,
            "negative_prompt": negative_prompt
        }

        if seed is None or seed <= 0:
            seed = random.randint(0, 2**31 - 1)
        
        params["seed"] = seed

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        async with self.ai_semaphore:
            async with session.get(self.endpoint + prompt, params=params, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    raise RuntimeError(f"Pollinations API returned {response.status}: {text}")
                else:
                    return io.BytesIO(await response.read()), seed


    @commands.command(name="zimage", aliases=["zdraw", "zgenerate", "zimg", "z"])
    async def zimage(self, ctx: commands.Context, *, text: str):
        """Generate a stateless zimage response."""
        now = datetime.now(timezone.utc)
        user_id = ctx.author.id
        if user_id in self.bot.user_cooldowns:
            last_used = self.bot.user_cooldowns[user_id]
            if now - last_used < timedelta(seconds=config.COOLDOWN):
                return await ctx.reply(f"⏳ Please wait {config.COOLDOWN} seconds between requests.")
        self.bot.user_cooldowns[user_id] = now

        if self.ai_toggle_users.get(str(ctx.author.id)) and self.ai_toggle_users[str(ctx.author.id)]["toggle"] == False:
            return await ctx.reply("AI features are disabled for you.")
        
        # Parse the text for prompt and flags
        parts = shlex.split(text)
        prompt_parts = []
        width = 1024
        height = 1024
        seed = None
        i = 0
        while i < len(parts):
            if parts[i] == '--width':
                i += 1
                if i < len(parts):
                    try:
                        width = int(parts[i])
                    except ValueError:
                        pass  # ignore invalid
            elif parts[i] == '--height':
                i += 1
                if i < len(parts):
                    try:
                        height = int(parts[i])
                    except ValueError:
                        pass
            elif parts[i] == '--seed':
                i += 1
                if i < len(parts):
                    try:
                        seed = int(parts[i])
                    except ValueError:
                        pass
            else:
                prompt_parts.append(parts[i])
            i += 1
        
        prompt = ' '.join(prompt_parts).strip()
        if not prompt:
            return await ctx.reply("❌ Please provide a prompt for zimage.")
        
        if width > 4096 or height > 4096:
            return await ctx.reply("❌ Width and height must be less than or equal to 4096.")

        await ctx.message.add_reaction(self.loading_emoji)

        try:
            async with ctx.typing():
                result, used_seed = await self._generate_image(prompt, width, height, seed)
        except Exception as exc:  # pylint: disable=broad-except
            await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
            return await ctx.reply(f"❌ Zimage request failed: {exc}")
        
        session = getattr(self.bot, "session", None)
        
        image_file = discord.File(result, filename="zimage.png")

        async with session.post(self.nsfw_detetor_endpoint, data={"image": result}) as resp:
            if resp.status != 200:
                await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                return await ctx.reply(f"❌ NSFW detector API returned {resp.status}: {await resp.text()}")
            else:
                data = await resp.json()
                is_nsfw = data["is_nsfw"]
                if is_nsfw:
                    result.seek(0)
                    image_file = discord.File(result, filename="SPOILER_zimage.png", spoiler=True)
                    # Try to host the image in the specific NSFW host channel
                    host_channel = self.bot.get_channel(self.nsfw_host_channel_id) or self.bot.get_channel(config.DEBUG_CHANNEL_ID)
                    if host_channel:
                        await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                        msg = await host_channel.send(
                            content=f"NSFW Image Log\nPrompt: {prompt}\nUser: {ctx.author} ({ctx.author.id})",
                            file=image_file,
                            delete_after=300
                        )
                        url = msg.attachments[0].url
                        embed = discord.Embed(
                            title="⚠️ Image is NSFW",
                            description=f"Prompt: {prompt}\n\n**⚠️ This image is NSFW and may not be suitable for all audiences.\nYou can view it at [this link]({url}).**",
                            color=discord.Color.blurple()
                        )
                        embed.set_footer(text=f"Seed: {used_seed}")
                        return await ctx.reply(embed=embed)
                    
                    # Fallback if no host channel: Send/Edit method
                    await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                    msg = await ctx.reply(file=image_file)
                    url = msg.attachments[0].url
                    embed = discord.Embed(
                        title="⚠️ Image is NSFW",
                        description=f"Prompt: {prompt}\n\n**⚠️ This image is NSFW and may not be suitable for all audiences.\nYou can view it at [this link]({url}).**",
                        color=discord.Color.blurple()
                    )
                    embed.set_footer(text=f"Seed: {used_seed}")
                    return await msg.edit(embed=embed, attachments=[])
        
        result.seek(0)
        embed = discord.Embed(
            title="🎨🖌️ Here's your image:",
            description=f"Prompt: {prompt}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Seed: {used_seed}")
        embed.set_image(url="attachment://zimage.png")
        await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
        await ctx.reply(embed=embed, file=image_file)

    @discord.app_commands.command(name="zimage", description="Generate a response using the pollinations zimage service")
    @discord.app_commands.describe(prompt="The prompt to send to zimage", width="The width of the image", height="The height of the image")
    async def slash_zimage(
        self,
        interaction: discord.Interaction,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = "worst quality, blurry"
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
        
        if width > 4096 or height > 4096:
            return await interaction.response.send_message("❌ Width and height must be less than or equal to 4096.", ephemeral=True)
        
        await interaction.response.defer(thinking=True)

        try:
            result, used_seed = await self._generate_image(prompt, width, height, seed, negative_prompt)
        except Exception as exc:  # pylint: disable=broad-except
            return await interaction.followup.send(f"❌ Zimage request failed: {exc}", ephemeral=True)

        negative_prompt = None if negative_prompt == "worst quality, blurry" else negative_prompt
        
        result.seek(0)
        session = getattr(self.bot, "session", None)
        if session is None:
            raise RuntimeError("HTTP session is not available on the bot.")
        
        async with session.post(self.nsfw_detetor_endpoint, data={"image": result}) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data["is_nsfw"]:
                    result.seek(0)
                    image_file = discord.File(result, filename="SPOILER_zimage.png", spoiler=True)
                    
                    # Try to host the image in the specific NSFW host channel
                    host_channel = self.bot.get_channel(self.nsfw_host_channel_id) or self.bot.get_channel(config.DEBUG_CHANNEL_ID)
                    if host_channel:
                        msg = await host_channel.send(
                            content=f"NSFW Image Log (Slash)\nPrompt: {prompt}{f'\nNegative prompt: {negative_prompt}' if negative_prompt else ''}\nUser: {interaction.user} ({interaction.user.id})",
                            file=image_file,
                            delete_after=300
                        )
                        url = msg.attachments[0].url
                        embed = discord.Embed(
                            title="⚠️ Image is NSFW",
                            description=f"Prompt: {prompt}{f'\nNegative prompt: {negative_prompt}' if negative_prompt else ''}\n\n**⚠️ This image is NSFW and may not be suitable for all audiences.\nYou can view it at [this link]({url}).**",
                            color=discord.Color.blurple()
                        )
                        embed.set_footer(text=f"Seed: {used_seed}")
                        return await interaction.followup.send(embed=embed)
                    
                    # Fallback if no host channel: Send/Edit method
                    msg = await interaction.followup.send(file=image_file, wait=True)
                    url = msg.attachments[0].url
                    embed = discord.Embed(
                        title="⚠️ Image is NSFW",
                        description=f"Prompt: {prompt}{f'\nNegative prompt: {negative_prompt}' if negative_prompt else ''}\n\n**⚠️ This image is NSFW and may not be suitable for all audiences.\nYou can view it at [this link]({url}).**",
                        color=discord.Color.blurple()
                    )
                    embed.set_footer(text=f"Seed: {used_seed}")
                    return await interaction.followup.edit_message(msg.id, embed=embed, attachments=[])
            else:
                return await interaction.followup.send(f"❌ NSFW detector API returned {resp.status}: {await resp.text()}", ephemeral=True)

        result.seek(0)
        image_file = discord.File(result, filename="zimage.png")
        embed = discord.Embed(
            title="🎨🖌️ Here's your image:",
            description=f"Prompt: {prompt}{f'\nNegative prompt: {negative_prompt}' if negative_prompt else ''}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Seed: {used_seed}")
        embed.set_image(url="attachment://zimage.png")
        await interaction.followup.send(embed=embed, file=image_file)


async def setup(bot: commands.Bot):
    await bot.add_cog(ZimageCommand(bot))
