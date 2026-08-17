import discord
from discord.ext import commands
from typing import Literal
from ..base import BaseCommand

class DareCommand(BaseCommand):
    """Command to get dare challenges"""
    
    @property
    def command_name(self) -> str:
        return "dare"
    
    @property
    def description(self) -> str:
        return "Get a dare challenge"

    @commands.command(name="dare")
    async def dare(self, ctx, rating: Literal['PG', 'PG13', 'R'] = None):
        """
        Get a dare
        
        Parameters
        ----------
        rating : Literal['PG', 'PG13', 'R'], optional
            The rating of the question (optional) (PG, PG13, R)
        """
        await ctx.message.add_reaction(self.loading_emoji)
        
        session = getattr(self.bot, 'session', None)
        if not session:
            await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
            return await ctx.reply("❌ HTTP session not available.")
        
        async with session.get(f"https://api.truthordarebot.xyz/v1/dare{f'?rating={rating}' if rating else '' }") as resp:
            if resp.status == 200:
                data = await resp.json()

                question_text = data["question"]
                type_val = data["type"]
                rating_val = data["rating"]
                id_val = data["id"]

                embed = discord.Embed(
                    title=f"**{question_text}**",
                    color=discord.Color.blurple(),
                )
                embed.set_author(icon_url=ctx.author.display_avatar.url, name=f"Requested by {ctx.author.display_name}")

                embed.set_footer(text=f"Type: {type_val} | Rating: {rating_val} | ID: {id_val}")
                await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                await ctx.reply(embed=embed)
            else:
                await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                await ctx.reply(f"😢 Couldn't fetch a dare right now... error: {resp.status}")

    @discord.app_commands.command(name="dare", description="Get a dare challenge")
    @discord.app_commands.describe(rating="The rating of the challenge (PG, PG13, R)")
    async def slash_dare(self, interaction: discord.Interaction, rating: Literal['PG', 'PG13', 'R'] = None):
        await interaction.response.defer(thinking=True)
        
        session = getattr(self.bot, 'session', None)
        if not session:
            return await interaction.followup.send("❌ HTTP session not available.")
        
        async with session.get(f"https://api.truthordarebot.xyz/v1/dare{f'?rating={rating}' if rating else '' }") as resp:
            if resp.status == 200:
                data = await resp.json()

                question_text = data["question"]
                type_val = data["type"]
                rating_val = data["rating"]
                id_val = data["id"]

                embed = discord.Embed(
                    title=f"**{question_text}**",
                    color=discord.Color.blurple(),
                )
                embed.set_author(icon_url=interaction.user.display_avatar.url, name=f"Requested by {interaction.user.display_name}")

                embed.set_footer(text=f"Type: {type_val} | Rating: {rating_val} | ID: {id_val}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"😢 Couldn't fetch a dare right now... error: {resp.status}")

async def setup(bot):
    await bot.add_cog(DareCommand(bot))
