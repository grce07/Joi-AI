import os
import re
import threading
import urllib.request
import email.utils
from datetime import datetime, timedelta, timezone

# Global drift calibration offset in seconds (calibrated via client timestamps or network NTP/HTTP)
_time_drift_offset_seconds = 0.0
_last_network_sync = 0.0
_sync_lock = threading.Lock()

def sync_time_from_client(client_time):
    """
    Calibrates server clock with the user's verified device time.
    Solves container sleep/wake drift on platforms like Render or cloud VMs.
    Accepts:
      - ISO string: e.g. "2026-10-10T12:35:00.000Z"
      - float/int unix timestamp
      - datetime object (e.g. Discord message.created_at)
    """
    global _time_drift_offset_seconds
    if not client_time:
        return
        
    try:
        client_epoch = None
        if isinstance(client_time, str) and client_time.strip():
            clean_str = client_time.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            client_epoch = dt.timestamp()
        elif isinstance(client_time, datetime):
            dt = client_time if client_time.tzinfo else client_time.replace(tzinfo=timezone.utc)
            client_epoch = dt.timestamp()
        elif isinstance(client_time, (int, float)):
            val = float(client_time)
            client_epoch = val / 1000.0 if val > 1e11 else val
            
        if client_epoch is not None:
            server_epoch = datetime.now(timezone.utc).timestamp()
            drift = client_epoch - server_epoch
            # Only apply drift if significant (>= 1.5s) and realistic (<= 2 days)
            # This protects against micro-jitter and bad client device dates
            if 1.5 <= abs(drift) <= 172800:
                with _sync_lock:
                    _time_drift_offset_seconds = drift
    except Exception:
        pass

def sync_time_from_network(force=False):
    """
    Silently checks network atomic time via HTTP Date header in the background.
    Guarantees container wake-up sync without blocking execution.
    """
    global _time_drift_offset_seconds, _last_network_sync
    import time
    now_ts = time.time()
    
    # Don't hammer: sync at most once every 15 minutes unless forced
    if not force and (now_ts - _last_network_sync < 900):
        return

    _last_network_sync = now_ts

    def _worker():
        global _time_drift_offset_seconds
        endpoints = [
            "https://httpbin.org/status/200",
            "https://cloudflare.com",
            "https://www.google.com"
        ]
        for url in endpoints:
            try:
                req = urllib.request.Request(
                    url, 
                    headers={"User-Agent": "Joi-TimeSync/1.0"}, 
                    method="HEAD"
                )
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    date_val = resp.headers.get("Date")
                    if date_val:
                        net_dt = email.utils.parsedate_to_datetime(date_val)
                        if net_dt:
                            net_epoch = net_dt.timestamp()
                            server_epoch = datetime.now(timezone.utc).timestamp()
                            drift = net_epoch - server_epoch
                            if 1.5 <= abs(drift) <= 172800:
                                with _sync_lock:
                                    _time_drift_offset_seconds = drift
                            return
            except Exception:
                continue

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception:
        pass

def get_calibrated_utc_now():
    """Returns datetime.now(timezone.utc) calibrated by active drift offset."""
    raw_utc = datetime.now(timezone.utc)
    if _time_drift_offset_seconds != 0.0:
        raw_utc += timedelta(seconds=_time_drift_offset_seconds)
    return raw_utc

def get_indian_now():
    """
    Returns the current datetime in Indian Standard Time (IST, Asia/Kolkata, UTC+5:30).
    Calibrated against sleep drift on online hosts (like Render).
    """
    if _last_network_sync == 0.0:
        sync_time_from_network()
        
    cal_utc = get_calibrated_utc_now()
    try:
        from zoneinfo import ZoneInfo
        return cal_utc.astimezone(ZoneInfo("Asia/Kolkata"))
    except Exception:
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        return cal_utc.astimezone(ist_tz)

