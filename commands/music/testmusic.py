# rewrite test by claude lmao

import asyncio
import difflib
import logging
import os
import random
import re
import time

import aiohttp
import discord
import mafic
from discord.ext import commands

from ..base import BaseCommand

# ─────────────────────────── configuration ────────────────────────────────── #

LAVA_HOST   = os.getenv("LAVALINK_HOST",     "lunar.voidhosting.vip")
LAVA_PORT   = int(os.getenv("LAVALINK_PORT", "9087"))
LAVA_PASS   = os.getenv("LAVALINK_PASSWORD", "2012hhh2012_secure_password_here")
LAVA_SECURE = os.getenv("LAVALINK_SECURE",   "false").lower() == "true"

LYRICS_API  = "https://api.lyrics.ovh/v1/{artist}/{title}"
ITUNES_API  = "https://itunes.apple.com/search"

logger = logging.getLogger("bot")

_URL_RE       = re.compile(r"^https?://\S+$|^www\.\S+$")
_YT_ID_RE     = re.compile(r"(?:v=|\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})")
_YT_HOSTS     = ("ytimg.com", "img.youtube.com", "i9.ytimg.com")

LOOP_CYCLE    = ("none", "track", "queue")
LOOP_LABELS   = {"none": "Loop: Off", "track": "Loop: Track", "queue": "Loop: Queue"}
SPEED_RANGE   = (0.5, 2.0)


# ─────────────────────────────── helpers ──────────────────────────────────── #

def _ms(ms: int | None) -> str:
    """Format milliseconds → mm:ss or h:mm:ss. Returns 'Live' for None/0."""
    if not ms:
        return "Live"
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(val, hi))


def _valid_art(url: str | None, *, allow_yt: bool = False) -> bool:
    if not url or "1x1" in url:
        return False
    if not allow_yt and any(h in url for h in _YT_HOSTS):
        return False
    return True


# ─────────────────────────────── data classes ─────────────────────────────── #

class QueuedTrack:
    """Wraps a mafic.Track with requester metadata."""

    __slots__ = ("track", "requester")

    def __init__(self, track: mafic.Track, requester: "discord.Member | str"):
        self.track     = track
        self.requester = requester

    # Proxy attribute access to the underlying track for convenience
    def __getattr__(self, name: str):
        return getattr(self.track, name)


