import discord
from discord.ext import commands
from ..base import BaseCommand

class UwuifyCommand(BaseCommand):
    """Command to uwuify text"""
    
    @property
    def command_name(self) -> str:
        return "uwuify"
    
    @property
    def description(self) -> str:
        return "Uwuify a message"

    @commands.command(name="uwuify", aliases=["uwu"])
    async def uwuify(self, ctx, *, text: str):
        """
        Uwuify a message

        Parameters
        ----------
        text : str
            The message to uwuify
        """
        if not text:
            await ctx.reply("Please provide a message to uwuify.")
            return

        session = getattr(self.bot, 'session', None)
        if not session:
            return await ctx.reply("❌ HTTP session not available.")

        async with session.post("https://uwu.pm/api/v1/uwu", json={"text": text}) as resp:
            if resp.status == 200:
                data = await resp.json()
                await ctx.reply(data["uwu"])
            else:
                await ctx.reply(f"😢 Couldn't uwuify right now... error: {resp.status}")

    @discord.app_commands.command(name="uwuify", description="Uwuify a message")
    @discord.app_commands.describe(text="The message to uwuify")
    async def slash_uwuify(self, interaction: discord.Interaction, text: str):
        if not text:
            return await interaction.response.send_message("Please provide a message to uwuify.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        session = getattr(self.bot, 'session', None)
        if not session:
            return await interaction.followup.send("❌ HTTP session not available.")

        async with session.post("https://uwu.pm/api/v1/uwu", json={"text": text}) as resp:
            if resp.status == 200:
                data = await resp.json()
                await interaction.followup.send(data["uwu"])
            else:
                await interaction.followup.send(f"😢 Couldn't uwuify right now... error: {resp.status}")

async def setup(bot):
    await bot.add_cog(UwuifyCommand(bot))
