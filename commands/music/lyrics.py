import discord
from discord.ext import commands
import lyricsgenius as lg
import os
import logging
from ..base import BaseCommand

class LyricsCommand(BaseCommand):
    """Lyrics command to fetch song lyrics"""
    
    def __init__(self, bot):
        super().__init__(bot)
        genius_token = os.getenv("GENIUS_ACCESS_TOKEN")
        # self.genius_api = lg.Genius( 
        #     genius_token, 
        #     remove_section_headers=False,
        #     verbose=False,
        #     timeout=10
        # )
        self.max_embed_chars = getattr(bot, 'max_embed_chars', 4000)
    
    @property
    def command_name(self) -> str:
        return "lyrics"
    
    @property
    def description(self) -> str:
        return "Get lyrics for a song"

    async def _get_thumbnail(self, session, track_name, artist_name):
        """Try Deezer first, fallback to iTunes for high-res thumbnails."""
        try:
            async with session.get("https://api.deezer.com/search", params={"q": f"{track_name} - {artist_name}"}, timeout=3.0) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        return data["data"][0]["album"]["cover_xl"]
        except:
            pass

        try:
            async with session.get("https://itunes.apple.com/search", params={"term": f"{track_name} - {artist_name}", "limit": 1, "entity": "song"}, timeout=3.0) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("resultCount", 0) > 0:
                        url = data["results"][0]["artworkUrl100"]
                        return url.replace("100x100bb", "1000x1000bb")
        except:
            pass
        return None
    
    @commands.is_owner()
    @commands.command(name="testlyrics", aliases=["testly", "tly"])
    async def test_lyrics(self, ctx, *, query: str):
        """
        Get the lyrics of a song

        Parameters
        ----------
        query : str
            The title of the song
        """
        ...

    @commands.command(name="lyrics", aliases=["ly"])
    async def lyrics(self, ctx, *, query: str = None):
        """
        Get the lyrics of a song

        Parameters
        ----------
        query : str, optional
            The title of the song. If omitted, uses the current playing track.
        """
        if query is None:
            player = ctx.voice_client
            if not player or not player.current:
                return await ctx.reply("Please provide a song title or play something first.")
            title = player.current.title
            artist = player.current.author
        else:
            title = query
            artist = None

        params = {"track_name": title, "artist_name": artist} if artist else {"q": title}

        session = getattr(self.bot, "session", None)
        if session is None:
            raise RuntimeError("HTTP session is not available on the bot.")
        
        async with ctx.typing():
            async with session.get("https://lrclib.net/api/search", params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    return await ctx.reply(f"LRCLib API returned {response.status}: {text}")
                
                data = await response.json()
                if not data:
                    return await ctx.reply(f"No lyrics found for **{query}**.")
                
                track = data[0]
                if track["instrumental"]:
                    return await ctx.reply("This song is instrumental.")

                lyrics = track["plainLyrics"]
                track_name = track["trackName"]
                artist_name = track["artistName"]

                thumbnail_url = await self._get_thumbnail(session, track_name, artist_name)

                chunks = self.split_message(lyrics)
                first_embed = discord.Embed(
                    title=f"🎵 Lyrics for **{track_name}** by **{artist_name}**",
                    description=chunks[0],
                    color=discord.Color.blurple()
                )
                if thumbnail_url:
                    first_embed.set_thumbnail(url=thumbnail_url)

                await ctx.reply(embed=first_embed)
                for chunk in chunks[1:]:
                    embed = discord.Embed(
                        description=chunk,
                        color=discord.Color.blurple()
                    )
                    await ctx.send(embed=embed)
                

    # @commands.command(name="lyrics", aliases=["ly"])
    async def old_lyrics(self, ctx, *, query: str):
        """
        Get the lyrics of a song

        Parameters
        ----------
        query : str
            The title of the song
        """
        await ctx.message.add_reaction(self.loading_emoji)
        initial_message = await ctx.send(f"🔍 Searching Genius for lyrics to **{query}**...")
        
        try:
            song = self.genius_api.search_song(query) 
            
            if not song:
                await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
                await initial_message.edit(content=f"❌ Could not find lyrics for **{query}**.")
                return
                
        except Exception as e:
            print(f"Genius API Error: {e}")
            await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
            await initial_message.edit(content="An error occurred while searching for the song.")
            return

        lyrics_text = song.lyrics
        title = f"🎵 Lyrics for **{song.title}** by **{song.artist}**"
        
        thumbnail_url = getattr(song, "song_art_image_thumbnail_url", None) or \
                        getattr(song, "album_art_thumbnail_url", None)
        
        if len(lyrics_text) <= self.max_embed_chars:
            embed = discord.Embed(
                title=title,
                description=lyrics_text,
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Full lyrics from Genius | {song.url}")
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
                
            await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
            await initial_message.edit(content=None, embed=embed)
            
        else:
            parts = []
            current_part = ""
            
            for line in lyrics_text.split("\n"):
                if len(current_part) + len(line) + 1 > self.max_embed_chars:
                    parts.append(current_part)
                    current_part = line + "\n"
                else:
                    current_part += line + "\n"
            if current_part:
                parts.append(current_part)
                
            first_embed = discord.Embed(
                title=title,
                description=parts[0],
                color=discord.Color.blurple()
            )
            first_embed.set_footer(text=f"Page 1 of {len(parts)} | Full lyrics from Genius")
            if thumbnail_url:
                first_embed.set_thumbnail(url=thumbnail_url)
            
            await ctx.message.remove_reaction(self.loading_emoji, self.bot.user)
            await initial_message.edit(content=None, embed=first_embed)
            
            for i, part in enumerate(parts[1:], 1):
                await ctx.send(f"**... (Page {i+1}/{len(parts)})**\n{part}")

    @discord.app_commands.command(name="lyrics", description="Get the lyrics of a song")
    @discord.app_commands.describe(
        title="The title of the song (optional if playing)",
        artist="The artist of the song (optional)"
    )
    async def slash_lyrics(self, interaction: discord.Interaction, title: str = None, artist: str = None):
        await interaction.response.defer(thinking=True)

        if title is None:
            player = interaction.guild.voice_client
            if not player or not player.current:
                return await interaction.followup.send("Please provide a song title or play something first.")
            title = player.current.title
            artist = player.current.author

        params = {"track_name": title, "artist_name": artist} if artist else {"q": title}

        session = getattr(self.bot, "session", None)
        if session is None:
            raise RuntimeError("HTTP session is not available on the bot.")
        
        async with session.get("https://lrclib.net/api/search", params=params) as response:
            if response.status != 200:
                text = await response.text()
                return await interaction.followup.send(f"LRCLib API returned {response.status}: {text}")
            
            data = await response.json()
            if not data:
                return await interaction.followup.send(f"No lyrics found for **{title}**.")
            
            track = data[0]
            if track["instrumental"]:
                return await interaction.followup.send("This song is instrumental.")

            lyrics = track["plainLyrics"]
            track_name = track["trackName"]
            artist_name = track["artistName"]

            thumbnail_url = await self._get_thumbnail(session, track_name, artist_name)

            chunks = self.split_message(lyrics)
            first_embed = discord.Embed(
                title=f"🎵 Lyrics for **{track_name}** by **{artist_name}**",
                description=chunks[0],
                color=discord.Color.blurple()
            )
            if thumbnail_url:
                first_embed.set_thumbnail(url=thumbnail_url)

            await interaction.followup.send(embed=first_embed)
            for chunk in chunks[1:]:
                embed = discord.Embed(
                    description=chunk,
                    color=discord.Color.blurple()
                )
                await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LyricsCommand(bot))
