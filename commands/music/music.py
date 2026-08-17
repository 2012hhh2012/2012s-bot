import discord
import asyncio
import mafic
import aiohttp
import os
import logging
import re
import difflib
import time
from discord.ext import commands
from ..base import BaseCommand

logger = logging.getLogger("bot")

LAVA_HOST = os.getenv("LAVALINK_HOST", "lunar.voidhosting.vip")
LAVA_PORT = int(os.getenv("LAVALINK_PORT", "9087"))
LAVA_PASS = os.getenv("LAVALINK_PASSWORD", "2012hhh2012_secure_password_here")
LAVA_SECURE = os.getenv("LAVALINK_SECURE", "false").lower() == "true"

_YT_THUMB_HOSTS = ("ytimg.com", "img.youtube.com", "i9.ytimg.com")
_URL_RE = re.compile(r"^https?://\S+$|^www\.\S+$")

def _format_duration(ms: int | None) -> str:
    if not ms: return "Live"
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

class QueuedTrack:
    def __init__(self, track: mafic.Track, requester: discord.Member | str):
        self.track = track
        self.requester = requester

    def __getattr__(self, name):
        return getattr(self.track, name)


def _is_valid_artwork(url: str | None, allow_yt: bool = False) -> bool:
    if not url: return False
    if "1x1" in url: return False
    if not allow_yt:
        for host in _YT_THUMB_HOSTS:
            if host in url: return False
    return True

async def _itunes_artwork(session: aiohttp.ClientSession, query: str) -> str | None:
    try:
        async with session.get(
            "https://itunes.apple.com/search",
            params={"term": query, "entity": "song", "limit": 1},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as r:
            if r.status != 200: return None
            data = await r.json(content_type=None)
            if not data.get("resultCount"): return None
            art = data["results"][0].get("artworkUrl100", "")
            return art.replace("100x100bb", "600x600bb").replace("100x100", "600x600") if art else None
    except Exception:
        return None

def _build_player_view(
    cog: "MusicCommand",
    player: "MaficPlayer",
    track: mafic.Track,
    requester: discord.Member | str,
    artwork_url: str | None,
) -> discord.ui.LayoutView:
    layout = discord.ui.LayoutView(timeout=None)
    container = discord.ui.Container()

    container.add_item(discord.ui.TextDisplay("## Now Playing"))
    container.add_item(discord.ui.Separator())

    duration_str = _format_duration(track.length) if track.length else "Live"

    if artwork_url:
        section = discord.ui.Section(accessory=discord.ui.Thumbnail(media=artwork_url))
        section.add_item(discord.ui.TextDisplay(f"**{track.title}**"))
        section.add_item(discord.ui.TextDisplay(f"*{track.author}*"))
        section.add_item(discord.ui.TextDisplay(f"`{duration_str}`"))
        container.add_item(section)
    else:
        container.add_item(discord.ui.TextDisplay(f"**{track.title}**"))
        container.add_item(discord.ui.TextDisplay(f"*{track.author}*   `{duration_str}`"))

    container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))

    next_track = player.queue[0] if len(player.queue) > 0 else None

    if isinstance(requester, str):
        meta = f"Added by **{requester}**"
    else:
        meta = f"Added by {requester.mention}"
    if next_track:
        meta += f"  ·  Next: **{next_track.title}**"
    container.add_item(discord.ui.TextDisplay(meta))

    container.add_item(discord.ui.Separator())

    mode = player.loop_mode
    if mode == "track": loop_label = "Loop: Track"
    elif mode == "queue": loop_label = "Loop: Queue"
    else: loop_label = "Loop: Off"

    is_paused = player.paused
    pause_label = "Resume" if is_paused else "Pause"
    pause_style = discord.ButtonStyle.success if is_paused else discord.ButtonStyle.primary

    row = discord.ui.ActionRow(
        discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="music_prev"),
        discord.ui.Button(label=pause_label, style=pause_style, custom_id="music_pause"),
        discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary, custom_id="music_skip"),
        discord.ui.Button(label=loop_label, style=discord.ButtonStyle.secondary, custom_id="music_loop"),
        discord.ui.Button(label="Stop", style=discord.ButtonStyle.danger, custom_id="music_stop"),
    )
    row.children[0].callback = cog._btn_previous
    row.children[1].callback = cog._btn_pause
    row.children[2].callback = cog._btn_skip
    row.children[3].callback = cog._btn_loop
    row.children[4].callback = cog._btn_stop

    container.add_item(row)
    layout.add_item(container)
    return layout

