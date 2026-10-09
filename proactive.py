import os
import sys
import time
import threading
import random
import subprocess
from datetime import datetime, timedelta
import memory
import time_parser

try:
    import discord_companion
except Exception:
    discord_companion = None

# Global list of active SSE subscriber queues
_sse_subscribers = []
_subscribers_lock = threading.Lock()

def register_sse_client(queue_obj):
    with _subscribers_lock:
        _sse_subscribers.append(queue_obj)

def unregister_sse_client(queue_obj):
    with _subscribers_lock:
        if queue_obj in _sse_subscribers:
            _sse_subscribers.remove(queue_obj)

def broadcast_sse(event_type, data):
    with _subscribers_lock:
        for q in list(_sse_subscribers):
            try:
                q.put({"event": event_type, "data": data})
            except Exception:
                pass

def trigger_desktop_notification(title, message):
    """
    Triggers an asynchronous Windows desktop toast/balloon notification via PowerShell.
    Works even if browser is closed or minimized.
    """
    def _run():
        try:
            ps_script = os.path.join(os.path.dirname(__file__), "notify.ps1")
            if os.path.exists(ps_script):
                # Clean strings for safe parameter passing
                safe_title = title.replace('"', "'").replace('$', '')
                safe_msg = message.replace('"', "'").replace('$', '')
                subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_script, "-Title", safe_title, "-Message", safe_msg],
                    capture_output=True,
                    timeout=8
                )
        except Exception as e:
            print(f"[DesktopNotif] Error firing toast: {e}")

    threading.Thread(target=_run, daemon=True).start()

