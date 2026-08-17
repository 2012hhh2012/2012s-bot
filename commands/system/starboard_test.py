import discord
from discord.ext import commands
from discord.utils import get
from datetime import datetime
from ..base import BaseCommand

class StarboardTest(BaseCommand):
    """Starboard test"""
    def __init__(self, bot):
        super().__init__(bot)

    @property
    def command_name(self) -> str:
        return "starboard_test"
    
    @property
    def description(self) -> str:
        return "Test starboard"
    
    # Prefix command
    @commands.command(name="test-starboard")
    async def command_name(self, ctx):
        """Command implementation"""
        pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if str(payload.emoji) == "🫃":
            reaction = get(message.reactions, emoji=payload.emoji.name)
            if reaction:
                if reaction.count > 1:
                    star_channel = self.bot.get_channel(1447134750056906834) or await self.bot.fetch_channel(1447134750056906834)
                    author = message.author
                    display_name = author.display_name
                    avatar_url = author.avatar.url if author.avatar else author.default_avatar.url
                    message_url = message.jump_url
                    main_embed = discord.Embed(
                        description=message.content,
                        color=discord.Color.blurple(),
                        timestamp=message.created_at
                    )
                    main_embed.set_author(icon_url=avatar_url, name=display_name, url=message_url)

                    if message.attachments:
                        for attachment in message.attachments:
                            main_embed.set_image(url=attachment.url)

                    if message.reference:
                        reference = message.reference
                        replied_message = reference.cached_message
                        if replied_message is None:
                            try:
                                replied_message = await channel.fetch_message(reference.message_id)
                            except discord.NotFound:
                                replied_message = "Message not found"

                            if replied_message == "Message not found":
                                reply_embed = discord.Embed(
                                    title="Replying to a deleted message"
                                )
                            else:
                                replied_author = replied_message.author
                                replied_display_name = replied_author.display_name
                                replied_avatar_url = replied_author.avatar.url if replied_author.avatar else replied_author.default_avatar.url
                                replied_message_url = replied_message.jump_url
                                reply_embed = discord.Embed(
                                    description=replied_message.content,
                                    timestamp=replied_message.created_at
                                )
                                reply_embed.set_author(icon_url=replied_avatar_url, name=f"Replying to {replied_display_name}", url=replied_message_url)

                                if replied_message.attachments:
                                    for attachment in message.attachments:
                                        reply_embed.set_image(url=attachment.url)

                            await star_channel.send(f"{payload.emoji} **{reaction.count} |** {message_url}", embeds=[reply_embed, main_embed])
                            return
                    
                    await star_channel.send(f"{payload.emoji} **{reaction.count} |** {message_url}", embed=main_embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.author.id == 1381369353970389142 and message.guild.id == 1415305792768442481:
            await message.add_reaction("🫃")

async def setup(bot):
    await bot.add_cog(StarboardTest(bot))