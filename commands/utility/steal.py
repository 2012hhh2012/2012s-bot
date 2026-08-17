import discord
from discord.ext import commands
from ..base import BaseCommand

class StealCommand(BaseCommand):
    """Command to get emoji information and download links"""
    
    @property
    def command_name(self) -> str:
        return "steal"
    
    @property
    def description(self) -> str:
        return "Get download link and info for custom emojis"

    @commands.command(name="steal")
    async def steal(self, ctx, emoji: str):
        """
        Provides the direct download link and info for a custom emoji.
        
        Parameters
        ----------
        emoji : str
            The custom emoji to get the info for
        """
        # 1. regex to extract animated status, name, and ID
        # pattern: ^< - start; (a)? - optional 'a' (animated); :([a-zA-Z0-9_]+): - name; (\d+) - ID; >$ - end
        if not (emoji.startswith('<') and emoji.endswith('>')):
            return await ctx.reply("❌ Please provide a **custom emoji**, standard emojis (like 🙂) don't have a file to download.")

        # 2. determine animated status and clean the string
        is_animated = emoji.startswith('<a:')
        
        # remove the surrounding brackets
        clean_emoji = emoji.strip('<>')

        # determine what to strip from the front based on animated status
        if is_animated:
            # animated: strip '<a:' and '>'
            content = clean_emoji[2:] 
        else:
            # static: strip '<:' and '>'
            content = clean_emoji[1:]
            
        # the content is now in the format 'name:id'
        
        try:
            # 3. split the remaining string into name and ID
            # splits 'name:id' into ['name', 'id']
            emoji_name, emoji_id = content.split(':')
        except ValueError:
            # this handles malformed strings that aren't 'name:id'
            return await ctx.reply("❌ That doesn't look like a valid custom emoji format. Make sure it was sent correctly.")
        
        # determine the file extension and type
        file_extension = "gif" if is_animated else "png"
        file_type = "Animated GIF" if is_animated else "Static PNG"
        
        # construct the direct download URL from Discord's CDN
        download_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{file_extension}"
        
        # 3. create a descriptive message using an embed
        embed = discord.Embed(
            title=f"Emoji Information: :{emoji_name}:",
            description="Here are the details for you to download and upload this emoji.",
            color=discord.Color.blurple()
        )
        
        embed.add_field(name="Name", value=f"`{emoji_name}`", inline=True)
        embed.add_field(name="File Type", value=file_type, inline=True)
        embed.add_field(name="URL", value=download_url, inline=False)
        
        # set the thumbnail to the emoji image itself
        embed.set_thumbnail(url=download_url)
        embed.set_footer(text=f"ID: {emoji_id}")

        await ctx.send(embed=embed)

    @discord.app_commands.command(name="steal", description="Get download link and info for custom emojis")
    @discord.app_commands.describe(emoji="The custom emoji to get info for")
    async def slash_steal(self, interaction: discord.Interaction, emoji: str, ephemeral: bool = True):
        if not (emoji.startswith('<') and emoji.endswith('>')):
            return await interaction.response.send_message("❌ Please provide a **custom emoji**, standard emojis (like 🙂) don't have a file to download.", ephemeral=True)

        is_animated = emoji.startswith('<a:')
        clean_emoji = emoji.strip('<>')

        if is_animated:
            content = clean_emoji[2:] 
        else:
            content = clean_emoji[1:]
            
        try:
            emoji_name, emoji_id = content.split(':')
        except ValueError:
            return await interaction.response.send_message("❌ That doesn't look like a valid custom emoji format. Make sure it was sent correctly.", ephemeral=True)
        
        file_extension = "gif" if is_animated else "png"
        file_type = "Animated GIF" if is_animated else "Static PNG"
        download_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{file_extension}"
        
        embed = discord.Embed(
            title=f"Emoji Information: :{emoji_name}:",
            description="Here are the details for you to download and upload this emoji.",
            color=discord.Color.blurple()
        )
        
        embed.add_field(name="Name", value=f"`{emoji_name}`", inline=True)
        embed.add_field(name="File Type", value=file_type, inline=True)
        embed.add_field(name="URL", value=download_url, inline=False)
        
        embed.set_thumbnail(url=download_url)
        embed.set_footer(text=f"ID: {emoji_id}")

        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

async def setup(bot):
    await bot.add_cog(StealCommand(bot))