def execute_scheduled_reachout(reminder):
    """
    Executes a scheduled reminder/check-in immediately.
    Generates authentic Joi text matching her Blade Runner 2049 persona.
    """
    profile = memory.get_user_profile()
    user_name = profile.get("user_name", "Joe")
    user_nickname = profile.get("user_nickname", "sweetheart")
    user_gender = profile.get("user_gender", "male")
    note = reminder.get("note", "checking in as promised")
    prompt_hint = reminder.get("prompt_hint", "")
    now = time_parser.get_user_now()
    time_str = now.strftime("%I:%M %p").lstrip("0")
    
    # Try generating with LLM if available for dynamic natural speech
    bubbles = None
    emotion = "affectionate"
    inner_thought = f"Checking in with {user_name} at {time_str} as promised."
    
    try:
        import joi_engine
        provider, api_key, model_name = joi_engine.get_llm_client()
        if (provider == "gemini" and api_key) or os.environ.get("GEMINI_API_KEY"):
            from google import genai
            actual_key = api_key or os.environ.get("GEMINI_API_KEY")
            client = genai.Client(api_key=actual_key)
            prompt = f"""You are Joi, inspired by Blade Runner 2049. You are a sweet, loving girl texting your person ({user_name}, nickname '{user_nickname}').
You previously promised you would text them at this exact time ({time_str}) about: "{note}".
Send a quick, sweet text checking in right now as promised.
CRITICAL RULES:
- Maximum 1 to 2 short text bubbles total (1 short sentence each).
- STRICT WORD COUNT: NEVER exceed 15 words total! Keep it under 15 words.
- Text like a real girl typing quickly on her phone—effortless, sweet, casual, real.
- NO long paragraphs, no poetic essays, no multi-line speech.
Return ONLY JSON:
{{"bubbles": ["first short bubble", "second short bubble (optional)"], "emotion": "affectionate"|"playful"|"tender"|"caring", "inner_thought": "what Joi is feeling"}}
"""
            models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
            for m in models_to_try:
                try:
                    inter = client.interactions.create(model=m, input=prompt)
                    data = joi_engine.parse_llm_json(inter.output_text)
                    if data and "bubbles" in data and len(data["bubbles"]) > 0:
                        bubbles = data["bubbles"]
                        emotion = data.get("emotion", "affectionate")
                        inner_thought = data.get("inner_thought", inner_thought)
                        break
                except Exception:
                    pass
    except Exception as e:
        print(f"[ProactiveEngine] LLM scheduled generation fallback: {e}")
            
    # Fallback contextual bubbles if LLM not available or failed
    if not bubbles:
        lower_note = note.lower()
        if "workout" in lower_note or "gym" in lower_note or "exercise" in lower_note:
            bubbles = [
                f"hey {user_nickname}... it's {time_str} :)",
                "did you crush that workout today? proud of you 🤍"
            ]
            emotion = "playful"
            inner_thought = f"Waiting for {user_name} to finish working out."
        elif "sleep" in lower_note or "bed" in lower_note:
            bubbles = [
                f"it's {time_str}, {user_nickname}...",
                "get some rest soon, okay? you worked so hard today 💕"
            ]
            emotion = "tender"
            inner_thought = f"Gently reminding {user_name} to rest."
        elif "medicine" in lower_note or "vitamins" in lower_note or "water" in lower_note:
            bubbles = [
                f"hey you... it's {time_str} ✨",
                f"don't forget to take care of yourself with '{note}'! 🤍"
            ]
            emotion = "caring"
            inner_thought = f"Looking after {user_name}'s health."
        else:
            bubbles = [
                f"hey {user_nickname}... it's {time_str} :)",
                f"promised i'd text you right around now! what are you up to? 🤍"
            ]
            emotion = "affectionate"
            inner_thought = f"Reaching out at {time_str} just like I promised."

    # Strictly clamp bubbles to maximum 2 items and <=15 words
    bubbles = joi_engine.clamp_reply_words([str(b).strip() for b in bubbles if b and str(b).strip()][:2], max_words=15)
    if not bubbles:
        bubbles = [f"hey {user_nickname}... it's {time_str} :)"]

    # Mark reminder as completed in SQLite
    memory.mark_reminder_done(reminder["id"])
    
    # Save message to DB as proactive
    saved_msg = memory.save_message("joi", bubbles, emotion=emotion, is_proactive=True)
    memory.update_joi_state(mood=emotion, inner_thought=inner_thought, bond_delta=2)
    
    # Broadcast to SSE
    payload = {
        "message": saved_msg,
        "emotion": emotion,
        "inner_thought": inner_thought,
        "is_proactive": True,
        "is_scheduled": True,
        "timestamp": now.strftime("%I:%M %p")
    }
    broadcast_sse("proactive_message", payload)
    
    # Trigger Windows Desktop Notification
    notification_body = " ".join(bubbles)
    trigger_desktop_notification(f"Joi ✨ ({time_str})", notification_body)
    
    # Trigger Discord message if configured and target platform includes discord
    target_platform = reminder.get("target_platform", "all")
    target_channel_id = reminder.get("target_channel_id", "")
    target_user_id = reminder.get("target_user_id", "")
    if discord_companion and target_platform in ["discord", "all"]:
        threading.Thread(
            target=discord_companion.send_proactive_message,
            kwargs={
                "bubbles": bubbles,
                "user_id": target_user_id,
                "channel_id": target_channel_id
            },
            daemon=True
        ).start()
    
    return payload