def _build_queue_view(player: "MaficPlayer", page: int = 0) -> discord.ui.LayoutView:
    layout = discord.ui.LayoutView(timeout=60)
    container = discord.ui.Container()

    container.add_item(discord.ui.TextDisplay("## Queue"))
    container.add_item(discord.ui.Separator())

    tracks = list(player.queue)
    if not tracks:
        container.add_item(discord.ui.TextDisplay("The queue is empty."))
        layout.add_item(container)
        return layout

    per_page = 10
    total_pages = max(1, (len(tracks) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = tracks[page * per_page : (page + 1) * per_page]
    start_idx = page * per_page

    lines = []
    for i, t in enumerate(chunk, start=start_idx + 1):
        req = t.requester.name if isinstance(t.requester, discord.Member) else t.requester
        lines.append(f"`{i}.` **{t.title}** — *{t.author}*  ·  `{req}`")
    container.add_item(discord.ui.TextDisplay("\n".join(lines)))

    container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
    container.add_item(discord.ui.TextDisplay(f"Page {page + 1} of {total_pages}  ·  {len(tracks)} tracks"))

    layout.add_item(container)
    return layout

class _SearchSelectView(discord.ui.LayoutView):
    def __init__(self, cog: "MusicCommand", ctx: commands.Context, tracks: list[mafic.Track], query: str):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.tracks = tracks
        self._query = query

        options = [
            discord.SelectOption(
                label=t.title[:100],
                description=f"{t.author} · {_format_duration(t.length)}"[:100],
                value=str(i),
            )
            for i, t in enumerate(tracks[:10])
        ]

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("## Search Results"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("Select a track to add to the queue."))

        row = discord.ui.ActionRow(
            discord.ui.Select(
                placeholder="Choose a track...",
                options=options,
                custom_id="music_search_select",
            )
        )
        row.children[0].callback = self._on_select
        container.add_item(row)
        self.add_item(container)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Only the requester can pick a track.", ephemeral=True)
            return
        idx = int(interaction.data["values"][0])
        track = self.tracks[idx]
        await interaction.response.defer()
        await self.cog._enqueue_and_play(self.ctx, track, interaction.message, query_str=self._query)

class MaficPlayer(mafic.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue: list[QueuedTrack] = []
        self.history: list[QueuedTrack] = []
        self.loop_mode: str = "none" # none, track, queue
        self._text_channel_id: int | None = None
        self.autoplay = False
        self.always_on = False
        self.skipping = False
        self.autoplay_history: list[str] = []
        self.current_requester: discord.Member | str | None = None

class MusicCommand(BaseCommand):
    def __init__(self, bot):
        super().__init__(bot)
        self._np_messages: dict[int, discord.Message] = {}
        self._np_artworks: dict[int, str | None] = {}
        self._np_locks: dict[int, asyncio.Lock] = {}
        self._last_track_id: dict[int, tuple[str, float]] = {}
        self.session: aiohttp.ClientSession | None = None
        
        # NOTE: mafic.NodePool is the official name instead of mafic.Pool
        self.pool = mafic.NodePool(bot) 
        logger.info(f"MusicCommand initialized with Mafic. Registered commands: {[c.name for c in self.get_commands()]}")
    
    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        await ctx.reply(f"⚠️ Music Error: {error}")

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        # Schedule the connection as a background task to avoid deadlock in cog_load
        self.bot.loop.create_task(self._connect_node())

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def _connect_node(self):
        # Wait for the bot to fully connect to Discord so it has a User ID
        await self.bot.wait_until_ready()
        
        logger.info(f"Connecting Mafic node to {LAVA_HOST}:{LAVA_PORT}...")
        try:
            await self.pool.create_node(
                host=LAVA_HOST,
                port=LAVA_PORT,
                password=LAVA_PASS,
                secure=LAVA_SECURE,
                label="MAIN_NODE"
            )
            logger.info("Mafic node connected successfully! 🎶")
        except Exception as e:
            print(f"CRITICAL ERROR: Mafic failed to connect: {e}")
            logger.error(f"Failed to connect Mafic node: {e}")

    @property
    def command_name(self) -> str: return "music"

    @property
    def description(self) -> str: return "Music playback commands using Mafic"

    async def _get_artwork(self, session: aiohttp.ClientSession, track: mafic.Track) -> str | None:
        # Mafic / Lavalink v4 uses artwork_url
        raw = getattr(track, "artwork_url", None)
        if _is_valid_artwork(raw, allow_yt=True): return raw
        
        # Fallback to iTunes for better quality/missing covers
        return await _itunes_artwork(session, f"{track.title} {track.author}")

    async def _delete_np(self, guild_id: int):
        msg = self._np_messages.pop(guild_id, None)
        if msg:
            try: await msg.delete()
            except discord.HTTPException: pass

    async def _send_np(self, channel: discord.TextChannel, player: MaficPlayer, track: mafic.Track, requester: discord.Member | str, artwork_url: str | None):
        guild_id = channel.guild.id
        
        if guild_id not in self._np_locks:
            self._np_locks[guild_id] = asyncio.Lock()

        async with self._np_locks[guild_id]:
            await self._delete_np(guild_id)
            view = _build_player_view(self, player, track, requester, artwork_url)
            msg = await channel.send(view=view)
            self._np_messages[guild_id] = msg

    def _check_voice(self, ctx: commands.Context) -> MaficPlayer | None:
        return ctx.voice_client

    async def _ensure_voice(self, ctx: commands.Context) -> MaficPlayer | None:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("You need to be in a voice channel.")
            return None
        
        player: MaficPlayer = ctx.voice_client
        if player:
            if player.channel != ctx.author.voice.channel:
                try:
                    await player.move_to(ctx.author.voice.channel)
                except Exception as e:
                    await ctx.reply(f"⚠️ Failed to move to your voice channel: {e}")
                    return None
        else:
            try:
                player = await ctx.author.voice.channel.connect(cls=MaficPlayer, self_deaf=True)
            except Exception as e:
                await ctx.reply(f"⚠️ Voice connection error: {e}")
                return None
        
        player._text_channel_id = ctx.channel.id
        return player

    async def _search_tracks(self, player: MaficPlayer, query: str):
        """Unified search logic with provider fallback and timeout management."""
        if _URL_RE.match(query.strip()):
            try:
                return await asyncio.wait_for(player.fetch_tracks(query.strip()), timeout=5.0)
            except:
                return None

        # Priority: Spotify -> YT Music -> YouTube -> SoundCloud
        search_attempts = [
            (mafic.SearchType.SPOTIFY_SEARCH, query),
            (mafic.SearchType.YOUTUBE_MUSIC, query),
            (mafic.SearchType.YOUTUBE, query),
            (mafic.SearchType.SOUNDCLOUD, query),
            # Final catch-all fallback: YouTube with "audio" keyword for better results
            (mafic.SearchType.YOUTUBE, f"{query} audio")
        ]
        
        for st, q in search_attempts:
            try:
                tracks = await asyncio.wait_for(player.fetch_tracks(q, search_type=st), timeout=5.0)
                if tracks:
                    # If it's a list, filter out dead results if any (node specific)
                    if isinstance(tracks, list) and len(tracks) > 0:
                        return tracks
                    elif not isinstance(tracks, list): # Playlist
                        return tracks
            except Exception as e:
                logger.debug(f"Search provider {st} failed for query '{q}': {e}")
                continue
        return None

    async def _play_track(self, player: MaficPlayer, queued_track: QueuedTrack, ctx: commands.Context = None):
        try:
            player.current_requester = queued_track.requester
            await player.play(queued_track.track)
            # Tracking for autoplay duplicates
            if not hasattr(player, 'autoplay_history'): player.autoplay_history = []
            player.autoplay_history.append(queued_track.id)
            if len(player.autoplay_history) > 15: player.autoplay_history.pop(0)
        except mafic.errors.HTTPNotFound as e:
            if "Session not found" in str(e):
                logger.warning(f"Mafic session not found for guild {player.guild.id}. Attempting recovery...")
                
                channel = player.channel
                text_id = player._text_channel_id
                queue = list(player.queue)
                history = list(player.history)
                loop = player.loop_mode
                autoplay = player.autoplay
                always_on = player.always_on
                
                try: await player.disconnect()
                except: pass
                
                if ctx: new_player = await self._ensure_voice(ctx)
                elif channel: new_player = await channel.connect(cls=MaficPlayer)
                else: return

                if new_player:
                    new_player._text_channel_id = text_id
                    new_player.queue = queue
                    new_player.history = history
                    new_player.loop_mode = loop
                    new_player.autoplay = autoplay
                    new_player.always_on = always_on
                    await new_player.play(queued_track.track)
            else:
                raise


    def _is_duplicate(self, track, current_track, player):
        """Check if a track is a duplicate or too similar to current/history."""
        if track.id == current_track.id: return True
        if track.id in getattr(player, 'autoplay_history', []): return True
        
        t1 = track.title.lower()
        t2 = current_track.title.lower()
        
        # Clean titles for comparison (remove mix, radio, etc)
        def clean(s): return re.sub(r'\(.*?\)|\[.*?\]|official|video|lyric|audio|radio|edit|remix|mix', '', s).strip()
        c1, c2 = clean(t1), clean(t2)
        
        if c1 == c2: return True
        
        # Similarity ratio
        ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
        if ratio > 0.6: return True # Slightly aggressive to avoid "Epic versions"
        
        # Substring match on cleaned titles
        if len(c1) > 3 and len(c2) > 3:
            if c2 in c1 or c1 in c2: return True
        
        return False

    async def _enqueue_and_play(self, ctx: commands.Context, track: mafic.Track, search_message: discord.Message | None = None, query_str: str | None = None):
        player = await self._ensure_voice(ctx)
        if not player: return

        if search_message:
            try: await search_message.delete()
            except discord.HTTPException: pass

        guild_id = ctx.guild.id
        qt = QueuedTrack(track, ctx.author)
        if player.current or len(player.queue) > 0:
            player.queue.append(qt)
            pos = len(player.queue)
            layout = discord.ui.LayoutView(timeout=30)
            c = discord.ui.Container()
            c.add_item(discord.ui.TextDisplay(f"Added to queue: **{track.title}**"))
            c.add_item(discord.ui.TextDisplay(f"*{track.author}*  ·  `{_format_duration(track.length)}`  ·  Position `{pos}`  ·  Source: `{track.source}`"))
            layout.add_item(c)
            await ctx.reply(view=layout)
        else:
            await self._play_track(player, qt, ctx=ctx)

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song by name or URL."""
        player = await self._ensure_voice(ctx)
        if not player: return

        # Check if node is ready
        if not self.pool.nodes:
            await ctx.reply("❌ No Lavalink nodes connected. Please wait a moment or check your config.")
            return

        async with ctx.typing():
            try:
                tracks = await self._search_tracks(player, query)

                if not tracks:
                    await ctx.reply(f"No results found for **{query}**.")
                    return

                if isinstance(tracks, mafic.Playlist):
                    added = 0
                    for t in tracks.tracks:
                        qt = QueuedTrack(t, ctx.author)
                        if not player.current and added == 0:
                            await self._play_track(player, qt, ctx=ctx)
                        else:
                            player.queue.append(qt)
                        added += 1
                    
                    layout = discord.ui.LayoutView(timeout=30)
                    c = discord.ui.Container()
                    c.add_item(discord.ui.TextDisplay(f"Added playlist: **{tracks.name}**"))
                    c.add_item(discord.ui.TextDisplay(f"`{added}` tracks added to the queue."))
                    layout.add_item(c)
                    await ctx.reply(view=layout)
                    return

                if _URL_RE.match(query.strip()) or len(tracks) == 1:
                    await self._enqueue_and_play(ctx, tracks[0], query_str=query)
                else:
                    view = _SearchSelectView(self, ctx, tracks[:10], query)
                    await ctx.reply(view=view)
            except Exception as e:
                await ctx.reply(f"Search failed: {e}")

    @play.error
    async def play_error(self, ctx, error):
        await ctx.reply(f"❌ Play error: {error}")

    @commands.command(name="skip", aliases=["s", "next"])
    async def skip(self, ctx: commands.Context):
        """Skip the current track."""
        player = self._check_voice(ctx)
        if not player or not player.current:
            await ctx.reply("Nothing is playing.")
            return
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Skipped: **{player.current.title}**"))
        layout.add_item(c)
        
        await ctx.reply(view=layout)
        player.skipping = True
        await player.stop()

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pause playback."""
        player = self._check_voice(ctx)
        if not player: return
        await player.pause()
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("Playback paused."))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="resume", aliases=["unpause", "res"])
    async def resume(self, ctx: commands.Context):
        """Resume playback."""
        player = self._check_voice(ctx)
        if not player: return
        await player.resume()
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("Playback resumed."))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="stop", aliases=["st"])
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue."""
        player = self._check_voice(ctx)
        if not player: return
        player.queue.clear()
        await player.disconnect()
        await self._delete_np(ctx.guild.id)
        self._np_locks.pop(ctx.guild.id, None)
        self._last_track_id.pop(ctx.guild.id, None)
        self._np_artworks.pop(ctx.guild.id, None)
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("Stopped playback and disconnected."))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="join", aliases=["connect", "jc"])
    async def join(self, ctx: commands.Context):
        """Make the bot join your voice channel."""
        player = await self._ensure_voice(ctx)
        if player:
            layout = discord.ui.LayoutView(timeout=30)
            c = discord.ui.Container()
            c.add_item(discord.ui.TextDisplay(f"Joined **{ctx.author.voice.channel.name}**"))
            layout.add_item(c)
            await ctx.reply(view=layout)

    @commands.command(name="leave", aliases=["dc", "disconnect"])
    async def leave(self, ctx: commands.Context):
        """Make the bot leave the voice channel."""
        await self.stop(ctx)

    @commands.command(name="clearqueue", aliases=["cq", "cl"])
    async def clearqueue(self, ctx: commands.Context):
        """Clear the queue."""
        player = self._check_voice(ctx)
        if not player: return
        player.queue.clear()
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("Queue cleared."))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int):
        """Remove a song from the queue by its number."""
        player = self._check_voice(ctx)
        if not player or not player.queue:
            await ctx.reply("The queue is empty.")
            return
        
        if index < 1 or index > len(player.queue):
            await ctx.reply(f"Invalid index. Please provide a number between 1 and {len(player.queue)}.")
            return
        
        removed = player.queue.pop(index - 1)
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Removed: **{removed.title}**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="move")
    async def move(self, ctx: commands.Context, from_idx: int, to_idx: int):
        """Move a song from one position to another."""
        player = self._check_voice(ctx)
        if not player or len(player.queue) < 2:
            await ctx.reply("Not enough songs in queue to move.")
            return
            
        if any(i < 1 or i > len(player.queue) for i in (from_idx, to_idx)):
            await ctx.reply(f"Invalid positions. Range: 1 to {len(player.queue)}.")
            return
            
        track = player.queue.pop(from_idx - 1)
        player.queue.insert(to_idx - 1, track)
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Moved **{track.title}** to position `{to_idx}`"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="swap")
    async def swap(self, ctx: commands.Context, pos1: int, pos2: int):
        """Swap the positions of two songs."""
        player = self._check_voice(ctx)
        if not player or len(player.queue) < 2:
            await ctx.reply("Not enough songs to swap.")
            return
            
        if any(i < 1 or i > len(player.queue) for i in (pos1, pos2)):
            await ctx.reply(f"Invalid positions. Range: 1 to {len(player.queue)}.")
            return
            
        player.queue[pos1-1], player.queue[pos2-1] = player.queue[pos2-1], player.queue[pos1-1]
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Swapped positions `{pos1}` and `{pos2}`"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="skipto", aliases=["jump"])
    async def skipto(self, ctx: commands.Context, index: int):
        """Skip directly to a specific song number."""
        player = self._check_voice(ctx)
        if not player or not player.queue:
            await ctx.reply("The queue is empty.")
            return
            
        if index < 1 or index > len(player.queue):
            await ctx.reply(f"Invalid index. Range: 1 to {len(player.queue)}.")
            return
            
        # Remove all songs before the target
        for _ in range(index - 1):
            player.queue.pop(0)
            
        player.skipping = True
        await player.stop()
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Jumped straight to track `{index}`"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="playnext", aliases=["pn"])
    async def playnext(self, ctx: commands.Context, *, query: str):
        """Add a song to the very top of the queue."""
        async with ctx.typing():
            player = await self._ensure_voice(ctx)
            if not player: return

            tracks = await self._search_tracks(player, query)
            
            if not tracks:
                await ctx.reply(f"No results found for **{query}**")
                return

            if isinstance(tracks, mafic.Playlist):
                track = tracks.tracks[0]
            else:
                track = tracks[0]

            qt = QueuedTrack(track, ctx.author)
            if not player.current:
                await self._play_track(player, qt, ctx=ctx)
            else:
                player.queue.insert(0, qt)

            layout = discord.ui.LayoutView(timeout=30)
            c = discord.ui.Container()
            c.add_item(discord.ui.TextDisplay(f"Added to play next: **{track.title}**"))
            layout.add_item(c)
            await ctx.reply(view=layout)

    @commands.command(name="autoplay", aliases=["ap"])
    async def autoplay(self, ctx: commands.Context):
        """Toggle autoplay for related songs."""
        player = self._check_voice(ctx)
        if not player:
            player = await self._ensure_voice(ctx)
            if not player: return

        player.autoplay = not player.autoplay
        status = "ENABLED" if player.autoplay else "DISABLED"
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Autoplay is now **{status}**"))
        if player.autoplay:
            c.add_item(discord.ui.TextDisplay("The bot will automatically play related songs when the queue ends."))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="seek")
    async def seek(self, ctx: commands.Context, position: str):
        """Seek to a position (e.g. 1:30 or 90)."""
        player = self._check_voice(ctx)
        if not player or not player.current:
            await ctx.reply("Nothing is playing.")
            return
            
        # Parse time
        try:
            if ":" in position:
                parts = position.split(":")
                if len(parts) == 2:
                    seconds = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                else: raise ValueError()
            else:
                seconds = int(position)
        except:
            await ctx.reply("Invalid time format. Use `1:30` or seconds.")
            return
            
        ms = seconds * 1000
        await player.seek(ms)
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Seeked to `{position}`"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="forward")
    async def forward(self, ctx: commands.Context, seconds: int = 15):
        """Fast-forward the song."""
        player = self._check_voice(ctx)
        if not player or not player.current: return
        
        new_pos = player.position + (seconds * 1000)
        await player.seek(min(new_pos, player.current.length))
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Forwarded **{seconds}s**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="rewind")
    async def rewind(self, ctx: commands.Context, seconds: int = 15):
        """Rewind the song."""
        player = self._check_voice(ctx)
        if not player or not player.current: return
        
        new_pos = max(0, player.position - (seconds * 1000))
        await player.seek(new_pos)
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Rewound **{seconds}s**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="replay", aliases=["restart"])
    async def replay(self, ctx: commands.Context):
        """Restart the current song."""
        player = self._check_voice(ctx)
        if not player or not player.current: return
        await player.seek(0)
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("Restarted the current track."))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="grab", aliases=["save"])
    async def grab(self, ctx: commands.Context):
        """DM you the current song info."""
        player = self._check_voice(ctx)
        if not player or not player.current: return
        
        track = player.current
        msg = f"**{track.title}**\nAuthor: {track.author}\nLink: {track.uri}"
        try:
            await ctx.author.send(msg)
            await ctx.message.add_reaction("📩")
        except:
            await ctx.reply("I couldn't DM you. Check your privacy settings.")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context, page: int = 1):
        """Show the current queue."""
        player = self._check_voice(ctx)
        if not player or not player.queue:
            await ctx.reply("The queue is empty.")
            return
        view = _build_queue_view(player, page - 1)
        await ctx.reply(view=view)

    @commands.command(name="nowplaying", aliases=["np", "current"])
    async def nowplaying(self, ctx: commands.Context):
        """Show the current track."""
        player = self._check_voice(ctx)
        if not player or not player.current:
            await ctx.reply("Nothing is playing.")
            return
        guild_id = ctx.guild.id
        requester = player.current_requester or ctx.author
        artwork = self._np_artworks.get(guild_id)
        view = _build_player_view(self, player, player.current, requester, artwork)
        await ctx.reply(view=view)

    @commands.command(name="history")
    async def history(self, ctx: commands.Context):
        """Show recently played songs."""
        player = self._check_voice(ctx)
        if not player or not player.history:
            await ctx.reply("No history available.")
            return
            
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("## Recently Played"))
        c.add_item(discord.ui.Separator())
        
        lines = []
        for i, t in enumerate(player.history[-10:][::-1], 1):
            lines.append(f"`{i}.` **{t.title}** — *{t.author}*")
        c.add_item(discord.ui.TextDisplay("\n".join(lines)))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="search")
    async def search(self, ctx: commands.Context, *, query: str):
        """Search for a song and pick from results."""
        async with ctx.typing():
            player = await self._ensure_voice(ctx)
            if not player: return
            
            # Prefer YouTube Music for search
            results = await player.fetch_tracks(f"ytmsearch:{query}")
            if not results:
                results = await player.fetch_tracks(f"ytsearch:{query}")
            if not results:
                results = await player.fetch_tracks(f"spsearch:{query}")
                
            tracks_list = results.tracks if isinstance(results, mafic.Playlist) else results
            if not tracks_list:
                await ctx.reply("No results found.")
                return
                
            view = _SearchSelectView(self, ctx, tracks_list[:5], query)
            await ctx.reply(view=view)


    @commands.command(name="24/7", aliases=["247", "alwayson"])
    async def alwayson(self, ctx: commands.Context):
        """Toggle whether the bot stays in VC when empty."""
        player = self._check_voice(ctx)
        if not player: return
        player.always_on = not player.always_on
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"24/7 Mode is now **{'ENABLED' if player.always_on else 'DISABLED'}**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    # --- FILTERS ---
    
    @commands.command(name="bassboost", aliases=["bb"])
    async def bassboost(self, ctx: commands.Context, level: str = "medium"):
        """Toggle bassboost: low, medium, high, or off."""
        player = self._check_voice(ctx)
        if not player: return
        
        if level == "off":
            await player.add_filter(mafic.Filter(), label="bass")
            await ctx.reply("Bassboost turned off.")
            return
            
        gains = {"low": 0.15, "medium": 0.25, "high": 0.45}
        gain = gains.get(level.lower(), 0.25)
        
        eq = mafic.Equalizer(bands=[(0, gain), (1, gain), (2, gain)])
        await player.add_filter(mafic.Filter(equalizer=eq), label="bass")
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Bassboost set to **{level.upper()}**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="nightcore")
    async def nightcore(self, ctx: commands.Context):
        """Toggle nightcore filter."""
        player = self._check_voice(ctx)
        if not player: return
        
        # Check if already active (simplified check)
        filter = mafic.Filter(timescale=mafic.Timescale(speed=1.2, pitch=1.2))
        await player.add_filter(filter, label="nightcore")
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("Nightcore filter **ENABLED**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="vaporwave", aliases=["slowed"])
    async def vaporwave(self, ctx: commands.Context):
        """Toggle vaporwave filter."""
        player = self._check_voice(ctx)
        if not player: return
        
        filter = mafic.Filter(timescale=mafic.Timescale(speed=0.8, pitch=0.8))
        await player.add_filter(filter, label="vaporwave")
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("Vaporwave filter **ENABLED**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="8d")
    async def eight_d(self, ctx: commands.Context):
        """Toggle 8D audio filter."""
        player = self._check_voice(ctx)
        if not player: return
        
        filter = mafic.Filter(rotation=mafic.Rotation(rotation_hz=0.2))
        await player.add_filter(filter, label="8d")
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("8D audio filter **ENABLED**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="speed")
    async def speed(self, ctx: commands.Context, val: float):
        """Set a custom playback speed (0.5 - 2.0)."""
        player = self._check_voice(ctx)
        if not player: return
        val = max(0.5, min(val, 2.0))
        await player.add_filter(mafic.Filter(timescale=mafic.Timescale(speed=val)), label="speed")
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Playback speed set to **{val}x**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="pitch")
    async def pitch(self, ctx: commands.Context, val: float):
        """Set a custom playback pitch (0.5 - 2.0)."""
        player = self._check_voice(ctx)
        if not player: return
        val = max(0.5, min(val, 2.0))
        await player.add_filter(mafic.Filter(timescale=mafic.Timescale(pitch=val)), label="pitch")
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Audio pitch set to **{val}**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="resetfilters", aliases=["clearfilters", "rsf"])
    async def resetfilters(self, ctx: commands.Context):
        """Remove all active audio filters."""
        player = self._check_voice(ctx)
        if not player: return
        await player.add_filter(mafic.Filter())
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("All audio filters have been **CLEARED**"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="volume", aliases=["vol", "v"])
    async def volume(self, ctx: commands.Context, vol: int):
        """Set volume (0-100)."""
        player = self._check_voice(ctx)
        if not player: return
        vol = max(0, min(vol, 100))
        await player.set_volume(vol)
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Volume set to `{vol}%`"))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the queue."""
        player = self._check_voice(ctx)
        if not player or not player.queue:
            await ctx.reply("The queue is empty.")
            return
        import random
        random.shuffle(player.queue)
        
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Shuffled `{len(player.queue)}` tracks in the queue."))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.command(name="loop", aliases=["repeat"])
    async def loop(self, ctx: commands.Context, mode: str = ""):
        """Set loop mode: track, queue, or off."""
        player = self._check_voice(ctx)
        if not player: return
        mode = mode.lower()
        if mode in ("track", "song", "1"):
            player.loop_mode = "track"
            label = "Loop Mode: Track"
        elif mode in ("queue", "all", "q"):
            player.loop_mode = "queue"
            label = "Loop Mode: Queue"
        else:
            player.loop_mode = "none"
            label = "Loop Mode: Off"
            
        layout = discord.ui.LayoutView(timeout=30)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(label))
        layout.add_item(c)
        await ctx.reply(view=layout)

    @commands.Cog.listener()
    async def on_track_start(self, event: mafic.TrackStartEvent):
        player: MaficPlayer = event.player
        track = event.track
        guild_id = player.guild.id
        channel = player.guild.get_channel(player._text_channel_id)
        if not channel: return

        # Debounce duplicate track start events (Lavalink bug)
        last = self._last_track_id.get(guild_id)
        now = time.monotonic()
        if last and last[0] == track.id and now - last[1] < 2.0:
            return
        self._last_track_id[guild_id] = (track.id, now)

        artwork = await self._get_artwork(self.session, track) if self.session else None
        self._np_artworks[guild_id] = artwork
        await self._send_np(channel, player, track, player.current_requester or "Unknown", artwork)

    @commands.Cog.listener()
    async def on_track_end(self, event: mafic.TrackEndEvent):
        player: MaficPlayer = event.player
        if event.reason == "REPLACED": return
        
        # Clear debounce on track end to allow same song to play again legitimately
        self._last_track_id.pop(player.guild.id, None)

        # Add to history
        qt = QueuedTrack(event.track, player.current_requester or "Autoplay")
        player.history.append(qt)
        if len(player.history) > 20: player.history.pop(0)

        if player.loop_mode == "track" and not player.skipping:
            await self._play_track(player, qt)
            return
        
        # Reset skipping flag if it was set
        player.skipping = False
        
        if player.loop_mode == "queue":
            player.queue.append(qt)

        if player.queue:
            next_qt = player.queue.pop(0)
            await self._play_track(player, next_qt)
        elif player.autoplay:
            # Autoplay: try to use YouTube Mix (RD) for a more natural radio experience
            # If it's a YouTube track, we can generate a Mix URL
            next_track = None
            
            # Try to extract YouTube ID for Mix
            video_id = None
            if "youtube.com" in event.track.uri or "youtu.be" in event.track.uri:
                match = re.search(r'(?:v=|\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})', event.track.uri)
                if match:
                    video_id = match.group(1)

            if video_id:
                mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
                try:
                    results = await asyncio.wait_for(player.fetch_tracks(mix_url), timeout=5.0)
                    if isinstance(results, mafic.Playlist):
                        for t in results.tracks:
                            if not self._is_duplicate(t, event.track, player):
                                next_track = t
                                break
                except:
                    pass

            if not next_track:
                query = f"songs similar to {event.track.title} {event.track.author}"
                try:
                    results = await asyncio.wait_for(player.fetch_tracks(query, search_type=mafic.SearchType.YOUTUBE_MUSIC), timeout=5.0)
                    if not results:
                        results = await self._search_tracks(player, f"{event.track.title} {event.track.author} similar")
                    
                    if results:
                        tracks = results.tracks if isinstance(results, mafic.Playlist) else results
                        for t in tracks:
                            if not self._is_duplicate(t, event.track, player):
                                next_track = t
                                break
                except Exception as e:
                    logger.error(f"Autoplay fallback failed: {e}")

            if next_track:
                next_qt = QueuedTrack(next_track, "Autoplay")
                await self._play_track(player, next_qt)
                return
            
        # If no more tracks and no autoplay
        if not player.queue:
            await self._delete_np(player.guild.id)
            self._np_artworks.pop(player.guild.id, None)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.id == self.bot.user.id: return
        
        # Get the player for this guild
        player: MaficPlayer = member.guild.voice_client
        if not player or player.always_on: return
        
        # If the bot is now alone in the VC
        if before.channel and before.channel.id == player.channel.id:
            if len([m for m in before.channel.members if not m.bot]) == 0:
                # Wait a bit to see if someone rejoins
                await asyncio.sleep(10)
                # Verify bot still in same channel
                if not player.channel or player.channel.id != before.channel.id:
                    return
                if len([m for m in player.channel.members if not m.bot]) == 0:
                    await player.disconnect()
                    await self._delete_np(member.guild.id)
                    self._np_locks.pop(member.guild.id, None)
                    self._last_track_id.pop(member.guild.id, None)
                    self._np_artworks.pop(member.guild.id, None)

    async def _check_interaction(self, interaction: discord.Interaction, player: MaficPlayer):
        if not player: 
            await interaction.response.send_message("The bot is not connected to a voice channel.", ephemeral=True)
            return False
        
        # Check if in same VC
        if not interaction.user.voice or interaction.user.voice.channel.id != player.channel.id:
            await interaction.response.send_message("You must be in the same voice channel to use buttons.", ephemeral=True)
            return False
            
        if not player.current: return True
        
        requester = player.current_requester or "Autoplay"
        if requester == "Autoplay":
            return True
            
        if isinstance(requester, discord.Member) and interaction.user.id == requester.id:
            return True
            
        if interaction.user.guild_permissions.manage_guild:
            return True
            
        await interaction.response.send_message("Only the requester can use these buttons for this song.", ephemeral=True)
        return False

    async def _btn_previous(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client
        if not await self._check_interaction(interaction, player): return
        
        if not player or not player.history:
            await interaction.response.send_message("No previous tracks found.", ephemeral=True)
            return
        
        # Take the last track from history and play it
        prev_track = player.history.pop()
        # If something is playing, push it to the front of the queue
        if player.current:
            qt = QueuedTrack(player.current, player.current_requester or "Unknown")
            player.queue.insert(0, qt)
            
        await self._play_track(player, prev_track)
        await interaction.response.send_message(f"Playing previous: **{prev_track.title}**", ephemeral=True)

    async def _btn_pause(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client
        if not await self._check_interaction(interaction, player): return
        
        if not player or not player.current:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        if player.paused: await player.resume()
        else: await player.pause()
        guild_id = interaction.guild_id
        requester = player.current_requester or "Autoplay"
        artwork = self._np_artworks.get(guild_id)
        new_view = _build_player_view(self, player, player.current, requester, artwork)
        await interaction.response.edit_message(view=new_view)

    async def _btn_skip(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client
        if not await self._check_interaction(interaction, player): return
        
        if not player or not player.current:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        player.skipping = True
        await player.stop()
        await interaction.response.send_message("Skipped!", ephemeral=True)

    async def _btn_loop(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client
        if not await self._check_interaction(interaction, player): return
        
        if not player or not player.current:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        modes = ["none", "track", "queue"]
        idx = modes.index(player.loop_mode)
        player.loop_mode = modes[(idx + 1) % 3]
        
        guild_id = interaction.guild_id
        requester = player.current_requester or "Autoplay"
        artwork = self._np_artworks.get(guild_id)
        new_view = _build_player_view(self, player, player.current, requester, artwork)
        await interaction.response.edit_message(view=new_view)

    async def _btn_stop(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client
        if not await self._check_interaction(interaction, player): return
        
        if not player:
            await interaction.response.send_message("Not connected.", ephemeral=True)
            return
        guild_id = interaction.guild_id
        player.queue.clear()
        await player.disconnect()
        await self._delete_np(guild_id)
        self._np_locks.pop(guild_id, None)
        self._last_track_id.pop(guild_id, None)
        self._np_artworks.pop(guild_id, None)
        
        layout = discord.ui.LayoutView(timeout=10)
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("Disconnected."))
        layout.add_item(c)
        await interaction.response.send_message(view=layout, ephemeral=True)

async def setup(bot):
    logger.info("Setting up MusicCommand cog...")
    await bot.add_cog(MusicCommand(bot))
    logger.info("MusicCommand cog added successfully.")