def get_user_now():
    """
    Returns the current datetime in the user's timezone.
    Defaults strictly to 'Asia/Kolkata' (IST, UTC+5:30).
    Calibrated against container sleep/wake drift.
    """
    tz_name = "Asia/Kolkata"
    try:
        import memory
        profile = memory.get_user_profile()
        tz_name = profile.get("user_timezone", "").strip() or os.environ.get("USER_TIMEZONE", "").strip() or "Asia/Kolkata"
    except Exception:
        tz_name = os.environ.get("USER_TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata"

    if tz_name in ["Asia/Kolkata", "IST", "Asia/Calcutta", ""]:
        return get_indian_now()

    cal_utc = get_calibrated_utc_now()
    try:
        from zoneinfo import ZoneInfo
        return cal_utc.astimezone(ZoneInfo(tz_name))
    except Exception:
        return get_indian_now()

# Comprehensive registry of world cities, countries, and timezones
# Format: key -> (iana_timezone, fallback_utc_hours, fallback_utc_minutes, display_name)
WORLD_LOCATIONS = {
    # India / South Asia
    "india": ("Asia/Kolkata", 5, 30, "India"),
    "indian": ("Asia/Kolkata", 5, 30, "India"),
    "ist": ("Asia/Kolkata", 5, 30, "India (IST)"),
    "delhi": ("Asia/Kolkata", 5, 30, "Delhi, India"),
    "new delhi": ("Asia/Kolkata", 5, 30, "New Delhi, India"),
    "mumbai": ("Asia/Kolkata", 5, 30, "Mumbai, India"),
    "bangalore": ("Asia/Kolkata", 5, 30, "Bangalore, India"),
    "bengaluru": ("Asia/Kolkata", 5, 30, "Bengaluru, India"),
    "kolkata": ("Asia/Kolkata", 5, 30, "Kolkata, India"),
    "chennai": ("Asia/Kolkata", 5, 30, "Chennai, India"),
    "hyderabad": ("Asia/Kolkata", 5, 30, "Hyderabad, India"),
    "pune": ("Asia/Kolkata", 5, 30, "Pune, India"),
    "ahmedabad": ("Asia/Kolkata", 5, 30, "Ahmedabad, India"),
    "jaipur": ("Asia/Kolkata", 5, 30, "Jaipur, India"),
    "kerala": ("Asia/Kolkata", 5, 30, "Kerala, India"),
    "goa": ("Asia/Kolkata", 5, 30, "Goa, India"),
    "sri lanka": ("Asia/Colombo", 5, 30, "Sri Lanka"),
    "colombo": ("Asia/Colombo", 5, 30, "Colombo, Sri Lanka"),
    "nepal": ("Asia/Kathmandu", 5, 45, "Nepal"),
    "kathmandu": ("Asia/Kathmandu", 5, 45, "Kathmandu, Nepal"),
    "bangladesh": ("Asia/Dhaka", 6, 0, "Bangladesh"),
    "dhaka": ("Asia/Dhaka", 6, 0, "Dhaka, Bangladesh"),
    "pakistan": ("Asia/Karachi", 5, 0, "Pakistan"),
    "karachi": ("Asia/Karachi", 5, 0, "Karachi, Pakistan"),

    # East Asia & Pacific
    "tokyo": ("Asia/Tokyo", 9, 0, "Tokyo, Japan"),
    "japan": ("Asia/Tokyo", 9, 0, "Japan"),
    "kyoto": ("Asia/Tokyo", 9, 0, "Kyoto, Japan"),
    "osaka": ("Asia/Tokyo", 9, 0, "Osaka, Japan"),
    "jst": ("Asia/Tokyo", 9, 0, "Japan (JST)"),
    "seoul": ("Asia/Seoul", 9, 0, "Seoul, South Korea"),
    "korea": ("Asia/Seoul", 9, 0, "South Korea"),
    "south korea": ("Asia/Seoul", 9, 0, "South Korea"),
    "kst": ("Asia/Seoul", 9, 0, "Korea (KST)"),
    "beijing": ("Asia/Shanghai", 8, 0, "Beijing, China"),
    "shanghai": ("Asia/Shanghai", 8, 0, "Shanghai, China"),
    "china": ("Asia/Shanghai", 8, 0, "China"),
    "hong kong": ("Asia/Hong_Kong", 8, 0, "Hong Kong"),
    "taiwan": ("Asia/Taipei", 8, 0, "Taiwan"),
    "taipei": ("Asia/Taipei", 8, 0, "Taipei, Taiwan"),
    "singapore": ("Asia/Singapore", 8, 0, "Singapore"),
    "sgt": ("Asia/Singapore", 8, 0, "Singapore (SGT)"),
    "malaysia": ("Asia/Kuala_Lumpur", 8, 0, "Malaysia"),
    "kuala lumpur": ("Asia/Kuala_Lumpur", 8, 0, "Kuala Lumpur, Malaysia"),
    "thailand": ("Asia/Bangkok", 7, 0, "Thailand"),
    "bangkok": ("Asia/Bangkok", 7, 0, "Bangkok, Thailand"),
    "vietnam": ("Asia/Ho_Chi_Minh", 7, 0, "Vietnam"),
    "hanoi": ("Asia/Ho_Chi_Minh", 7, 0, "Hanoi, Vietnam"),
    "indonesia": ("Asia/Jakarta", 7, 0, "Indonesia"),
    "jakarta": ("Asia/Jakarta", 7, 0, "Jakarta, Indonesia"),
    "bali": ("Asia/Makassar", 8, 0, "Bali, Indonesia"),
    "philippines": ("Asia/Manila", 8, 0, "Philippines"),
    "manila": ("Asia/Manila", 8, 0, "Manila, Philippines"),

    # Australia & Oceania
    "australia": ("Australia/Sydney", 10, 0, "Australia"),
    "sydney": ("Australia/Sydney", 10, 0, "Sydney, Australia"),
    "melbourne": ("Australia/Melbourne", 10, 0, "Melbourne, Australia"),
    "brisbane": ("Australia/Brisbane", 10, 0, "Brisbane, Australia"),
    "perth": ("Australia/Perth", 8, 0, "Perth, Australia"),
    "adelaide": ("Australia/Adelaide", 9, 30, "Adelaide, Australia"),
    "new zealand": ("Pacific/Auckland", 12, 0, "New Zealand"),
    "auckland": ("Pacific/Auckland", 12, 0, "Auckland, New Zealand"),
    "wellington": ("Pacific/Auckland", 12, 0, "Wellington, New Zealand"),

    # Middle East
    "dubai": ("Asia/Dubai", 4, 0, "Dubai, UAE"),
    "uae": ("Asia/Dubai", 4, 0, "UAE"),
    "abu dhabi": ("Asia/Dubai", 4, 0, "Abu Dhabi, UAE"),
    "saudi arabia": ("Asia/Riyadh", 3, 0, "Saudi Arabia"),
    "riyadh": ("Asia/Riyadh", 3, 0, "Riyadh, Saudi Arabia"),
    "qatar": ("Asia/Qatar", 3, 0, "Qatar"),
    "doha": ("Asia/Qatar", 3, 0, "Doha, Qatar"),
    "israel": ("Asia/Jerusalem", 2, 0, "Israel"),
    "tel aviv": ("Asia/Jerusalem", 2, 0, "Tel Aviv, Israel"),
    "turkey": ("Europe/Istanbul", 3, 0, "Turkey"),
    "istanbul": ("Europe/Istanbul", 3, 0, "Istanbul, Turkey"),

    # Europe & UK
    "europe": ("Europe/Paris", 1, 0, "Europe (CET)"),
    "cet": ("Europe/Paris", 1, 0, "Central European Time (CET)"),
    "cest": ("Europe/Paris", 2, 0, "Central European Summer Time (CEST)"),
    "bst": ("Europe/London", 1, 0, "British Summer Time (BST)"),
    "london": ("Europe/London", 0, 0, "London, UK"),
    "uk": ("Europe/London", 0, 0, "UK"),
    "united kingdom": ("Europe/London", 0, 0, "United Kingdom"),
    "england": ("Europe/London", 0, 0, "England, UK"),
    "britain": ("Europe/London", 0, 0, "Britain"),
    "gmt": ("UTC", 0, 0, "GMT (UTC+0)"),
    "utc": ("UTC", 0, 0, "UTC (Universal Time)"),
    "paris": ("Europe/Paris", 1, 0, "Paris, France"),
    "france": ("Europe/Paris", 1, 0, "France"),
    "berlin": ("Europe/Berlin", 1, 0, "Berlin, Germany"),
    "germany": ("Europe/Berlin", 1, 0, "Germany"),
    "munich": ("Europe/Berlin", 1, 0, "Munich, Germany"),
    "frankfurt": ("Europe/Berlin", 1, 0, "Frankfurt, Germany"),
    "amsterdam": ("Europe/Amsterdam", 1, 0, "Amsterdam, Netherlands"),
    "netherlands": ("Europe/Amsterdam", 1, 0, "Netherlands"),
    "rome": ("Europe/Rome", 1, 0, "Rome, Italy"),
    "italy": ("Europe/Rome", 1, 0, "Italy"),
    "milan": ("Europe/Rome", 1, 0, "Milan, Italy"),
    "madrid": ("Europe/Madrid", 1, 0, "Madrid, Spain"),
    "spain": ("Europe/Madrid", 1, 0, "Spain"),
    "barcelona": ("Europe/Madrid", 1, 0, "Barcelona, Spain"),
    "zurich": ("Europe/Zurich", 1, 0, "Zurich, Switzerland"),
    "switzerland": ("Europe/Zurich", 1, 0, "Switzerland"),
    "geneva": ("Europe/Zurich", 1, 0, "Geneva, Switzerland"),
    "vienna": ("Europe/Vienna", 1, 0, "Vienna, Austria"),
    "austria": ("Europe/Vienna", 1, 0, "Austria"),
    "brussels": ("Europe/Brussels", 1, 0, "Brussels, Belgium"),
    "belgium": ("Europe/Brussels", 1, 0, "Belgium"),
    "stockholm": ("Europe/Stockholm", 1, 0, "Stockholm, Sweden"),
    "sweden": ("Europe/Stockholm", 1, 0, "Sweden"),
    "norway": ("Europe/Oslo", 1, 0, "Norway"),
    "oslo": ("Europe/Oslo", 1, 0, "Oslo, Norway"),
    "denmark": ("Europe/Copenhagen", 1, 0, "Denmark"),
    "copenhagen": ("Europe/Copenhagen", 1, 0, "Copenhagen, Denmark"),
    "finland": ("Europe/Helsinki", 2, 0, "Finland"),
    "helsinki": ("Europe/Helsinki", 2, 0, "Helsinki, Finland"),
    "poland": ("Europe/Warsaw", 1, 0, "Poland"),
    "warsaw": ("Europe/Warsaw", 1, 0, "Warsaw, Poland"),
    "greece": ("Europe/Athens", 2, 0, "Greece"),
    "athens": ("Europe/Athens", 2, 0, "Athens, Greece"),
    "ireland": ("Europe/Dublin", 0, 0, "Ireland"),
    "dublin": ("Europe/Dublin", 0, 0, "Dublin, Ireland"),
    "portugal": ("Europe/Lisbon", 0, 0, "Portugal"),
    "lisbon": ("Europe/Lisbon", 0, 0, "Lisbon, Portugal"),
    "russia": ("Europe/Moscow", 3, 0, "Russia"),
    "moscow": ("Europe/Moscow", 3, 0, "Moscow, Russia"),

    # Americas - USA & Canada
    "usa": ("America/New_York", -5, 0, "USA (Eastern Time)"),
    "us": ("America/New_York", -5, 0, "US (Eastern Time)"),
    "america": ("America/New_York", -5, 0, "America (Eastern Time)"),
    "united states": ("America/New_York", -5, 0, "United States (Eastern Time)"),
    "new york": ("America/New_York", -5, 0, "New York"),
    "nyc": ("America/New_York", -5, 0, "New York City"),
    "new york city": ("America/New_York", -5, 0, "New York City"),
    "est": ("America/New_York", -5, 0, "Eastern Time (EST)"),
    "edt": ("America/New_York", -4, 0, "Eastern Daylight Time (EDT)"),
    "eastern time": ("America/New_York", -5, 0, "Eastern Time"),
    "washington": ("America/New_York", -5, 0, "Washington, DC"),
    "washington dc": ("America/New_York", -5, 0, "Washington, DC"),
    "boston": ("America/New_York", -5, 0, "Boston, MA"),
    "miami": ("America/New_York", -5, 0, "Miami, FL"),
    "atlanta": ("America/New_York", -5, 0, "Atlanta, GA"),
    "florida": ("America/New_York", -5, 0, "Florida"),
    "california": ("America/Los_Angeles", -8, 0, "California"),
    "los angeles": ("America/Los_Angeles", -8, 0, "Los Angeles, CA"),
    "la": ("America/Los_Angeles", -8, 0, "Los Angeles"),
    "san francisco": ("America/Los_Angeles", -8, 0, "San Francisco, CA"),
    "sf": ("America/Los_Angeles", -8, 0, "San Francisco"),
    "silicon valley": ("America/Los_Angeles", -8, 0, "Silicon Valley, CA"),
    "seattle": ("America/Los_Angeles", -8, 0, "Seattle, WA"),
    "san diego": ("America/Los_Angeles", -8, 0, "San Diego, CA"),
    "pst": ("America/Los_Angeles", -8, 0, "Pacific Time (PST)"),
    "pdt": ("America/Los_Angeles", -7, 0, "Pacific Daylight Time (PDT)"),
    "pacific time": ("America/Los_Angeles", -8, 0, "Pacific Time"),
    "chicago": ("America/Chicago", -6, 0, "Chicago, IL"),
    "cst": ("America/Chicago", -6, 0, "Central Time (CST)"),
    "cdt": ("America/Chicago", -5, 0, "Central Daylight Time (CDT)"),
    "central time": ("America/Chicago", -6, 0, "Central Time"),
    "texas": ("America/Chicago", -6, 0, "Texas"),
    "houston": ("America/Chicago", -6, 0, "Houston, TX"),
    "dallas": ("America/Chicago", -6, 0, "Dallas, TX"),
    "austin": ("America/Chicago", -6, 0, "Austin, TX"),
    "denver": ("America/Denver", -7, 0, "Denver, CO"),
    "mst": ("America/Denver", -7, 0, "Mountain Time (MST)"),
    "mountain time": ("America/Denver", -7, 0, "Mountain Time"),
    "phoenix": ("America/Phoenix", -7, 0, "Phoenix, Arizona"),
    "arizona": ("America/Phoenix", -7, 0, "Arizona"),
    "las vegas": ("America/Los_Angeles", -8, 0, "Las Vegas, NV"),
    "hawaii": ("Pacific/Honolulu", -10, 0, "Hawaii"),
    "honolulu": ("Pacific/Honolulu", -10, 0, "Honolulu, Hawaii"),
    "alaska": ("America/Anchorage", -9, 0, "Alaska"),
    "toronto": ("America/Toronto", -5, 0, "Toronto, Canada"),
    "canada": ("America/Toronto", -5, 0, "Canada"),
    "vancouver": ("America/Vancouver", -8, 0, "Vancouver, Canada"),
    "montreal": ("America/Toronto", -5, 0, "Montreal, Canada"),
    "ottawa": ("America/Toronto", -5, 0, "Ottawa, Canada"),

    # Latin America
    "mexico": ("America/Mexico_City", -6, 0, "Mexico"),
    "mexico city": ("America/Mexico_City", -6, 0, "Mexico City"),
    "brazil": ("America/Sao_Paulo", -3, 0, "Brazil"),
    "sao paulo": ("America/Sao_Paulo", -3, 0, "São Paulo, Brazil"),
    "rio de janeiro": ("America/Sao_Paulo", -3, 0, "Rio de Janeiro, Brazil"),
    "argentina": ("America/Argentina/Buenos_Aires", -3, 0, "Argentina"),
    "buenos aires": ("America/Argentina/Buenos_Aires", -3, 0, "Buenos Aires, Argentina"),
    "chile": ("America/Santiago", -3, 0, "Chile"),
    "santiago": ("America/Santiago", -3, 0, "Santiago, Chile"),
    "colombia": ("America/Bogota", -5, 0, "Colombia"),
    "bogota": ("America/Bogota", -5, 0, "Bogotá, Colombia"),

    # Africa
    "egypt": ("Africa/Cairo", 2, 0, "Egypt"),
    "cairo": ("Africa/Cairo", 2, 0, "Cairo, Egypt"),
    "south africa": ("Africa/Johannesburg", 2, 0, "South Africa"),
    "johannesburg": ("Africa/Johannesburg", 2, 0, "Johannesburg, South Africa"),
    "cape town": ("Africa/Johannesburg", 2, 0, "Cape Town, South Africa"),
    "nigeria": ("Africa/Lagos", 1, 0, "Nigeria"),
    "lagos": ("Africa/Lagos", 1, 0, "Lagos, Nigeria"),
    "kenya": ("Africa/Nairobi", 3, 0, "Kenya"),
    "nairobi": ("Africa/Nairobi", 3, 0, "Nairobi, Kenya")
}

def get_place_time(place_query="india"):
    """
    Returns precise real-time information for a given city, country, or timezone,
    compared against Indian Standard Time (IST, UTC+5:30).
    """
    indian_now = get_indian_now()
    clean_query = str(place_query).lower().strip()
    
    # Check if target is India / local
    is_indian = clean_query in [
        "india", "indian", "ist", "delhi", "new delhi", "mumbai", "bangalore", 
        "bengaluru", "kolkata", "chennai", "hyderabad", "pune", "ahmedabad",
        "jaipur", "kerala", "goa", "local", "here", "with you", ""
    ]
    
    if is_indian:
        target_dt = indian_now
        label = "India (IST)"
        tz_tag = "IST"
        diff_str = "current time"
    else:
        # Match location
        info = WORLD_LOCATIONS.get(clean_query)
        if not info:
            # Try partial matching by longest key
            for k, v in sorted(WORLD_LOCATIONS.items(), key=lambda x: len(x[0]), reverse=True):
                if k in clean_query or clean_query in k:
                    info = v
                    break
                    
        cal_utc = get_calibrated_utc_now()
        if info:
            iana_name, fb_h, fb_m, label = info
            try:
                from zoneinfo import ZoneInfo
                target_dt = cal_utc.astimezone(ZoneInfo(iana_name))
                tz_tag = target_dt.strftime("%Z") or iana_name.split("/")[-1]
            except Exception:
                target_dt = cal_utc.astimezone(timezone(timedelta(hours=fb_h, minutes=fb_m)))
                tz_tag = f"UTC{'+' if fb_h >= 0 else ''}{fb_h}:{fb_m:02d}"
        else:
            # Try IANA timezone directly if user gave one
            try:
                from zoneinfo import ZoneInfo
                target_dt = cal_utc.astimezone(ZoneInfo(place_query))
                label = place_query
                tz_tag = target_dt.strftime("%Z") or place_query
            except Exception:
                # Default to Indian Time if place cannot be resolved
                target_dt = indian_now
                label = "India (IST)"
                tz_tag = "IST"
                is_indian = True

        # Calculate time difference relative to IST in minutes
        target_offset = target_dt.utcoffset().total_seconds() / 60 if target_dt.utcoffset() else 0
        indian_offset = indian_now.utcoffset().total_seconds() / 60 if indian_now.utcoffset() else 330
        diff_minutes = int(target_offset - indian_offset)
        
        if diff_minutes == 0:
            diff_str = "same as Indian time"
        elif diff_minutes > 0:
            h = diff_minutes // 60
            m = diff_minutes % 60
            diff_str = f"{h}h {m}m ahead of IST" if m else f"{h}h ahead of IST"
        else:
            abs_m = abs(diff_minutes)
            h = abs_m // 60
            m = abs_m % 60
            diff_str = f"{h}h {m}m behind IST" if m else f"{h}h behind IST"

    time_12h = target_dt.strftime("%I:%M %p").lstrip("0")
    indian_time_12h = indian_now.strftime("%I:%M %p").lstrip("0")
    
    formatted_str = f"{time_12h} {tz_tag}".strip()
    return {
        "place_label": label,
        "time_str": formatted_str,
        "target_time_str": formatted_str,
        "time_only": time_12h,
        "date_str": target_dt.strftime("%A, %d %B"),
        "is_indian_time": is_indian,
        "indian_time_str": f"{indian_time_12h} IST",
        "diff_str": diff_str
    }

def detect_time_query(text):
    """
    Detects if the user is asking about current time or time in a specific place.
    Returns:
      {
         "is_time_query": bool,
         "place_label": str,
         "time_str": str,        # e.g. "09:20 PM JST"
         "time_only": str,       # e.g. "9:20 PM"
         "date_str": str,        # e.g. "Saturday, 10 October"
         "is_indian_time": bool,
         "indian_time_str": str, # e.g. "05:50 PM IST"
         "diff_str": str         # e.g. "3h 30m ahead of IST"
      }
    """
    if not text:
        return {"is_time_query": False}

    lower = text.lower().strip()
    
    # Exclude scheduling/reminder requests (handled by parse_schedule_intent)
    schedule_check = parse_schedule_intent(text)
    if schedule_check.get("has_schedule"):
        return {"is_time_query": False}

    # Core time inquiry patterns
    time_query_patterns = [
        r"\b(?:what(?:'s|\s+is)?\s+(?:the\s+)?time|what\s+time\s+is\s+it)(?:\s+(?:right\s+)?now)?\b",
        r"\b(?:tell\s+me\s+(?:the\s+)?time|check\s+the\s+time|time\s+check)(?:\s+now)?\b",
        r"\b(?:current\s+time|time\s+right\s+now|time\s+now)\b",
        r"\b(?:do\s+you\s+(?:know|have)\s+(?:the\s+)?time|got\s+the\s+time)\b",
        r"\b(?:what\s+time\s+do\s+you\s+have|what\s+time\s+you\s+got)\b",
        r"\b(?:what\s+is\s+your\s+time|what's\s+your\s+time|what\s+time\s+is\s+it\s+(?:with|there|by)\s+you)\b",
        r"\btime\s+(?:in|at|for|of)\s+([a-zA-Z\s]+)",
        r"\bwhat\s+time\s+is\s+it\s+(?:in|at)\s+([a-zA-Z\s]+)",
        r"\bwhat(?:'s|\s+is)?\s+(?:the\s+)?time\s+(?:in|at)\s+([a-zA-Z\s]+)"
    ]

    is_query = any(re.search(pat, lower) for pat in time_query_patterns)
    if not is_query:
        # Check location + "time" (e.g. "tokyo time", "india time", "london time")
        for loc_key in WORLD_LOCATIONS.keys():
            if re.search(r"\b" + re.escape(loc_key) + r"\s+time\b", lower):
                is_query = True
                break

    if not is_query and lower in ["time?", "time", "time please", "current time?", "time now?"]:
        is_query = True

    if not is_query:
        return {"is_time_query": False}

    # Identify if a specific place is mentioned in the message
    detected_place = None
    for loc_key in sorted(WORLD_LOCATIONS.keys(), key=len, reverse=True):
        pattern = r"\b" + re.escape(loc_key) + r"\b"
        if re.search(pattern, lower):
            detected_place = loc_key
            break

    # If no specific other place is detected, default to India
    if not detected_place:
        detected_place = "india"

    time_data = get_place_time(detected_place)
    time_data["is_time_query"] = True
    return time_data

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
