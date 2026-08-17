import discord
from discord.ext import commands
from urllib.parse import urlencode
from ..base import BaseCommand

import io
from typing import Union

class EjectCommand(BaseCommand):
    """Command to eject users Among Us style"""
    
    @property
    def command_name(self) -> str:
        return "eject"
    
    @property
    def description(self) -> str:
        return "Eject a user Among Us style"

    async def _eject_user(self, ctx_or_interaction: Union[commands.Context, discord.Interaction], target: discord.Member, imposter: bool):
        """
        Shared logic to handle the API call and image generation 
        for both Text commands, Slash commands, and Context Menus.
        """
        
        # Determine if this is an interaction or a text context
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
        
        if not is_interaction:
            try:
                await ctx_or_interaction.message.add_reaction(self.loading_emoji)
            except:
                pass
        else:
            if not ctx_or_interaction.response.is_done():
                await ctx_or_interaction.response.defer(thinking=True)

        session = getattr(self.bot, 'session', None)
        if not session:
            msg = "❌ HTTP session not available."
            if is_interaction:
                return await ctx_or_interaction.followup.send(msg)
            else:
                return await ctx_or_interaction.reply(msg)

        # Construct parameters (keys restored from eject.py)
        params = {
            "avatar": str(target.display_avatar.url),
            "username": target.display_name,
            "imposter": str(imposter).lower() # converts True/False to "true"/"false"
        }

        try:
            async with session.get("https://api.some-random-api.com/premium/amongus", params=params) as resp:
                if resp.status == 200:
                    data = io.BytesIO(await resp.read())
                    file = discord.File(data, "eject.gif")
                    embed = discord.Embed(
                        title=f"**{target.display_name}** has been ejected!",
                        color=discord.Color.blurple()
                    )
                    embed.set_image(url="attachment://eject.gif")
                    
                    if is_interaction:
                        await ctx_or_interaction.followup.send(embed=embed, file=file)
                    else:
                        try:
                            await ctx_or_interaction.message.remove_reaction(self.loading_emoji, self.bot.user)
                        except:
                            pass
                        await ctx_or_interaction.reply(embed=embed, file=file)
                else:
                    error_msg = f"API Error {resp.status}"
                    try:
                        error_data = await resp.json()
                        error_msg = error_data.get('error', error_msg)
                    except:
                        pass
                    
                    final_msg = f"😢 Couldn't fetch the ejection image... Error: {error_msg}"
                    if is_interaction:
                        await ctx_or_interaction.followup.send(final_msg)
                    else:
                        try:
                            await ctx_or_interaction.message.remove_reaction(self.loading_emoji, self.bot.user)
                        except:
                            pass
                        await ctx_or_interaction.reply(final_msg)
        except Exception as e:
            final_msg = f"❌ An error occurred: {str(e)}"
            if is_interaction:
                await ctx_or_interaction.followup.send(final_msg)
            else:
                await ctx_or_interaction.reply(final_msg)

    @commands.command(name="eject", aliases=["amongus"])
    async def eject(self, ctx, target: discord.Member, imposter: bool = False):
        """
        Eject a user Among Us style

        Parameters
        ----------
        target : discord.Member
            The member to eject
        imposter : bool, optional
            Whether the target is an impostor
        """
        await self._eject_user(ctx, target, imposter)

    @discord.app_commands.command(name="eject", description="Eject a user Among Us style")
    @discord.app_commands.describe(
        target="The member to eject",
        imposter="Whether the target is an impostor"
    )
    async def slash_eject(self, interaction: discord.Interaction, target: discord.Member, imposter: bool = False):
        await self._eject_user(interaction, target, imposter)

# Context Menu Commands (Right Click -> Apps)
@discord.app_commands.context_menu(name="Eject imposter")
async def context_eject_imposter(interaction: discord.Interaction, target: discord.Member):
    cog = interaction.client.get_cog("EjectCommand")
    if cog:
        await cog._eject_user(interaction, target, True)
    else:
        await interaction.response.send_message("❌ EjectCommand cog not found.", ephemeral=True)

@discord.app_commands.context_menu(name="Eject crewmate")
async def context_eject_crewmate(interaction: discord.Interaction, target: discord.Member):
    cog = interaction.client.get_cog("EjectCommand")
    if cog:
        await cog._eject_user(interaction, target, False)
    else:
        await interaction.response.send_message("❌ EjectCommand cog not found.", ephemeral=True)

async def setup(bot):
    cog = EjectCommand(bot)
    await bot.add_cog(cog)
    # Register context menus
    bot.tree.add_command(context_eject_imposter)
    bot.tree.add_command(context_eject_crewmate)