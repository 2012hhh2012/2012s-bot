import discord
from discord.ext import commands
from ..base import BaseCommand

from config import config
import io

class IsNsfwCommand(BaseCommand):
    """Check if an image is NSFW"""

    def __init__(self, bot):
        super().__init__(bot)
        self.ai_toggle_users = getattr(bot, 'ai_toggle_users', {})
        self.endpoint = "https://2012hhh2012-nsfw-detector.hf.space/detect"
    
    @property
    def command_name(self) -> str:
        return "is_nsfw"
    
    @property
    def description(self) -> str:
        return "Check if an image is NSFW"
    
    async def check_nsfw(self, image_url: str = None, image: discord.Attachment = None) -> bool:
        session = getattr(self.bot, "session", None)
        if session is None:
            raise RuntimeError("HTTP session is not available on the bot.")
        
        if image_url:
            async with session.get(self.endpoint, params={"image_url": image_url}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["is_nsfw"]
                else:
                    raise RuntimeError(f"NSFW detector API returned {resp.status}: {await resp.text()}")
        elif image:
            image_bytes = await image.read()
            image = io.BytesIO(image_bytes)
            async with session.post(self.endpoint, data={"image": image}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["is_nsfw"]
                else:
                    raise RuntimeError(f"NSFW detector API returned {resp.status}: {await resp.text()}")
        else:
            return False
    
    # Prefix command
    @commands.command(name="is-nsfw", aliases=["nsfw", "isnsfw", "is_nsfw"])
    async def is_nsfw(self, ctx, image_url: str = None):
        """Check if an image is NSFW"""
        if self.ai_toggle_users.get(str(ctx.author.id)) and self.ai_toggle_users[str(ctx.author.id)]["toggle"] == False:
            return await ctx.reply("AI features are disabled for you.", ephemeral=True)

        try:
            async with ctx.typing():
                if image_url:
                    is_nsfw = await self.check_nsfw(image_url=image_url)
                elif ctx.message.attachments:
                    is_nsfw = await self.check_nsfw(image=ctx.message.attachments[0])
                else:
                    return await ctx.reply("Please provide an image URL or attach an image to the message.")
                
                await ctx.reply(f"The image is {'not ' if not is_nsfw else ''}NSFW.")

        except Exception as e:
            await ctx.reply(f"❌ Error: {str(e)}")    

    # Slash command
    @discord.app_commands.command(name="is_nsfw", description="Check if an image is NSFW")
    async def slash_is_nsfw(self, interaction: discord.Interaction, image_url: str = None, image: discord.Attachment = None):
        if self.ai_toggle_users.get(str(interaction.user.id)) and self.ai_toggle_users[str(interaction.user.id)]["toggle"] == False:
            return await interaction.response.send_message("AI features are disabled for you.", ephemeral=True)
        
        await interaction.response.defer(thinking=True)

        try:
            if image_url:
                is_nsfw = await self.check_nsfw(image_url=image_url)
            elif image:
                is_nsfw = await self.check_nsfw(image=image)
            else:
                return await interaction.followup.send("Please provide an image URL or attach an image to the message.", ephemeral=True)
            
            await interaction.followup.send(f"The image is {'not ' if not is_nsfw else ''}NSFW.")

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")

async def setup(bot):
    await bot.add_cog(IsNsfwCommand(bot))