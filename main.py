import discord
from discord.ext import commands
from discord.ext import tasks
import logging
from dotenv import load_dotenv
import asyncio
from google import genai
from google.genai.types import Part
from datetime import datetime, timezone, timedelta
import jishaku
import aiohttp
from groq import Groq
import json
from cerebras.cloud.sdk import Cerebras
from google.cloud import firestore 
from google.oauth2 import service_account
from commands.loader import CommandLoader
from help_command import PaginatedHelpCommand
import sys
from openai import OpenAI, AsyncOpenAI

# Load environment variables FIRST before importing config
load_dotenv(dotenv_path='.env', verbose=True)

# Now import config after environment variables are loaded
from config import config

# Print configuration summary on startup
config.print_config_summary()

# Validate required configuration
missing_keys = config.validate_required_keys()
if missing_keys:
    print(f"❌ Missing required environment variables: {', '.join(missing_keys)}")
    print("Please check your .env file and ensure all required keys are set.")
    exit(1)

# !!! DATABASE INITIALIZATION !!!
credentials_json_string = config.FIREBASE_CREDENTIALS
credentials_info = json.loads(credentials_json_string)
credentials = service_account.Credentials.from_service_account_info(credentials_info)
database = firestore.Client(
    project=config.FIREBASE_PROJECT_ID,
    credentials=credentials,
    database=config.FIREBASE_DATABASE_ID
)

# genai setup (new SDK)
gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
gemini_model = config.GEMINI_MODEL

# groq setup
groq_client = Groq(api_key=config.GROQ_API_KEY)
groq_model = config.GROQ_MODEL

# cerebras setup
cerebras_client = Cerebras(api_key=config.CEREBRAS_API_KEY)
cerebras_model = config.CEREBRAS_MODEL

# messa ai openai client setup
messa_ai_client = AsyncOpenAI(
    base_url=config.MESSA_AI_API_URL,
    api_key=config.MESSA_AI_API_KEY
)

# semaphore — controls how many requests can run at once
ai_semaphore = asyncio.Semaphore(config.AI_SEMAPHORE_LIMIT)

# --- discord setup ---
token = config.DISCORD_TOKEN

# Setup logging for both discord and bot
discord_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
bot_handler = logging.FileHandler(filename="bot.log", encoding="utf-8", mode="w")

# Configure discord.py logging
discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.INFO)
discord_logger.addHandler(discord_handler)

# Configure bot logging
bot_logger = logging.getLogger("bot")
bot_logger.setLevel(logging.INFO)
bot_logger.addHandler(bot_handler)

# Also log to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
bot_logger.addHandler(console_handler)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

# prefixes
def get_prefixes(bot, message):
    # Get prefixes from config
    prefixes = config.BOT_PREFIXES.copy()
    prefixes.append(f"<@{bot.user.id}> ")
    prefixes.append(f"<@!{bot.user.id}> ")
    return prefixes

# --- General setup ---
bot = commands.Bot(command_prefix=get_prefixes, intents=intents, allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), max_messages=None)
bot.owner_ids = config.OWNER_IDS

# -- help command --
bot.help_command = PaginatedHelpCommand()

# -- jishaku --
async def setup_hooks():
    await bot.load_extension("jishaku")

bot.setup_hook = setup_hooks

# debug
test_guild = discord.Object(id=config.TEST_GUILD_ID)
debug_channel_id = config.DEBUG_CHANNEL_ID

# -- logging --
class DiscordLogHandler(logging.Handler):
    def __init__(self, bot, channel_id: int):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
        self._lock = asyncio.Lock()
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None

    async def send_log(self, message: str):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print(f"⚠️ Log channel {self.channel_id} not found.")
            return

        if "rate limit" in message.lower():
            print("⚠️ Skipping log to avoid recursive rate-limit loop.")
            return

        if len(message) > 1900:
            message = message[:1900] + "\n... (truncated)"

        async with self._lock:
            try:
                await channel.send(f"```py\n{message}\n```")
            except discord.HTTPException as e:
                print(f"⚠️ Could not send log: {e}")

    def emit(self, record):
        try:
            msg = self.format(record)
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.send_log(msg), self.loop)
            else:
                # Fallback if there is no loop or loop is closed
                pass
        except Exception as e:
            print(f"⚠️ Log handler error: {e}")

