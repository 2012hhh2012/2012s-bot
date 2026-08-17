import discord
from discord.ext import commands
from ..base import BaseCommand
import random

class AnimeWaifuCommand(BaseCommand):
    """Command to get random anime waifu images"""
    
    @property
    def command_name(self) -> str:
        return "anime-waifu"
    
    @property
    def description(self) -> str:
        return "Get a random anime waifu image"

    @commands.command(name="anime-waifu", aliases=["waifu"])
    async def anime_waifu(self, ctx):
        """Get a random anime waifu image"""
        await ctx.message.add_reaction(self.loading_emoji)
        
        session = getattr(self.bot, 'session', None)
        if not session:
            await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
            return await ctx.reply("❌ HTTP session not available.")
        
        if random.randint(1, 10) <= 3:
            api_url = "https://api.waifu.im/images?IsNsfw=False&IncludedTags=Waifu&ExcludedTags=Oppai&ExcludedTags=Hentai&ExcludedTags=Oral"
            api_type = "waifu.im"
        else:
            api_url = "https://api.nekosapi.com/v4/images/random?limit=1&rating=safe&tags=girl&without_tags=exposed_girl_breasts"
            api_type = "nekosapi"
        
        async with session.get(api_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                image_info = data["items"][0] if api_type == "waifu.im" else data[0]
                image_url = image_info["url"]
                tags = [tag["name"] for tag in image_info.get("tags", [])] if api_type == "waifu.im" else image_info["tags"]
                if tags:
                    tags = f"Tags: {', '.join(tags)}"
                else:
                    tags = "Tags: None specified by API."
                embed = discord.Embed(title="🐱 Here's a random anime waifu:")
                embed.set_image(url=image_url)
                embed.set_footer(text=f"Source: {image_info['source'] if api_type == 'waifu.im' else image_info['source_url']}\n{tags}")
                await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                await ctx.reply(embed=embed)
            else:
                await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                await ctx.reply(f"😿 Couldn't fetch an anime waifu right now... status: {resp.status}")

    @discord.app_commands.command(name="anime-waifu", description="Get a random anime waifu image")
    async def slash_anime_waifu(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        session = getattr(self.bot, 'session', None)
        if not session:
            return await interaction.followup.send("❌ HTTP session not available.")
        
        if random.randint(1, 10) <= 3:
            api_url = "https://api.waifu.im/images?IsNsfw=False"
            api_type = "waifu.im"
        else:
            api_url = "https://api.nekosapi.com/v4/images/random?limit=1&rating=safe&tags=girl&without_tags=exposed_girl_breasts"
            api_type = "nekosapi"
        
        async with session.get(api_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                image_info = data["items"][0] if api_type == "waifu.im" else data[0]
                image_url = image_info["url"]
                tags = [tag["name"] for tag in image_info.get("tags", [])] if api_type == "waifu.im" else image_info["tags"]
                if tags:
                    tags = f"Tags: {', '.join(tags)}"
                else:
                    tags = "Tags: None specified by API."
                embed = discord.Embed(title="🐱 Here's a random anime waifu:")
                embed.set_image(url=image_url)
                embed.set_footer(text=f"Source: {image_info['source'] if api_type == 'waifu.im' else image_info['source_url']}\n{tags}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"😿 Couldn't fetch an anime waifu right now... status: {resp.status}")

async def setup(bot):
    await bot.add_cog(AnimeWaifuCommand(bot))
