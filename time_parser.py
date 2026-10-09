import os
import re
from datetime import datetime, timedelta

def get_user_now():
    """
    Returns the current datetime in the user's timezone.
    Defaults to 'Asia/Kolkata' (IST) or the user's configured timezone.
    Works consistently on local machines and UTC cloud servers (like Render).
    """
    tz_name = "Asia/Kolkata"
    try:
        import memory
        profile = memory.get_user_profile()
        tz_name = profile.get("user_timezone", "").strip() or os.environ.get("USER_TIMEZONE", "").strip() or "Asia/Kolkata"
    except Exception:
        tz_name = os.environ.get("USER_TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata"

    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        # Fallback to IST (+05:30) offset if system tzdata is absent
        from datetime import timezone
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))

def parse_schedule_intent(text):
    """
    Parses user message for intent to be texted, reached out to, or reminded at a specific time.
    Returns dict:
      {
         "has_schedule": bool,
         "target_dt": datetime or None,
         "target_time_str": str, # e.g. "08:00 PM"
         "note": str,            # e.g. "checking in as promised / workout"
         "relative_seconds": int or None,
         "relative_minutes": int or None
      }
    """
    if not text:
        return {"has_schedule": False}

    lower = text.lower().strip()
    now = get_user_now()

    # Trigger patterns that indicate intent
    intent_triggers = [
        "text me", "message me", "ping me", "call me", "check in on me",
        "remind me", "wake me up", "reach out", "talk to me", "buzz me",
        "chat with me", "hit me up", "see you at", "be here at"
    ]
    
    has_trigger = any(t in lower for t in intent_triggers)
    if not has_trigger and not re.search(r"\b(at|around|by|in|after|within)\s*\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?\b", lower):
        return {"has_schedule": False}

    target_dt = None
    note = "checking in as promised"

    # Extract note/subject if "remind me to <do something>"
    remind_match = re.search(r"remind me\s+(?:to\s+)?(.+?)(?:\s+(?:at|around|in|after|within|by)\s+|$)", lower)
    if remind_match:
        subject = remind_match.group(1).strip()
        subject = re.sub(r'\b(?:on|in)\s+discord\b', '', subject).strip()
        subject = re.sub(r'^(?:at|around|in|after|within|by)\s+.*', '', subject).strip()
        subject = re.sub(r'^\d+\s*(?:mins?|minutes?|m|hrs?|hours?|h|seconds?|secs?|s).*', '', subject).strip()
        if subject and len(subject) > 2:
            note = subject
            
    # Also extract if "text me ... about <topic>" or "remind me about <topic>"
    about_match = re.search(r"\babout\s+(.+)$", lower)
    if about_match and note == "checking in as promised":
        subj = about_match.group(1).strip()
        subj = re.sub(r'\b(?:on|in)\s+discord\b', '', subj).strip()
        if subj:
            note = subj

    # 1. Relative time:
    # "in X minutes / mins / m / hours / hrs / h / seconds / secs / s"
    # "after X minutes / mins / m / hours / hrs / h"
    # "within X minutes / mins / m / hours / hrs / h"
    # "X mins later / from now"
    rel_match = re.search(r"\b(?:in|after|within)\s*(\d+)\s*(mins?|minutes?|m|hrs?|hours?|h|seconds?|secs?|s)\b", lower)
    if not rel_match:
        rel_match = re.search(r"\b(\d+)\s*(mins?|minutes?|m|hrs?|hours?|h|seconds?|secs?|s)\s+(?:later|from now)\b", lower)

    if rel_match:
        val = int(rel_match.group(1))
        unit = rel_match.group(2).lower()
        total_secs = 0
        if "h" in unit:
            total_secs = val * 3600
        elif "s" in unit and "m" not in unit:
            total_secs = val
        else:
            total_secs = val * 60
            
        target_dt = now + timedelta(seconds=total_secs)
        # Convert to naive local datetime for uniform storage
        target_dt_naive = target_dt.replace(tzinfo=None) if hasattr(target_dt, 'tzinfo') and target_dt.tzinfo else target_dt
            
        return {
            "has_schedule": True,
            "target_dt": target_dt_naive,
            "target_time_str": target_dt.strftime("%I:%M:%S %p") if total_secs < 120 else target_dt.strftime("%I:%M %p"),
            "note": note,
            "relative_seconds": total_secs,
            "relative_minutes": max(1, int(total_secs / 60))
        }

    # 2. Time expressions like:
    # "at 9.35", "at 9:35", "around 8.00pm", "at 8:00pm", "at 8.00 pm", "around 8pm", "at 8:30", "at 8", "9.35 pm", "9:35"
    patterns_to_try = [
        r"(?:text me|message me|ping me|check in|reach out|remind me|wake me up|see you)?\s*(?:like\s+)?(?:around|at|about|by)\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b",
        r"\b(\d{1,2})[:.](\d{2})\s*(am|pm)?\b",
        r"\b(\d{1,2})\s*(am|pm)\b",
        r"\b(\d{1,2})\s*o'clock\s*(am|pm)?\b"
    ]

    match = None
    for pat in patterns_to_try:
        m = re.search(pat, lower)
        if m:
            match = m
            break

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.lastindex >= 2 and match.group(2) else 0
        meridiem = match.group(3).lower() if match.lastindex >= 3 and match.group(3) else None

        if 0 <= minute < 60 and 1 <= hour <= 24:
            if meridiem == "pm" and hour < 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            elif not meridiem:
                # Infer AM vs PM based on user's current local time
                if hour <= 12:
                    pm_hour = hour + 12 if hour < 12 else 12
                    candidate_pm = now.replace(hour=pm_hour, minute=minute, second=0, microsecond=0)
                    candidate_am = now.replace(hour=hour if hour < 12 else 0, minute=minute, second=0, microsecond=0)
                    
                    if candidate_pm > now:
                        hour = pm_hour
                    elif candidate_am > now:
                        hour = hour if hour < 12 else 0
                    else:
                        hour = pm_hour

            target_candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if "tomorrow" in lower:
                target_candidate += timedelta(days=1)
            elif target_candidate <= now:
                # If target has already passed today, advance to tomorrow at the same time
                target_candidate += timedelta(days=1)

            target_dt = target_candidate
            total_sec_diff = max(0, int((target_dt - now).total_seconds()))
            target_dt_naive = target_dt.replace(tzinfo=None) if hasattr(target_dt, 'tzinfo') and target_dt.tzinfo else target_dt

            return {
                "has_schedule": True,
                "target_dt": target_dt_naive,
                "target_time_str": target_dt.strftime("%I:%M %p"),
                "note": note,
                "relative_seconds": total_sec_diff,
                "relative_minutes": max(1, int(total_sec_diff / 60))
            }

    return {"has_schedule": False}
