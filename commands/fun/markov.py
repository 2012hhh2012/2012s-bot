import discord
import logging
import markovify
from discord.ext import commands
from ..base import BaseCommand

logger = logging.getLogger("bot")

class Markov(BaseCommand):
    """
    Generate Markov chains from text
    """
    def __init__(self, bot):
        super().__init__(bot)
        with open("markov_model.json", "r", encoding="utf-8") as f:
            model_json = f.read()
        self.model = markovify.Text.from_json(model_json)
        logger.info("Markov model loaded.")

    property
    def command_name(self) -> str:
        return "markov"
    
    @property
    def description(self) -> str:
        return "Generate Markov chains from text"

    async def _generate(self, start_word = None, max_attempts = 100):
        """
        Generate a message. If start_word is given, try to start with that word.
        """
        if start_word:
            # Try to start with the given word
            for _ in range(max_attempts):
                try:
                    sentence = self.model.make_sentence_with_start(start_word, strict=False)
                    if sentence:
                        return sentence
                except Exception:
                    return f"No data for `{start_word}`."
        
        # Fallback: generate any random message
        sentence = self.model.make_sentence(tries=max_attempts)
        if sentence:
            return sentence
        
        return "I can't think of anything right now."

    @commands.command(name="markov", aliases=["m", "larp"])
    async def markov(self, ctx, *, start_word = None):
        message = await self._generate(start_word)
        await ctx.reply(message)

    @discord.app_commands.command(name="markov", description="Generate Markov chains from text")
    async def slash_markov(self, interaction: discord.Interaction, start_word: str = None):
        message = await self._generate(start_word)
        await interaction.response.send_message(message)

async def setup(bot):
    await bot.add_cog(Markov(bot))
