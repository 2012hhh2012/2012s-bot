import asyncio
import discord
from discord.ext import commands
from abc import abstractmethod


class BaseCommand(commands.Cog):
    """Base class for all command cogs"""

    def __init__(self, bot):
        self.bot = bot
        self.loading_emoji = "<a:loading3:1426096957427814480>"
        self.max_file_size = getattr(bot, "max_file_size", 20 * 1024 * 1024)
        self.max_message_length = getattr(bot, "max_message_length", 1990)

    @property
    @abstractmethod
    def command_name(self) -> str:
        """The name of this command"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this command does"""
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def split_message(self, text: str, limit: int | None = None) -> list[str]:
        """Split a long message into Discord-friendly chunks."""
        if limit is None:
            limit = self.max_message_length

        chunks: list[str] = []
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
                in_codeblock = False

        if text:
            if in_codeblock and not text.rstrip().endswith("```"):
                text += "\n```"
            chunks.append(text)

        return chunks

    async def ensure_file_size(self, attachment: discord.Attachment) -> bool:
        """Check if attachment size is within allowed limits."""
        if attachment.size > self.max_file_size:
            max_mb = self.max_file_size // (1024 * 1024)
            if hasattr(attachment, "message") and attachment.message:
                await attachment.message.reply(
                    f"❌ File **{attachment.filename}** is too large. Please keep files under {max_mb}MB."
                )
            return False
        return True

    async def run_in_thread(self, func, *args, **kwargs):
        """Convenience wrapper around asyncio.to_thread."""
        return await asyncio.to_thread(func, *args, **kwargs)