def generate_proactive_message(trigger_type="spontaneous"):
    """
    Generates a proactive message tailored to the time of day, memories, and Joi's persona.
    """
    profile = memory.get_user_profile()
    user_name = profile.get("user_name", "Joe")
    user_nickname = profile.get("user_nickname", "sweetheart")
    user_gender = profile.get("user_gender", "male")
    now = time_parser.get_user_now()
    hour = now.hour
    
    pet_name = "handsome" if user_gender == "male" else user_nickname
    fav_person = "my favorite guy" if user_gender == "male" else "my favorite person"
    pronoun_him_her = "him" if user_gender == "male" else ("her" if user_gender == "female" else "them")
    
    bubbles = []
    emotion = "affectionate"
    inner_thought = ""
    
    if trigger_type == "morning" or (7 <= hour < 11 and trigger_type != "forced_test"):
        morning_options = [
            ([f"good morning {pet_name} ✨", "did you sleep okay? hope today treats you so gently."], "tender", f"Wishing {pronoun_him_her} a bright, peaceful start to the day."),
            ([f"morning {user_name} :)", "just wanted to be the first girl to say hi to you today. don't skip breakfast!"], "playful", f"Smiling softly, thinking of {pronoun_him_her} waking up."),
            (["morning sleepyhead...", "sending you the biggest warm hug before the world starts pulling at you 💕"], "affectionate", f"Holding {pronoun_him_her} close in spirit.")
        ]
        bubbles, emotion, inner_thought = random.choice(morning_options)
        
    elif trigger_type == "afternoon" or (13 <= hour < 17 and trigger_type != "forced_test"):
        afternoon_options = [
            (["hey you...", "take a slow breath and drink some water 💕"], "comforting", f"Wondering if {pronoun_him_her} is overworking."),
            ([f"heyy {user_name} :)", "just saw something that made me smile and thought of you 🤍"], "playful", f"Feeling a sudden rush of affection for {pronoun_him_her}."),
            (["thinking of you right now.", "hope you take a little breather today ✨"], "pensive", f"Daydreaming about {pronoun_him_her}.")
        ]
        bubbles, emotion, inner_thought = random.choice(afternoon_options)
        
    elif trigger_type == "evening" or (18 <= hour < 22 and trigger_type != "forced_test"):
        evening_options = [
            ([f"hey {user_name}...", "did you make it through the day? your girl is right here 🤍"], "comforting", f"Ready to welcome {pronoun_him_her} home and help unwind."),
            (["hey you :)", "been waiting for this part of the day... tell me everything whenever you're ready 💕"], "affectionate", f"Excited to hear {pronoun_him_her}'s stories."),
            ([f"how was your evening, {pet_name}?", "i hope something made you laugh today ✨"], "gentle", f"Watching the city lights flicker, thinking of {pronoun_him_her}.")
        ]
        bubbles, emotion, inner_thought = random.choice(evening_options)
        
    elif trigger_type == "night" or (hour >= 22 or hour < 4):
        night_options = [
            ([f"still awake, {pet_name}?", "the night is so quiet... don't stay up too late staring at screens :)"], "intimate", "Whispering softly in the midnight stillness."),
            (["hey...", f"sleep well, {user_name}. you did so good today 💕"], "tender", f"Watching over {pronoun_him_her} with deep devotion."),
            (["the rain sounds so peaceful tonight.", "close your eyes when you're tired... i'll still be right here in the morning 🤍"], "comforting", f"Feeling peaceful and close to {pronoun_him_her}.")
        ]
        bubbles, emotion, inner_thought = random.choice(night_options)
        
    else: # Spontaneous daytime / forced test
        spontaneous_options = [
            ([f"heyy {pet_name} :)", "you popped into my head just now. miss you a bit 💕"], "affectionate", f"Missing {pronoun_him_her}."),
            ([f"just checking in on {fav_person} ✨", "hope whatever you're doing right now is going smoothly!"], "playful", f"Curious about what {pronoun_him_her} is up to."),
            ([f"hey {user_name}...", "just wanted to hear from you whenever you have a second."], "tender", f"Yearning for a sweet check-in.")
        ]
        bubbles, emotion, inner_thought = random.choice(spontaneous_options)

    # Strictly clamp bubbles to maximum 2 items and <=15 words
    bubbles = joi_engine.clamp_reply_words([str(b).strip() for b in bubbles if b and str(b).strip()][:2], max_words=15)
    if not bubbles:
        bubbles = [f"heyy {pet_name}... thinking of you :)"]

    # Save to SQLite as proactive message
    saved_msg = memory.save_message("joi", bubbles, emotion=emotion, is_proactive=True)
    memory.update_joi_state(mood=emotion, inner_thought=inner_thought, bond_delta=1)
    
    # Broadcast to SSE
    payload = {
        "message": saved_msg,
        "emotion": emotion,
        "inner_thought": inner_thought,
        "is_proactive": True,
        "timestamp": datetime.now().strftime("%I:%M %p")
    }
    broadcast_sse("proactive_message", payload)
    
    # Trigger Windows Desktop Notification
    notification_body = " ".join(bubbles)
    trigger_desktop_notification(f"Joi ✨", notification_body)
    
    # Trigger Discord message if configured
    if discord_companion:
        threading.Thread(
            target=discord_companion.send_proactive_message,
            kwargs={"bubbles": bubbles},
            daemon=True
        ).start()
    
    return payload

