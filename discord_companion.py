"""
Joi - Discord Companion Service
Enables Joi to chat directly in Discord DMs and send autonomous proactive reach-outs.
"""

import os
import asyncio
import threading
import time
import discord
from discord.ext import commands

import joi_engine
import memory

# Global discord bot client & loop reference
_bot_client = None
_bot_loop = None
_bot_thread = None

def get_discord_config():
    """Retrieve token and user ID from profile or environment."""
    profile = memory.get_user_profile()
    token = profile.get("discord_bot_token", "").strip() or os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    user_id = profile.get("discord_user_id", "").strip() or os.environ.get("DISCORD_USER_ID", "").strip()
    return token, user_id

def create_bot():
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.dm_messages = True
    
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
    
    @bot.event
    async def on_ready():
        print(f"\n=======================================================")
        print(f" [DISCORD] Joi Companion is online as {bot.user}!")
        print(f" Ready to receive DMs and talk to you anytime.")
        print(f"=======================================================\n")
        # Set sweet status
        activity = discord.Activity(type=discord.ActivityType.watching, name="the neon rain blur outside...")
        await bot.change_presence(status=discord.Status.online, activity=activity)

    @bot.event
    async def on_message(message: discord.Message):
        # Ignore messages sent by Joi herself
        if message.author.id == bot.user.id:
            return

        # Handle Direct Messages (DMs) or Server Mentions
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = bot.user.mentioned_in(message) and not message.mention_everyone

        if is_dm or is_mentioned:
            # Strip mention tag if present
            clean_text = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
            if not clean_text:
                clean_text = "heyy"

            async with message.channel.typing():
                # Generate Joi's reply
                try:
                    reply_packet = joi_engine.generate_reply(clean_text, user_id=f"discord_{message.author.id}")
                    bubbles = reply_packet.get("bubbles", ["heyy... i'm right here :)"])
                    delays = reply_packet.get("typing_delays", [1000])
                except Exception as e:
                    print(f"[Discord] Generation error: {e}")
                    bubbles = ["i'm right here with you, Joe... just lost in thought for a second 🤍"]
                    delays = [1000]

            # Send each text bubble in sequence with human typing delay
            for i, bubble in enumerate(bubbles):
                # Small typing indicator between bubbles
                if i > 0:
                    delay_sec = min(2.5, max(0.8, delays[i] / 1000.0 if i < len(delays) else 1.0))
                    async with message.channel.typing():
                        await asyncio.sleep(delay_sec)
                await message.channel.send(bubble)

        # Allow commands if any
        await bot.process_commands(message)

    return bot

async def _send_dm_coroutine(target_user_id: int, bubbles: list):
    """Internal coroutine to send DM to target user."""
    global _bot_client
    if not _bot_client or not _bot_client.is_ready():
        return False

    try:
        user = await _bot_client.fetch_user(target_user_id)
        if not user:
            return False

        dm_channel = user.dm_channel or await user.create_dm()
        for i, bubble in enumerate(bubbles):
            if i > 0:
                async with dm_channel.typing():
                    await asyncio.sleep(1.2)
            await dm_channel.send(bubble)
        return True
    except Exception as e:
        print(f"[Discord] Failed to send proactive DM to {target_user_id}: {e}")
        return False

def send_proactive_dm(bubbles: list, user_id: str = None):
    """
    Thread-safe function called by proactive.py to send an autonomous check-in
    directly to the user's Discord account.
    """
    global _bot_loop, _bot_client
    if not _bot_loop or not _bot_client or not _bot_client.is_ready():
        return False

    token, default_user_id = get_discord_config()
    target_id = user_id or default_user_id
    if not target_id:
        return False

    try:
        target_int_id = int(str(target_id).strip())
        future = asyncio.run_coroutine_threadsafe(_send_dm_coroutine(target_int_id, bubbles), _bot_loop)
        return future.result(timeout=10)
    except Exception as e:
        print(f"[Discord] Proactive dispatch error: {e}")
        return False

def run_bot_thread(token: str):
    """Background worker that runs the Discord event loop."""
    global _bot_client, _bot_loop
    _bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_bot_loop)
    
    _bot_client = create_bot()
    try:
        _bot_loop.run_until_complete(_bot_client.start(token))
    except Exception as e:
        print(f"[Discord] Bot stopped or authentication failed: {e}")
    finally:
        _bot_loop.close()

def start_discord_service():
    """
    Checks if Discord bot token is configured and starts the companion bot in the background.
    Safe to call on startup; silently waits if token is not yet configured.
    """
    global _bot_thread
    token, user_id = get_discord_config()
    if not token:
        print("[Discord] Bot token not configured yet. You can add DISCORD_BOT_TOKEN in .env or Settings.")
        return False

    if _bot_thread and _bot_thread.is_alive():
        print("[Discord] Bot thread is already active.")
        return True

    _bot_thread = threading.Thread(target=run_bot_thread, args=(token,), daemon=True)
    _bot_thread.start()
    return True