# Global variables that commands might need (from config)
loading_emoji = config.LOADING_EMOJI
join_emoji = config.JOIN_EMOJI
left_emoji = config.LEFT_EMOJI
inactivity_limit = timedelta(minutes=config.THREAD_INACTIVITY_LIMIT)
max_thread_history = config.MAX_THREAD_HISTORY
max_embed_chars = config.MAX_EMBED_CHARS
max_message_length = config.MAX_MESSAGE_LENGTH
max_file_size = config.MAX_FILE_SIZE
thread_histories = {}
user_cooldowns = {}
afk_users = {}
session: aiohttp.ClientSession | None = None
shutdown_notified = False

# Attach global variables to bot for command access
bot.database = database
bot.gemini_client = gemini_client
bot.gemini_model = gemini_model
bot.groq_client = groq_client
bot.groq_model = groq_model
bot.cerebras_client = cerebras_client
bot.cerebras_model = cerebras_model
bot.messa_ai_client = messa_ai_client
bot.ai_semaphore = ai_semaphore
bot.user_cooldowns = user_cooldowns
bot.thread_histories = thread_histories
bot.afk_users = afk_users
bot.max_embed_chars = max_embed_chars
bot.max_message_length = max_message_length
bot.max_file_size = max_file_size
bot.join_emoji = join_emoji
bot.left_emoji = left_emoji
bot.chatbot_thingy_data = {}
bot.j_count = 0
bot.ai_toggle_users = {}
bot.welcome_channels_data = {}
bot.farewell_channels_data = {}
bot.no_prefix_users = {}

async def notify_shutdown(message: str = "🛑 Bot is closing.") -> None:
    """Send a shutdown notification to the debug channel once."""
    global shutdown_notified
    if shutdown_notified:
        return

    shutdown_notified = True
    bot_logger = logging.getLogger("bot")

    try:
        channel = bot.get_channel(debug_channel_id)
        if channel:
            try:
                await channel.send(message)
                bot_logger.info("Sent shutdown message to debug channel")
            except Exception as exc:
                bot_logger.error(f"Failed to send shutdown message: {exc}")
        else:
            bot_logger.warning("Debug channel not found during shutdown notification")
    except Exception as e:
        bot_logger.error(f"Error in notify_shutdown: {e}")

# -- auto thread deletion --
@tasks.loop(minutes=config.CLEANUP_INTERVAL)
async def cleanup_inactive_threads():
    now = datetime.now(timezone.utc)
    to_delete = []

    for thread_id, data in list(thread_histories.items()):
        last_active = data["last_activity"]
        if now - last_active > inactivity_limit:
            try:
                thread = bot.get_channel(thread_id)
                if thread:
                    def format_duration(td: timedelta) -> str:
                        total_seconds = int(td.total_seconds())
                        minutes = total_seconds // 60
                        return f"{minutes}"
                    
                    await thread.send(f"⏳ This Gemini thread has been inactive for {format_duration(inactivity_limit)} minutes and will be closed.")
                    await thread.delete()
            except Exception as e:
                print(f"Failed to delete thread {thread_id}: {e}")
            finally:
                to_delete.append(thread_id)

    for tid in to_delete:
        del thread_histories[tid]