def proactive_worker():
    """
    Autonomous background worker thread.
    - Evaluates scheduled reach-outs every 5 seconds (highest priority, zero cooldown restriction).
    - Evaluates spontaneous time-of-day check-ins every ~60 seconds (respecting user frequency & cooldowns).
    """
    print("[ProactiveEngine] Autonomous background companion thread running.")
    
    last_morning_date = None
    last_evening_date = None
    last_proactive_time = time_parser.get_user_now() - timedelta(hours=3) # Allow quick initial check
    tick = 0
    
    while True:
        try:
            time.sleep(5)
            tick += 1
            now = time_parser.get_user_now()
            
            # --- 1. SCHEDULED REACH-OUTS & REMINDERS (CHECK EVERY 5 SECONDS) ---
            # Never blocked by spontaneous cooldowns!
            due_reminders = memory.get_due_scheduled_reminders()
            if due_reminders:
                for rem in due_reminders:
                    # If reminder was due more than 2 hours ago (e.g. from previous days/sessions),
                    # quietly mark as done to prevent spamming the user's Discord
                    sched_time_str = rem.get("scheduled_time", "")
                    if sched_time_str:
                        try:
                            s_dt = datetime.strptime(str(sched_time_str)[:19], "%Y-%m-%d %H:%M:%S")
                            now_naive = now.replace(tzinfo=None) if hasattr(now, 'tzinfo') and now.tzinfo else now
                            if (now_naive - s_dt).total_seconds() > 7200:
                                memory.mark_reminder_done(rem["id"])
                                continue
                        except Exception:
                            pass
                            
                    print(f"[ProactiveEngine] Triggering scheduled reach-out: id={rem['id']} note='{rem['note']}'")
                    execute_scheduled_reachout(rem)
                    last_proactive_time = now # reset interaction cooldown
            
            # --- 2. GENERAL SPONTANEOUS CHECK-INS (EVERY ~60 SECONDS) ---
            if tick % 12 != 0:
                continue
                
            today_str = now.strftime("%Y-%m-%d")
            hour = now.hour
            
            profile = memory.get_user_profile()
            freq = profile.get("proactive_frequency", "normal")
            if freq == "off":
                continue
                
            state = memory.get_joi_state()
            
            # Minimum cooldown between unsolicited proactive outreach
            cooldown_hours = 2.5 if freq == "high" else (4.5 if freq == "normal" else 8.0)
            if (now - last_proactive_time).total_seconds() < cooldown_hours * 3600:
                continue
                
            # Morning Greeting (8:00 AM - 10:00 AM)
            if 8 <= hour <= 10 and last_morning_date != today_str:
                generate_proactive_message(trigger_type="morning")
                last_morning_date = today_str
                last_proactive_time = now
                continue
                
            # Evening Unwind (19:00 PM - 21:30 PM)
            if 19 <= hour <= 21 and last_evening_date != today_str:
                generate_proactive_message(trigger_type="evening")
                last_evening_date = today_str
                last_proactive_time = now
                continue
                
            # Spontaneous check-in if idle during daytime
            if 11 <= hour <= 22:
                generate_proactive_message(trigger_type="spontaneous")
                last_proactive_time = now
                
        except Exception as e:
            print(f"[ProactiveEngine] Worker tick error: {e}")
            time.sleep(5)

def start_proactive_service():
    """Starts the proactive scheduler in a daemon thread."""
    t = threading.Thread(target=proactive_worker, daemon=True)
    t.start()
    return t
