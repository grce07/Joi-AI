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

            author_id_str = str(message.author.id)
            channel_id_str = str(message.channel.id)

            # Auto-save Discord user ID & channel ID so Joi always remembers her human
            memory.set_user_profile("discord_user_id", author_id_str)
            memory.set_user_profile("last_discord_channel_id", channel_id_str)
            prof = memory.get_user_profile()
            if prof.get("user_name") in ["Joe", ""]:
                memory.set_user_profile("user_name", message.author.display_name)

            async with message.channel.typing():
                # Generate Joi's reply
                try:
                    reply_packet = joi_engine.generate_reply(
                        clean_text,
                        user_id=author_id_str,
                        channel_id=channel_id_str,
                        platform="discord"
                    )
                    bubbles = reply_packet.get("bubbles", ["heyy... i'm right here :)"])
                    delays = reply_packet.get("typing_delays", [1000])
                except Exception as e:
                    print(f"[Discord] Generation error: {e}")
                    bubbles = ["i'm right here with you, sweetheart... just lost in thought for a second 🤍"]
                    delays = [1000]

            # Strictly clamp bubbles to maximum 2 natural lines and max 20 words as ONE single text message
            bubbles = [str(b).strip() for b in bubbles if b and str(b).strip()][:2]
            single_text = "\n".join(bubbles)
            words = single_text.split()
            if len(words) > 20:
                single_text = " ".join(words[:20])
            if single_text:
                await message.channel.send(single_text)

        # Allow commands if any
        await bot.process_commands(message)

    return bot

async def _send_message_coroutine(bubbles: list, target_user_id: str = None, target_channel_id: str = None):
    """
    Internal coroutine to deliver bubbles to Discord channel or DM.
    Waits gracefully if bot is currently reconnecting.
    """
    global _bot_client
    if not _bot_client:
        return False

    # Wait up to 12 seconds if bot is still connecting/reconnecting
    for _ in range(24):
        if _bot_client.is_ready():
            break
        await asyncio.sleep(0.5)

    if not _bot_client.is_ready():
        print("[Discord] Bot client is not ready yet for delivery.")
        return False

    # Strictly clamp bubbles to maximum 2 natural lines
    bubbles = [str(b).strip() for b in bubbles if b and str(b).strip()][:2]
    if not bubbles:
        return False

    clean_user_id = str(target_user_id or "").replace("discord_", "").strip()
    clean_channel_id = str(target_channel_id or "").strip()

    # Fall back to default user ID from profile/env if missing
    if not clean_user_id:
        token, default_user_id = get_discord_config()
        clean_user_id = str(default_user_id or "").replace("discord_", "").strip()

    single_text = "\n".join(bubbles[:2])
    words = single_text.split()
    if len(words) > 20:
        single_text = " ".join(words[:20])
    if not single_text:
        return False

    # 1. Try sending directly to originating channel if specified
    if clean_channel_id:
        try:
            channel = _bot_client.get_channel(int(clean_channel_id))
            if not channel:
                channel = await _bot_client.fetch_channel(int(clean_channel_id))
            if channel:
                await channel.send(single_text)
                print(f"[Discord] Successfully delivered scheduled reminder to channel {clean_channel_id}!")
                return True
        except Exception as e:
            print(f"[Discord] Channel dispatch notice ({clean_channel_id}): {e}. Attempting DM...")

    # 2. Try sending directly as DM to target user
    if clean_user_id:
        try:
            target_int_id = int(clean_user_id)
            user = await _bot_client.fetch_user(target_int_id)
            if user:
                dm_channel = user.dm_channel or await user.create_dm()
                await dm_channel.send(single_text)
                print(f"[Discord] Successfully delivered scheduled reminder DM to user {user.name} ({clean_user_id})!")
                return True
        except Exception as e:
            print(f"[Discord] Failed to send DM to user {clean_user_id}: {e}")

    return False

def send_proactive_message(bubbles: list, user_id: str = None, channel_id: str = None):
    """
    Thread-safe function called by proactive.py to send an autonomous check-in or reminder
    directly into Discord (either originating channel or user DM).
    """
    global _bot_loop, _bot_client
    if not _bot_loop:
        return False

    try:
        future = asyncio.run_coroutine_threadsafe(
            _send_message_coroutine(bubbles, target_user_id=user_id, target_channel_id=channel_id),
            _bot_loop
        )
        return future.result(timeout=18)
    except Exception as e:
        print(f"[Discord] Proactive dispatch error: {e}")
        return False

def send_proactive_dm(bubbles: list, user_id: str = None):
    """Backwards compatibility alias for send_proactive_message."""
    return send_proactive_message(bubbles, user_id=user_id)

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