#
@bot.event
async def on_command_error(ctx, error):
    """Global error handler for all commands."""
    if isinstance(error, discord.ext.commands.CommandNotFound):
        return  # Suppress CommandNotFound errors
    
    original = getattr(error, 'original', error)
    error_type = type(original).__name__
    error_msg = str(original)
    full_error = f"{error_type}: {error_msg}" if error_msg else error_type
    
    embed = discord.Embed(
            title="❌ Command Error",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
    
    # Format the error based on type
    if isinstance(original, commands.MissingRequiredArgument):
        embed.description = f"Missing required argument: **{original.param.name}**"
        embed.add_field(
            name="Usage",
            value=f"`{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
            inline=False
        )
    
    elif isinstance(original, commands.BadArgument):
        embed.description = f"Invalid argument: {str(original)}"
    
    elif isinstance(original, commands.MissingPermissions):
        embed.description = f"You're missing permissions: **{', '.join(original.missing_permissions)}**"
    
    elif isinstance(original, commands.BotMissingPermissions):
        embed.description = f"I'm missing permissions: **{', '.join(original.missing_permissions)}**"
    
    elif isinstance(original, commands.NotOwner):
        embed.description = "This command is only available to the bot owner."
    
    elif isinstance(original, commands.CommandOnCooldown):
        embed.description = f"Command on cooldown. Try again in **{original.retry_after:.1f}** seconds."
    
    elif isinstance(original, commands.NoPrivateMessage):
        embed.description = "This command cannot be used in DMs."
    
    elif isinstance(original, discord.Forbidden):
        embed.description = "I don't have permission to do that. Check my role permissions."
    
    elif isinstance(original, discord.NotFound):
        embed.description = "Something wasn't found. The message or channel may have been deleted."
    
    else:
        # Unknown error - show the error message
        full_error = full_error[:1900]
        embed.description = f"```py\n{full_error}\n```"
        embed.add_field(
            name="Need Help?",
            value=f"[Join our support server](https://discord.gg/hf8MxGKPEn)",
            inline=False
        )
    
    # Add footer with command info
    embed.set_footer(
        text=f"Command: {ctx.prefix}{ctx.command.qualified_name}" if ctx.command else "Unknown",
        icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
    )
    
    # Send the error message
    try:
        await ctx.reply(embed=embed, ephemeral=True)
    except discord.HTTPException:
        await ctx.send(f"❌ Error: {embed.description[:100]}")
                                                   
    # Log to console for debugging
    print(f"Error in {ctx.command}: {full_error}")
    raise error

# -- on_ready --
@bot.event
async def on_ready():
    bot_logger = logging.getLogger("bot")
    
    print(f"✅ Started, logged in as {bot.user}")
    
    channel = bot.get_channel(debug_channel_id)
    if channel:
        await channel.send("✅ Bot is ready.")
    else:
        print(f"⚠️ Debug channel {debug_channel_id} not found.")
    
    cleanup_inactive_threads.start()
    bot_logger.info("✅ Started cleanup_inactive_threads task")

    # logging 
    logger = logging.getLogger("discord")
    logger.setLevel(logging.INFO)
    if not any(isinstance(h, DiscordLogHandler) for h in logger.handlers):
        discord_handler = DiscordLogHandler(bot, debug_channel_id)
        discord_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s: %(message)s"))
        logger.addHandler(discord_handler)
        bot_logger.info("✅ Added Discord log handler")

    bot_logger_discord = logging.getLogger("bot")
    bot_logger_discord.setLevel(logging.INFO)
    if not any(isinstance(h, DiscordLogHandler) for h in bot_logger_discord.handlers):
        discord_handler2 = DiscordLogHandler(bot, debug_channel_id)
        discord_handler2.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s: %(message)s"))
        bot_logger_discord.addHandler(discord_handler2)
        bot_logger.info("✅ Added Bot log handler")

    # cache database data
    for doc_snapshot in database.collection("chatbot thingy data").get():
        bot.chatbot_thingy_data[doc_snapshot.id] = doc_snapshot.to_dict()
    
    bot.j_count = database.collection("do j").document("j count").get().to_dict()["j"]

    for doc_snapshot in database.collection("ai toggle users").get():
        bot.ai_toggle_users[doc_snapshot.id] = doc_snapshot.to_dict()

    for doc_snapshot in database.collection("welcome channels data").get():
        bot.welcome_channels_data[doc_snapshot.id] = doc_snapshot.to_dict()

    for doc_snapshot in database.collection("farewell channels data").get():
        bot.farewell_channels_data[doc_snapshot.id] = doc_snapshot.to_dict()

    # Load no-prefix users
    try:
        np_doc = database.collection("bot_settings").document("no_prefix_users").get()
        np_data = np_doc.to_dict()
        bot.no_prefix_users = np_data.get("users", {}) if np_data else {}
        bot_logger.info(f"Loaded {len(bot.no_prefix_users)} no-prefix users")
    except Exception as e:
        bot_logger.error(f"Error loading no-prefix users: {e}")
        bot.no_prefix_users = {}

    bot_logger.info("✅ Cached database data successfully")

    # custom rpc (from config)
    status_type = getattr(discord.ActivityType, config.BOT_STATUS_TYPE, discord.ActivityType.watching)
    
    activity = discord.Activity(
        name=config.BOT_STATUS_NAME,
        type=status_type,
        state=config.BOT_STATUS_STATE
    )
    await bot.change_presence(activity=activity)
    print(f"📝 Set bot status: {config.BOT_STATUS_TYPE} {config.BOT_STATUS_NAME}")

    global session
    if session is None:
        session = aiohttp.ClientSession()
        bot.session = session
        bot_logger.info("✅ Created aiohttp session")
    
    # Load all commands
    loader = CommandLoader(bot)
    await loader.load_all_commands()
    bot_logger.info("✅ Loaded all command modules")
    
    try:
        synced = await bot.tree.sync(guild=test_guild)
        print(f"⚡ Synced {len(synced)} commands to test guild {test_guild.id}")
        asyncio.create_task(sync_global())
    except Exception as e:
        print(f"⚠️ Failed to sync commands: {e}")

async def sync_global():
    bot_logger = logging.getLogger("bot")
    try:
        synced = await bot.tree.sync()
        print(f"🌍 Synced {len(synced)} commands globally (may take up to 1 hour)")
    except Exception as e:
        print(f"❌ Global sync failed: {e}")

# -- utility to split long text into 1990-char chunks --
def split_message(text: str, limit: int = 1990):
    #split long text into chunks, without breaking code blocks
    chunks = []
    in_codeblock = False
    while len(text) > limit:
        # prefer to split at a newline
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1 or split_at < limit // 2:
            split_at = limit
        chunk = text[:split_at]
        text = text[split_at:]
        # count fences in this chunk
        if chunk.count("```") % 2 == 1:
            chunk += "\n```"
            in_codeblock = True
        else:
            in_codeblock = False
        chunks.append(chunk)
        # if still inside, start next chunk with a reopen
        if in_codeblock and not text.lstrip().startswith("```"):
            text = "```\n" + text.lstrip()
            in_codeblock = False
    # handle final remainder
    if text:
        if in_codeblock:
            # Close any unclosed block
            if not text.rstrip().endswith("```"):
                text += "\n```"
            in_codeblock = False
        chunks.append(text)
    return chunks

# - format duration -
def format_duration(td: timedelta) -> str:
    # converts a timedelta object into a cleaner string
    total_seconds = int(td.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    # always show seconds unless the duration is 0
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
        
    return " ".join(parts)

# Basic message responses (keeping some simple ones in main)
@bot.event
async def on_message(message):
    if message.guild:
        if message.channel.id == 1438886174809788496:
            if message.author.bot:
                print("Commit detected, restarting")
                sys.exit(1)

    if message.author == bot.user:
        return

    # Check if user has no-prefix permission
    no_prefix_users = getattr(bot, 'no_prefix_users', {})
    user_id = str(message.author.id)
    has_no_prefix = user_id in no_prefix_users
    
    # For no-prefix users, we need to modify the message content to include a prefix
    if has_no_prefix and not message.content.startswith(tuple(await bot.get_prefix(message))):
        # Get the first prefix and add it to the message content
        prefixes = await bot.get_prefix(message)
        first_prefix = prefixes[0] if prefixes else '!'
        
        # Create a new message with prefix
        old_content = message.content
        message.content = first_prefix + old_content
        
        # Process the modified message
        await bot.process_commands(message)
        
        # Restore original content and return to prevent auto-response
        message.content = old_content
    else:
        # Normal command processing
        await bot.process_commands(message)

    if message.content.startswith(tuple(await bot.get_prefix(message))):
        return

    # Chatbot Thingy auto-response logic (only when no commands are used)
    # Check if this is a chatbot command to prevent duplicate responses
    prefixes = await bot.get_prefix(message)
    chatbot_commands = ["chatbot-thingy", "ct", "chat", "chatbot_thingy"]
    for prefix in prefixes:
        for cmd in chatbot_commands:
            if message.content.startswith(f"{prefix}{cmd}"):
                return
    
    if message.guild:
        doc_ref = database.collection("chatbot thingy data").document(str(message.guild.id))
        if bot.chatbot_thingy_data.get(str(message.guild.id)):
            if bot.chatbot_thingy_data[str(message.guild.id)]["channel id"] == message.channel.id:
                if bot.ai_toggle_users.get(str(message.author.id)) and bot.ai_toggle_users[str(message.author.id)]["toggle"] == False:
                    return
                timestamp = datetime.now(timezone.utc)
                await asyncio.to_thread(doc_ref.update, {"histories": firestore.ArrayUnion([{"message": f"{message.author.name}: {message.content}", "timestamp": timestamp}])})
                bot.chatbot_thingy_data[str(message.guild.id)]["histories"].append({"message": f"{message.author.name}: {message.content}", "timestamp": timestamp})
                data = bot.chatbot_thingy_data[str(message.guild.id)]["histories"]
                # Format histories in new bracketed context format
                formatted_context = "[context: "
                for item in data:
                    if "message" in item:
                        formatted_context += f"{item['message']} "
                formatted_context += "/end]"
                
                system_prompt = """You're a funny chatbot on discord named Chatbot Thingy that chat with the user,
your primary language is english, be casual, don't use characters like ', don't capitalize your words,
try to keep your response short enough so it's funny

you can see some structures like:
- username: message
that's the user's message, and:
- chatbot thingy: message
that's your message,
also you don't need to add \"chatbot thingy:\" at the start of your message,

follow the brackets and understand the context, only reply to the message which is requested.
Context format: [context: neuvi: ... assistant: ... 2012hhh2012: ... /end] reply to neuvi: hi
ok thats all, now goodluck!"""

                # attachments support
                try:
                    # build gemini contents (can be text + files)
                    contents = [f"{message.author.name}: {message.content}" or f"{message.author.name}: See the files:"]

                    for attachment in message.attachments:
                        if attachment.size > 20 * 1024 * 1024:
                            return await message.reply(f"❌ File **{attachment.filename}** is too large. Please keep files under 20MB.", ephemeral=True)
                        
                        data = await attachment.read()
                        mime_type = attachment.content_type
                        
                        # override specific text encodings (like TIS-620) to ensure API compatibility
                        if mime_type and mime_type.startswith("text/"):
                            mime_type = 'text/plain'
                        else:
                            # fallback for non-text files or unknown types
                            mime_type = mime_type or "application/octet-stream"
                        
                        attachment_part = Part.from_bytes(
                            data=data,
                            mime_type=mime_type
                        )
                        
                        contents.append(attachment_part)
                    
                except Exception as e:
                    return

                # Cooldown check
                now = datetime.now(timezone.utc)
                user_id = message.author.id
                if user_id in user_cooldowns:
                    last_used = user_cooldowns[user_id]
                    if now - last_used < timedelta(seconds=config.GEMINI_COOLDOWN):
                        return await message.reply(f"⏳ Please wait {config.GEMINI_COOLDOWN} seconds between requests.")
                user_cooldowns[user_id] = now

                async with message.channel.typing():
                    try:
                        # Use new bracketed context format
                        async with ai_semaphore:
                            response = await asyncio.to_thread(
                                bot.gemini_client.models.generate_content,
                                model=bot.gemini_model,
                                contents=formatted_context + f"\nreply to {message.author.name}: " + message.content,
                                config=genai.types.GenerateContentConfig(
                                    system_instruction=system_prompt,
                                    tools=[{"google_search": {} }]
                                )
                            )

                    
                        # save chatbot thingy response
                        await asyncio.to_thread(doc_ref.update, {"histories": firestore.ArrayUnion([{"message": f"Chatbot Thingy: {response.text}", "timestamp": timestamp}])})
                        bot.chatbot_thingy_data[str(message.guild.id)]["histories"].append({"message": f"Chatbot Thingy: {response.text}", "timestamp": timestamp})

                        if not response.text:
                            await message.reply("⚠️ Chatbot Thingy response was empty after strip.")
                            return

                        chunks = split_message(response.text)
                        await message.reply(chunks[0])

                        if len(chunks) > 1:
                            for chunk in chunks[1:]:
                                await asyncio.sleep(0.5)
                                await message.channel.send(chunk)
                        return

                    except Exception as e:
                        print(f"Chatbot Thingy error: {e}")
                        await asyncio.to_thread(doc_ref.update, {"histories": firestore.ArrayRemove([{"message": f"{message.author.name}: {message.content}", "timestamp": timestamp}])})
                        bot.chatbot_thingy_data[str(message.guild.id)]["histories"].remove({"message": f"{message.author.name}: {message.content}", "timestamp": timestamp})
                        await message.reply(f"❌ Error: {e}")
                        return

    if has_no_prefix:
        return

    # Auto responses
    if message.content.lower() == "hi":
        await message.reply(f"Hello {message.author.mention}!")  

    if message.content.lower() == "hello":
        await message.reply(f"Hi {message.author.mention}!")

    if message.content.lower() in ["bye", "goodbye", "cya", "see you later"]:
        await message.reply(f"Goodbye {message.author.mention}!")

    if message.content.lower().startswith("bruh"):
        await message.reply(f"bruh")
    
    if message.content.lower().startswith(("stfu", "shut up", "shutup")):
        await message.reply(f"Ayo guys we're gonna have a fight to watch 🍿:D")

    if message.content.lower() in ["lmao", "lmfao"]:
        await message.reply("lol")

    if message.content.lower() == "lol":
        await message.reply("lmao")

    if message.content.strip() == bot.user.mention:
        await message.reply(f"Hi {message.author.mention}! You can check my commands using `b?help` and `/`")

    if not message.content.startswith(bot.user.mention) and bot.user.mention in message.content:
        await message.reply(f"Hi {message.author.mention}! You can check my commands using `b?help` and `/`")

    if any(phrase in message.content.lower() for phrase in ["6-7", "6 7", "six seven", "six-seven"]):
        await message.reply("67 🔥")

# All commands are now migrated to cogs

async def run_bot():
    bot_logger = logging.getLogger("bot")
    global session

    try:
        await bot.start(token, reconnect=True)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("Shutdown signal received; notifying shutdown.")
        await notify_shutdown()
    finally:
        # Clean up in the correct order
        bot_logger.info("Starting cleanup...")
        
        # 1. Stop background tasks
        cleanup_inactive_threads.cancel()
        
        # 2. Close aiohttp session properly
        if session and not session.closed:
            await session.close()
            bot_logger.info("Closed aiohttp session")
        
        # 3. Close the bot
        if not bot.is_closed():
            await bot.close()
            bot_logger.info("Closed bot connection")
        
        # 4. Give time for cleanup
        await asyncio.sleep(0.5)
        
        bot_logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