class MaficPlayer(mafic.Player):
    """Extended Lavalink player with queue, history and state flags."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue:             list[QueuedTrack]       = []
        self.history:           list[QueuedTrack]       = []
        self.loop_mode:         str                     = "none"
        self._text_channel_id:  int | None              = None
        self.autoplay:          bool                    = False
        self.always_on:         bool                    = False
        self.skipping:          bool                    = False
        self.autoplay_history:  list[str]               = []
        self.current_requester: discord.Member | str | None = None


# ───────────────────────────── view builders ──────────────────────────────── #

def _container(*items) -> discord.ui.Container:
    c = discord.ui.Container()
    for item in items:
        c.add_item(item)
    return c


def _layout(*containers, timeout: int = 30) -> discord.ui.LayoutView:
    v = discord.ui.LayoutView(timeout=timeout)
    for c in containers:
        v.add_item(c)
    return v


def _sep(small: bool = False):
    return discord.ui.Separator(
        spacing=discord.SeparatorSpacing.small if small else discord.SeparatorSpacing.large
    )


def build_player_view(
    cog:        "MusicCommand",
    player:     MaficPlayer,
    track:      mafic.Track,
    requester:  "discord.Member | str",
    artwork:    str | None,
) -> discord.ui.LayoutView:
    dur  = _ms(track.length)
    req  = requester.mention if isinstance(requester, discord.Member) else f"**{requester}**"
    nxt  = player.queue[0].title if player.queue else None

    c = discord.ui.Container()
    c.add_item(discord.ui.TextDisplay("## Now Playing"))
    c.add_item(_sep())

    # Track info — with or without thumbnail
    if artwork:
        sec = discord.ui.Section(accessory=discord.ui.Thumbnail(media=artwork))
        sec.add_item(discord.ui.TextDisplay(f"**{track.title}**"))
        sec.add_item(discord.ui.TextDisplay(f"*{track.author}*"))
        sec.add_item(discord.ui.TextDisplay(f"`{dur}`"))
        c.add_item(sec)
    else:
        c.add_item(discord.ui.TextDisplay(f"**{track.title}**"))
        c.add_item(discord.ui.TextDisplay(f"*{track.author}*  ·  `{dur}`"))

    c.add_item(_sep(small=True))

    meta = f"Requested by {req}"
    if nxt:
        meta += f"  ·  Up next: **{nxt}**"
    c.add_item(discord.ui.TextDisplay(meta))
    c.add_item(_sep())

    # Control buttons
    pause_label = "Resume" if player.paused else "Pause"
    pause_style = discord.ButtonStyle.success if player.paused else discord.ButtonStyle.primary
    loop_label  = LOOP_LABELS[player.loop_mode]

    row = discord.ui.ActionRow(
        discord.ui.Button(label="⏮ Prev",   style=discord.ButtonStyle.secondary, custom_id="np_prev"),
        discord.ui.Button(label=pause_label, style=pause_style,                   custom_id="np_pause"),
        discord.ui.Button(label="⏭ Skip",   style=discord.ButtonStyle.secondary, custom_id="np_skip"),
        discord.ui.Button(label=loop_label,  style=discord.ButtonStyle.secondary, custom_id="np_loop"),
        discord.ui.Button(label="⏹ Stop",   style=discord.ButtonStyle.danger,    custom_id="np_stop"),
    )
    row.children[0].callback = cog._btn_prev
    row.children[1].callback = cog._btn_pause
    row.children[2].callback = cog._btn_skip
    row.children[3].callback = cog._btn_loop
    row.children[4].callback = cog._btn_stop

    c.add_item(row)
    return _layout(c, timeout=None)


def build_queue_view(player: MaficPlayer, page: int = 0) -> discord.ui.LayoutView:
    tracks     = list(player.queue)
    per_page   = 10
    total      = max(1, (len(tracks) + per_page - 1) // per_page)
    page       = max(0, min(page, total - 1))
    chunk      = tracks[page * per_page : (page + 1) * per_page]
    start      = page * per_page

    c = discord.ui.Container()
    c.add_item(discord.ui.TextDisplay("## Queue"))
    c.add_item(_sep())

    if not tracks:
        c.add_item(discord.ui.TextDisplay("The queue is empty."))
    else:
        lines = []
        for i, t in enumerate(chunk, start + 1):
            req = t.requester.name if isinstance(t.requester, discord.Member) else t.requester
            lines.append(f"`{i}.` **{t.title}** — *{t.author}*  ·  `{_ms(t.length)}`  ·  {req}")
        c.add_item(discord.ui.TextDisplay("\n".join(lines)))
        c.add_item(_sep(small=True))
        c.add_item(discord.ui.TextDisplay(
            f"Page **{page + 1}** of **{total}**  ·  **{len(tracks)}** tracks total"
        ))

    return _layout(c, timeout=60)


class SearchSelectView(discord.ui.LayoutView):
    """Ephemeral track-picker shown after a search."""

    def __init__(self, cog: "MusicCommand", ctx: commands.Context, tracks: list[mafic.Track], query: str):
        super().__init__(timeout=30)
        self._cog   = cog
        self._ctx   = ctx
        self._query = query

        options = [
            discord.SelectOption(
                label       = t.title[:100],
                description = f"{t.author} · {_ms(t.length)}"[:100],
                value       = str(i),
            )
            for i, t in enumerate(tracks[:10])
        ]
        self._tracks = tracks[:10]

        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("## Search Results"))
        c.add_item(_sep())
        c.add_item(discord.ui.TextDisplay("Pick a track to add to the queue."))

        row = discord.ui.ActionRow(
            discord.ui.Select(
                placeholder = "Choose a track…",
                options     = options,
                custom_id   = "search_select",
            )
        )
        row.children[0].callback = self._on_select
        c.add_item(row)
        self.add_item(c)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self._ctx.author.id:
            await interaction.response.send_message("Only the requester can pick.", ephemeral=True)
            return
        idx   = int(interaction.data["values"][0])
        track = self._tracks[idx]
        await interaction.response.defer()
        await self._cog._enqueue(self._ctx, track, delete_msg=interaction.message)


# ─────────────────────────────── cog ──────────────────────────────────────── #

class MusicCommand(BaseCommand):
    """Music playback powered by Lavalink via mafic."""

    def __init__(self, bot):
        super().__init__(bot)
        self._np_msg:      dict[int, discord.Message]  = {}
        self._np_art:      dict[int, str | None]        = {}
        self._np_locks:    dict[int, asyncio.Lock]      = {}
        self._last_event:  dict[int, tuple[str, float]] = {}
        self.session:      aiohttp.ClientSession | None = None
        self.pool          = mafic.NodePool(bot)
        logger.info("MusicCommand initialised.")

    # ── lifecycle ──────────────────────────────────────────────────────────── #

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        self.bot.loop.create_task(self._connect_node())

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def cog_command_error(self, ctx, error):
        orig = getattr(error, "original", error)
        await ctx.reply(f"⚠️ {orig}")

    async def _connect_node(self):
        await self.bot.wait_until_ready()
        logger.info(f"Connecting Lavalink node {LAVA_HOST}:{LAVA_PORT}…")
        try:
            await self.pool.create_node(
                host     = LAVA_HOST,
                port     = LAVA_PORT,
                password = LAVA_PASS,
                secure   = LAVA_SECURE,
                label    = "MAIN",
            )
            logger.info("Lavalink node connected ✓")
        except Exception as exc:
            logger.error(f"Lavalink node connection failed: {exc}")

    # ── properties ─────────────────────────────────────────────────────────── #

    @property
    def command_name(self) -> str:  return "music"
    @property
    def description(self) -> str:   return "Music playback via Lavalink"

    # ── internal helpers ───────────────────────────────────────────────────── #

    def _player(self, ctx: commands.Context) -> MaficPlayer | None:
        return ctx.voice_client  # type: ignore

    async def _join(self, ctx: commands.Context) -> MaficPlayer | None:
        """Ensure the bot is in the author's voice channel, return the player."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("You need to be in a voice channel first.")
            return None
        player: MaficPlayer = ctx.voice_client  # type: ignore
        if not player:
            try:
                player = await ctx.author.voice.channel.connect(cls=MaficPlayer, self_deaf=True)
            except Exception as exc:
                await ctx.reply(f"Could not join voice: {exc}")
                return None
        player._text_channel_id = ctx.channel.id
        return player

    async def _search(self, player: MaficPlayer, query: str):
        """Search with provider fallback. Returns tracks/playlist or None."""
        if _URL_RE.match(query.strip()):
            try:
                return await asyncio.wait_for(player.fetch_tracks(query.strip()), timeout=6.0)
            except Exception:
                return None

        attempts = [
            (mafic.SearchType.SPOTIFY_SEARCH, query),
            (mafic.SearchType.YOUTUBE_MUSIC,  query),
            (mafic.SearchType.YOUTUBE,         query),
            (mafic.SearchType.SOUNDCLOUD,      query),
            (mafic.SearchType.YOUTUBE,         f"{query} audio"),
        ]
        for stype, q in attempts:
            try:
                result = await asyncio.wait_for(
                    player.fetch_tracks(q, search_type=stype), timeout=5.0
                )
                if result:
                    if isinstance(result, list) and len(result) > 0:
                        return result
                    elif not isinstance(result, list):
                        return result
            except Exception as exc:
                logger.debug(f"Provider {stype} failed for '{q}': {exc}")
        return None

    async def _get_artwork(self, track: mafic.Track) -> str | None:
        raw = getattr(track, "artwork_url", None)
        if _valid_art(raw, allow_yt=True):
            return raw
        if not self.session:
            return None
        try:
            async with self.session.get(
                ITUNES_API,
                params   = {"term": f"{track.title} {track.author}", "entity": "song", "limit": 1},
                timeout  = aiohttp.ClientTimeout(total=5),
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json(content_type=None)
                if not data.get("resultCount"):
                    return None
                art = data["results"][0].get("artworkUrl100", "")
                return art.replace("100x100bb", "600x600bb").replace("100x100", "600x600") if art else None
        except Exception:
            return None

    async def _delete_np(self, guild_id: int):
        msg = self._np_msg.pop(guild_id, None)
        if msg:
            try:
                await msg.delete()
            except discord.HTTPException:
                pass

    async def _send_np(
        self,
        channel:   discord.TextChannel,
        player:    MaficPlayer,
        track:     mafic.Track,
        requester: "discord.Member | str",
        artwork:   str | None,
    ):
        gid = channel.guild.id
        self._np_locks.setdefault(gid, asyncio.Lock())
        async with self._np_locks[gid]:
            await self._delete_np(gid)
            view = build_player_view(self, player, track, requester, artwork)
            self._np_msg[gid] = await channel.send(view=view)

    async def _play(self, player: MaficPlayer, qt: QueuedTrack, ctx: commands.Context | None = None):
        """Start playing a QueuedTrack, with Lavalink session-recovery on error."""
        player.current_requester = qt.requester
        try:
            await player.play(qt.track)
        except mafic.errors.HTTPNotFound as exc:
            if "Session not found" not in str(exc):
                raise
            logger.warning(f"Lavalink session lost for guild {player.guild.id}. Recovering…")
            # Save state
            ch, tid   = player.channel, player._text_channel_id
            q, hist   = list(player.queue), list(player.history)
            loop, ap  = player.loop_mode, player.autoplay
            ao        = player.always_on
            try:
                await player.disconnect()
            except Exception:
                pass
            # Reconnect
            new = await ctx.author.voice.channel.connect(cls=MaficPlayer, self_deaf=True) if ctx else \
                  await ch.connect(cls=MaficPlayer, self_deaf=True)
            if new:
                new._text_channel_id = tid
                new.queue, new.history = q, hist
                new.loop_mode, new.autoplay, new.always_on = loop, ap, ao
                await new.play(qt.track)
        # Track for duplicate detection
        player.autoplay_history.append(qt.track.id)
        if len(player.autoplay_history) > 20:
            player.autoplay_history.pop(0)

    async def _enqueue(
        self,
        ctx:        commands.Context,
        track:      mafic.Track,
        *,
        delete_msg: discord.Message | None = None,
        front:      bool                   = False,
    ):
        """Add a track to the queue (or play immediately if idle)."""
        player = await self._join(ctx)
        if not player:
            return
        if delete_msg:
            try:
                await delete_msg.delete()
            except discord.HTTPException:
                pass

        qt = QueuedTrack(track, ctx.author)
        if player.current or player.queue:
            if front:
                player.queue.insert(0, qt)
                pos_label = "next"
            else:
                player.queue.append(qt)
                pos_label = f"position `{len(player.queue)}`"

            c = discord.ui.Container()
            c.add_item(discord.ui.TextDisplay(f"Added to queue at {pos_label}: **{track.title}**"))
            c.add_item(discord.ui.TextDisplay(
                f"*{track.author}*  ·  `{_ms(track.length)}`  ·  `{track.source}`"
            ))
            await ctx.reply(view=_layout(c))
        else:
            await self._play(player, qt, ctx=ctx)

    def _is_dupe(self, candidate: mafic.Track, current: mafic.Track, player: MaficPlayer) -> bool:
        if candidate.id == current.id or candidate.id in player.autoplay_history:
            return True
        def clean(s: str) -> str:
            return re.sub(r"\(.*?\)|\[.*?\]|official|video|lyric|audio|radio|edit|remix|mix", "", s.lower()).strip()
        c1, c2 = clean(candidate.title), clean(current.title)
        if c1 == c2:
            return True
        if difflib.SequenceMatcher(None, candidate.title.lower(), current.title.lower()).ratio() > 0.6:
            return True
        if len(c1) > 3 and len(c2) > 3 and (c1 in c2 or c2 in c1):
            return True
        return False

    async def _check_btn(self, interaction: discord.Interaction, player: MaficPlayer) -> bool:
        """Validate button interactions — voice channel + requester check."""
        if not player:
            await interaction.response.send_message("Not in a voice channel.", ephemeral=True)
            return False
        if not interaction.user.voice or interaction.user.voice.channel.id != player.channel.id:
            await interaction.response.send_message("Join the voice channel first.", ephemeral=True)
            return False
        req = player.current_requester
        if req and req != "Autoplay" and isinstance(req, discord.Member):
            if interaction.user.id != req.id and not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "Only the requester (or a moderator) can use these controls.", ephemeral=True
                )
                return False
        return True

    # ── simple reply helpers ────────────────────────────────────────────────── #

    async def _ok(self, ctx: commands.Context, text: str):
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(text))
        await ctx.reply(view=_layout(c))

    # ═══════════════════════════ commands ═══════════════════════════════════ #

    # ── connection ──────────────────────────────────────────────────────────── #

    @commands.command(name="join", aliases=["connect", "jc"])
    async def join(self, ctx: commands.Context):
        """Make the bot join your voice channel."""
        player = await self._join(ctx)
        if player:
            await self._ok(ctx, f"Joined **{ctx.author.voice.channel.name}**.")

    @commands.command(name="leave", aliases=["dc", "disconnect"])
    async def leave(self, ctx: commands.Context):
        """Make the bot leave the voice channel."""
        await self.stop(ctx)

    # ── playback ────────────────────────────────────────────────────────────── #

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song by name or URL."""
        player = await self._join(ctx)
        if not player:
            return
        if not self.pool.nodes:
            await ctx.reply("No Lavalink nodes available. Please try again shortly.")
            return

        async with ctx.typing():
            result = await self._search(player, query)
            if not result:
                await ctx.reply(f"No results found for **{query}**.")
                return

            if isinstance(result, mafic.Playlist):
                count = 0
                for i, t in enumerate(result.tracks):
                    qt = QueuedTrack(t, ctx.author)
                    if not player.current and count == 0:
                        await self._play(player, qt, ctx=ctx)
                    else:
                        player.queue.append(qt)
                    count += 1
                c = discord.ui.Container()
                c.add_item(discord.ui.TextDisplay(f"Added playlist **{result.name}**"))
                c.add_item(discord.ui.TextDisplay(f"`{count}` tracks queued."))
                await ctx.reply(view=_layout(c))
                return

            # Single or search results
            if _URL_RE.match(query.strip()) or len(result) == 1:
                await self._enqueue(ctx, result[0])
            else:
                await ctx.reply(view=SearchSelectView(self, ctx, result[:10], query))

    @commands.command(name="playnext", aliases=["pn"])
    async def playnext(self, ctx: commands.Context, *, query: str):
        """Add a song to the top of the queue."""
        player = await self._join(ctx)
        if not player:
            return
        async with ctx.typing():
            result = await self._search(player, query)
            if not result:
                await ctx.reply(f"No results for **{query}**.")
                return
            track = (result.tracks[0] if isinstance(result, mafic.Playlist) else result[0])
            await self._enqueue(ctx, track, front=True)

    @commands.command(name="search")
    async def search(self, ctx: commands.Context, *, query: str):
        """Search and pick from a list of results."""
        player = await self._join(ctx)
        if not player:
            return
        async with ctx.typing():
            result = await self._search(player, query)
            tracks = result.tracks if isinstance(result, mafic.Playlist) else (result or [])
            if not tracks:
                await ctx.reply("No results found.")
                return
            await ctx.reply(view=SearchSelectView(self, ctx, tracks[:10], query))

    @commands.command(name="stop", aliases=["st"])
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue."""
        player = self._player(ctx)
        if not player:
            return
        gid = ctx.guild.id
        player.queue.clear()
        await player.disconnect()
        await self._delete_np(gid)
        self._np_locks.pop(gid, None)
        self._last_event.pop(gid, None)
        self._np_art.pop(gid, None)
        await self._ok(ctx, "Stopped and disconnected.")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pause playback."""
        player = self._player(ctx)
        if not player:
            return
        await player.pause()
        await self._ok(ctx, "Paused.")

    @commands.command(name="resume", aliases=["unpause", "res"])
    async def resume(self, ctx: commands.Context):
        """Resume playback."""
        player = self._player(ctx)
        if not player:
            return
        await player.resume()
        await self._ok(ctx, "Resumed.")

    @commands.command(name="skip", aliases=["s", "next"])
    async def skip(self, ctx: commands.Context):
        """Skip the current track."""
        player = self._player(ctx)
        if not player or not player.current:
            await ctx.reply("Nothing is playing.")
            return
        title = player.current.title
        player.skipping = True
        await player.stop()
        await self._ok(ctx, f"Skipped **{title}**.")

    @commands.command(name="skipto", aliases=["jump"])
    async def skipto(self, ctx: commands.Context, index: int):
        """Skip directly to a specific position in the queue."""
        player = self._player(ctx)
        if not player or not player.queue:
            await ctx.reply("The queue is empty.")
            return
        if not 1 <= index <= len(player.queue):
            await ctx.reply(f"Position must be between 1 and {len(player.queue)}.")
            return
        for _ in range(index - 1):
            player.queue.pop(0)
        player.skipping = True
        await player.stop()
        await self._ok(ctx, f"Jumped to track `{index}`.")

    @commands.command(name="seek")
    async def seek(self, ctx: commands.Context, position: str):
        """Seek to a position (mm:ss or seconds)."""
        player = self._player(ctx)
        if not player or not player.current:
            await ctx.reply("Nothing is playing.")
            return
        try:
            parts = position.split(":")
            if len(parts) == 2:
                secs = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                secs = int(position)
        except (ValueError, IndexError):
            await ctx.reply("Use a format like `1:30` or `90`.")
            return
        await player.seek(secs * 1000)
        await self._ok(ctx, f"Seeked to `{position}`.")

    @commands.command(name="forward")
    async def forward(self, ctx: commands.Context, seconds: int = 15):
        """Fast-forward by N seconds (default 15)."""
        player = self._player(ctx)
        if not player or not player.current:
            return
        await player.seek(min(player.position + seconds * 1000, player.current.length))
        await self._ok(ctx, f"Forwarded `{seconds}s`.")

    @commands.command(name="rewind")
    async def rewind(self, ctx: commands.Context, seconds: int = 15):
        """Rewind by N seconds (default 15)."""
        player = self._player(ctx)
        if not player or not player.current:
            return
        await player.seek(max(0, player.position - seconds * 1000))
        await self._ok(ctx, f"Rewound `{seconds}s`.")

    @commands.command(name="replay", aliases=["restart"])
    async def replay(self, ctx: commands.Context):
        """Restart the current song from the beginning."""
        player = self._player(ctx)
        if not player or not player.current:
            return
        await player.seek(0)
        await self._ok(ctx, "Restarted the current track.")

    @commands.command(name="volume", aliases=["vol", "v"])
    async def volume(self, ctx: commands.Context, vol: int):
        """Set volume (0–100)."""
        player = self._player(ctx)
        if not player:
            return
        vol = int(_clamp(vol, 0, 100))
        await player.set_volume(vol)
        await self._ok(ctx, f"Volume set to `{vol}%`.")

    # ── queue management ─────────────────────────────────────────────────────── #

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context, page: int = 1):
        """Show the current queue."""
        player = self._player(ctx)
        if not player or not player.queue:
            await ctx.reply("The queue is empty.")
            return
        await ctx.reply(view=build_queue_view(player, page - 1))

    @commands.command(name="clearqueue", aliases=["cq", "cl"])
    async def clearqueue(self, ctx: commands.Context):
        """Clear all tracks from the queue."""
        player = self._player(ctx)
        if not player:
            return
        player.queue.clear()
        await self._ok(ctx, "Queue cleared.")

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int):
        """Remove a track from the queue by its number."""
        player = self._player(ctx)
        if not player or not player.queue:
            await ctx.reply("The queue is empty.")
            return
        if not 1 <= index <= len(player.queue):
            await ctx.reply(f"Position must be between 1 and {len(player.queue)}.")
            return
        removed = player.queue.pop(index - 1)
        await self._ok(ctx, f"Removed **{removed.title}** from the queue.")

    @commands.command(name="move")
    async def move(self, ctx: commands.Context, from_idx: int, to_idx: int):
        """Move a track from one position to another."""
        player = self._player(ctx)
        if not player or len(player.queue) < 2:
            await ctx.reply("Not enough tracks to move.")
            return
        n = len(player.queue)
        if not (1 <= from_idx <= n and 1 <= to_idx <= n):
            await ctx.reply(f"Both positions must be between 1 and {n}.")
            return
        track = player.queue.pop(from_idx - 1)
        player.queue.insert(to_idx - 1, track)
        await self._ok(ctx, f"Moved **{track.title}** to position `{to_idx}`.")

    @commands.command(name="swap")
    async def swap(self, ctx: commands.Context, pos1: int, pos2: int):
        """Swap two tracks in the queue."""
        player = self._player(ctx)
        if not player or len(player.queue) < 2:
            await ctx.reply("Not enough tracks to swap.")
            return
        n = len(player.queue)
        if not (1 <= pos1 <= n and 1 <= pos2 <= n):
            await ctx.reply(f"Both positions must be between 1 and {n}.")
            return
        player.queue[pos1 - 1], player.queue[pos2 - 1] = player.queue[pos2 - 1], player.queue[pos1 - 1]
        await self._ok(ctx, f"Swapped positions `{pos1}` and `{pos2}`.")

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Randomly shuffle the queue."""
        player = self._player(ctx)
        if not player or not player.queue:
            await ctx.reply("The queue is empty.")
            return
        random.shuffle(player.queue)
        await self._ok(ctx, f"Shuffled `{len(player.queue)}` tracks.")

    # ── info / utility ───────────────────────────────────────────────────────── #

    @commands.command(name="nowplaying", aliases=["np", "current"])
    async def nowplaying(self, ctx: commands.Context):
        """Show what's currently playing."""
        player = self._player(ctx)
        if not player or not player.current:
            await ctx.reply("Nothing is playing.")
            return
        artwork  = self._np_art.get(ctx.guild.id)
        req      = player.current_requester or ctx.author
        view     = build_player_view(self, player, player.current, req, artwork)
        await ctx.reply(view=view)

    @commands.command(name="history")
    async def history(self, ctx: commands.Context):
        """Show the last 10 played tracks."""
        player = self._player(ctx)
        if not player or not player.history:
            await ctx.reply("No history yet.")
            return
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay("## Recently Played"))
        c.add_item(_sep())
        lines = [
            f"`{i}.` **{t.title}** — *{t.author}*"
            for i, t in enumerate(player.history[-10:][::-1], 1)
        ]
        c.add_item(discord.ui.TextDisplay("\n".join(lines)))
        await ctx.reply(view=_layout(c))

    @commands.command(name="grab", aliases=["save"])
    async def grab(self, ctx: commands.Context):
        """DM yourself the current song info."""
        player = self._player(ctx)
        if not player or not player.current:
            return
        t = player.current
        try:
            await ctx.author.send(f"**{t.title}**\nArtist: {t.author}\nLink: {t.uri}")
            await ctx.message.add_reaction("📩")
        except discord.Forbidden:
            await ctx.reply("I couldn't DM you — check your privacy settings.")

    # @commands.command(name="testlyrics", aliases=["lyrics", "ly"])
    async def testlyrics(self, ctx: commands.Context, *, query: str | None = None):
        """Fetch lyrics for the current track (or a search query)."""
        player = self._player(ctx)

        # Determine artist / title
        if query:
            parts  = query.split(" - ", maxsplit=1)
            artist = parts[0].strip() if len(parts) == 2 else ""
            title  = parts[-1].strip()
        elif player and player.current:
            artist = player.current.author
            title  = player.current.title
        else:
            await ctx.reply("Nothing is playing. Provide a query like `artist - title`.")
            return

        if not self.session:
            await ctx.reply("HTTP session not available.")
            return

        async with ctx.typing():
            # Try lyrics.ovh
            url = LYRICS_API.format(
                artist = artist.replace("/", " "),
                title  = title.replace("/", " "),
            )
            lyrics = None
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if r.status == 200:
                        data   = await r.json(content_type=None)
                        lyrics = data.get("lyrics", "").strip()
            except Exception as exc:
                logger.debug(f"Lyrics fetch failed: {exc}")

            if not lyrics:
                await ctx.reply(f"Couldn't find lyrics for **{title}**.")
                return

            # Split into ≤1800-char pages so we stay under Discord limits
            chunks  = []
            current = []
            chars   = 0
            for line in lyrics.splitlines():
                addition = len(line) + 1
                if chars + addition > 1800 and current:
                    chunks.append("\n".join(current))
                    current, chars = [], 0
                current.append(line)
                chars += addition
            if current:
                chunks.append("\n".join(current))

            label = f"**{title}**" + (f" — *{artist}*" if artist else "")
            for i, chunk in enumerate(chunks[:3]):  # cap at 3 pages
                header = (f"## Lyrics — {label}\n" if i == 0 else f"## Lyrics (cont.) — {label}\n")
                c = discord.ui.Container()
                c.add_item(discord.ui.TextDisplay(header))
                c.add_item(_sep())
                c.add_item(discord.ui.TextDisplay(f"```\n{chunk}\n```"))
                if i == len(chunks) - 1 or i == 2:
                    c.add_item(_sep(small=True))
                    c.add_item(discord.ui.TextDisplay("*Lyrics provided by lyrics.ovh*"))
                await ctx.send(view=_layout(c, timeout=120))

    # ── loop / autoplay / 24-7 ───────────────────────────────────────────────── #

    @commands.command(name="loop", aliases=["repeat"])
    async def loop(self, ctx: commands.Context, mode: str = ""):
        """Set loop mode: `track`, `queue`, or `off`."""
        player = self._player(ctx)
        if not player:
            return
        m = mode.lower()
        if m in ("track", "song", "1"):
            player.loop_mode = "track"
        elif m in ("queue", "all", "q"):
            player.loop_mode = "queue"
        else:
            player.loop_mode = "none"
        await self._ok(ctx, LOOP_LABELS[player.loop_mode])

    @commands.command(name="autoplay", aliases=["ap"])
    async def autoplay(self, ctx: commands.Context):
        """Toggle autoplay — keeps the music going when the queue ends."""
        player = self._player(ctx)
        if not player:
            player = await self._join(ctx)
            if not player:
                return
        player.autoplay = not player.autoplay
        status = "**ENABLED**" if player.autoplay else "**DISABLED**"
        c = discord.ui.Container()
        c.add_item(discord.ui.TextDisplay(f"Autoplay is now {status}."))
        if player.autoplay:
            c.add_item(discord.ui.TextDisplay(
                "The bot will queue related songs automatically when the queue runs out."
            ))
        await ctx.reply(view=_layout(c))

    @commands.command(name="24/7", aliases=["247", "alwayson"])
    async def alwayson(self, ctx: commands.Context):
        """Toggle whether the bot stays in VC when everyone leaves."""
        player = self._player(ctx)
        if not player:
            return
        player.always_on = not player.always_on
        status = "**ENABLED**" if player.always_on else "**DISABLED**"
        await self._ok(ctx, f"24/7 mode is now {status}.")

    # ── filters ──────────────────────────────────────────────────────────────── #

    @commands.command(name="bassboost", aliases=["bb"])
    async def bassboost(self, ctx: commands.Context, level: str = "medium"):
        """Bass boost: `low`, `medium`, `high`, or `off`."""
        player = self._player(ctx)
        if not player:
            return
        if level.lower() == "off":
            await player.add_filter(mafic.Filter(), label="bass")
            await self._ok(ctx, "Bassboost **OFF**.")
            return
        gain = {"low": 0.15, "medium": 0.25, "high": 0.45}.get(level.lower(), 0.25)
        eq   = mafic.Equalizer(bands=[(0, gain), (1, gain), (2, gain)])
        await player.add_filter(mafic.Filter(equalizer=eq), label="bass")
        await self._ok(ctx, f"Bassboost set to **{level.upper()}**.")

    @commands.command(name="nightcore")
    async def nightcore(self, ctx: commands.Context):
        """Toggle nightcore (speed + pitch up)."""
        player = self._player(ctx)
        if not player:
            return
        await player.add_filter(
            mafic.Filter(timescale=mafic.Timescale(speed=1.2, pitch=1.2)),
            label="nightcore",
        )
        await self._ok(ctx, "Nightcore filter **ENABLED**.")

    @commands.command(name="vaporwave", aliases=["slowed"])
    async def vaporwave(self, ctx: commands.Context):
        """Toggle vaporwave / slowed + reverb effect."""
        player = self._player(ctx)
        if not player:
            return
        await player.add_filter(
            mafic.Filter(timescale=mafic.Timescale(speed=0.8, pitch=0.8)),
            label="vaporwave",
        )
        await self._ok(ctx, "Vaporwave filter **ENABLED**.")

    @commands.command(name="8d")
    async def eight_d(self, ctx: commands.Context):
        """Toggle 8D audio (rotating stereo)."""
        player = self._player(ctx)
        if not player:
            return
        await player.add_filter(
            mafic.Filter(rotation=mafic.Rotation(rotation_hz=0.2)),
            label="8d",
        )
        await self._ok(ctx, "8D audio filter **ENABLED**.")

    @commands.command(name="speed")
    async def speed(self, ctx: commands.Context, val: float):
        """Set playback speed (0.5 – 2.0)."""
        player = self._player(ctx)
        if not player:
            return
        val = _clamp(val, *SPEED_RANGE)
        await player.add_filter(
            mafic.Filter(timescale=mafic.Timescale(speed=val)),
            label="speed",
        )
        await self._ok(ctx, f"Speed set to **{val}x**.")

    @commands.command(name="pitch")
    async def pitch(self, ctx: commands.Context, val: float):
        """Set playback pitch (0.5 – 2.0)."""
        player = self._player(ctx)
        if not player:
            return
        val = _clamp(val, *SPEED_RANGE)
        await player.add_filter(
            mafic.Filter(timescale=mafic.Timescale(pitch=val)),
            label="pitch",
        )
        await self._ok(ctx, f"Pitch set to **{val}**.")

    @commands.command(name="resetfilters", aliases=["clearfilters", "rsf"])
    async def resetfilters(self, ctx: commands.Context):
        """Remove all active audio filters."""
        player = self._player(ctx)
        if not player:
            return
        await player.add_filter(mafic.Filter())
        await self._ok(ctx, "All audio filters **CLEARED**.")

    # ═══════════════════════════ event listeners ════════════════════════════ #

    @commands.Cog.listener()
    async def on_track_start(self, event: mafic.TrackStartEvent):
        player:  MaficPlayer = event.player
        track                = event.track
        gid                  = player.guild.id
        channel              = player.guild.get_channel(player._text_channel_id)
        if not channel:
            return

        # Debounce duplicate start events (Lavalink quirk)
        now  = time.monotonic()
        last = self._last_event.get(gid)
        if last and last[0] == track.id and now - last[1] < 2.0:
            return
        self._last_event[gid] = (track.id, now)

        artwork             = await self._get_artwork(track)
        self._np_art[gid]   = artwork
        await self._send_np(channel, player, track, player.current_requester or "Unknown", artwork)

    @commands.Cog.listener()
    async def on_track_end(self, event: mafic.TrackEndEvent):
        player: MaficPlayer = event.player
        gid                 = player.guild.id

        if event.reason == "REPLACED":
            return

        self._last_event.pop(gid, None)

        # Update history
        qt = QueuedTrack(event.track, player.current_requester or "Autoplay")
        player.history.append(qt)
        if len(player.history) > 20:
            player.history.pop(0)

        # Loop: track
        if player.loop_mode == "track" and not player.skipping:
            await self._play(player, qt)
            return

        player.skipping = False

        # Loop: queue — re-append completed track
        if player.loop_mode == "queue":
            player.queue.append(qt)

        # Normal next
        if player.queue:
            await self._play(player, player.queue.pop(0))
            return

        # Autoplay
        if player.autoplay:
            next_qt = await self._autoplay_next(player, event.track)
            if next_qt:
                await self._play(player, next_qt)
                return

        # Queue empty
        await self._delete_np(gid)
        self._np_art.pop(gid, None)

    async def _autoplay_next(self, player: MaficPlayer, last: mafic.Track) -> QueuedTrack | None:
        """Try to find a non-duplicate autoplay track via YouTube Mix or similarity search."""
        # Attempt 1: YouTube Mix
        video_id = None
        if "youtube.com" in last.uri or "youtu.be" in last.uri:
            m = _YT_ID_RE.search(last.uri)
            if m:
                video_id = m.group(1)

        if video_id:
            mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
            try:
                results = await asyncio.wait_for(player.fetch_tracks(mix_url), timeout=5.0)
                if isinstance(results, mafic.Playlist):
                    for t in results.tracks:
                        if not self._is_dupe(t, last, player):
                            return QueuedTrack(t, "Autoplay")
            except Exception:
                pass

        # Attempt 2: Similarity search
        for query in (
            f"songs similar to {last.title} {last.author}",
            f"{last.title} {last.author} similar",
        ):
            try:
                results = await asyncio.wait_for(
                    player.fetch_tracks(query, search_type=mafic.SearchType.YOUTUBE_MUSIC),
                    timeout=5.0,
                )
                tracks = results.tracks if isinstance(results, mafic.Playlist) else (results or [])
                for t in tracks:
                    if not self._is_dupe(t, last, player):
                        return QueuedTrack(t, "Autoplay")
            except Exception as exc:
                logger.debug(f"Autoplay search failed: {exc}")

        return None

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after:  discord.VoiceState,
    ):
        if member.id == self.bot.user.id:
            return
        player: MaficPlayer = member.guild.voice_client  # type: ignore
        if not player or player.always_on:
            return
        if before.channel and before.channel.id == player.channel.id:
            if not any(not m.bot for m in before.channel.members):
                await asyncio.sleep(10)
                if player.channel and not any(not m.bot for m in player.channel.members):
                    gid = member.guild.id
                    await player.disconnect()
                    await self._delete_np(gid)
                    self._np_locks.pop(gid, None)
                    self._last_event.pop(gid, None)
                    self._np_art.pop(gid, None)

    # ═══════════════════════════ button callbacks ═══════════════════════════ #

    async def _btn_prev(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client  # type: ignore
        if not await self._check_btn(interaction, player):
            return
        if not player.history:
            await interaction.response.send_message("No previous tracks.", ephemeral=True)
            return
        prev = player.history.pop()
        if player.current:
            player.queue.insert(0, QueuedTrack(player.current, player.current_requester or "Unknown"))
        await self._play(player, prev)
        await interaction.response.send_message(f"Playing previous: **{prev.title}**", ephemeral=True)

    async def _btn_pause(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client  # type: ignore
        if not await self._check_btn(interaction, player):
            return
        if not player.current:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        if player.paused:
            await player.resume()
        else:
            await player.pause()
        gid     = interaction.guild_id
        artwork = self._np_art.get(gid)
        req     = player.current_requester or "Autoplay"
        await interaction.response.edit_message(
            view=build_player_view(self, player, player.current, req, artwork)
        )

    async def _btn_skip(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client  # type: ignore
        if not await self._check_btn(interaction, player):
            return
        if not player.current:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        player.skipping = True
        await player.stop()
        await interaction.response.send_message("Skipped!", ephemeral=True)

    async def _btn_loop(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client  # type: ignore
        if not await self._check_btn(interaction, player):
            return
        if not player.current:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        idx             = LOOP_CYCLE.index(player.loop_mode)
        player.loop_mode = LOOP_CYCLE[(idx + 1) % len(LOOP_CYCLE)]
        gid             = interaction.guild_id
        artwork         = self._np_art.get(gid)
        req             = player.current_requester or "Autoplay"
        await interaction.response.edit_message(
            view=build_player_view(self, player, player.current, req, artwork)
        )

    async def _btn_stop(self, interaction: discord.Interaction):
        player: MaficPlayer = interaction.guild.voice_client  # type: ignore
        if not await self._check_btn(interaction, player):
            return
        if not player:
            await interaction.response.send_message("Not connected.", ephemeral=True)
            return
        gid = interaction.guild_id
        player.queue.clear()
        await player.disconnect()
        await self._delete_np(gid)
        self._np_locks.pop(gid, None)
        self._last_event.pop(gid, None)
        self._np_art.pop(gid, None)
        await interaction.response.send_message("Disconnected.", ephemeral=True)


# ─────────────────────────────── setup ────────────────────────────────────── #

# async def setup(bot):
#     logger.info("Loading MusicCommand cog…")
#     await bot.add_cog(MusicCommand(bot))
#     logger.info("MusicCommand cog loaded ✓")