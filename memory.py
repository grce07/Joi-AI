import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "joi_memory.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. User Profile
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Memories (Long-term facts, preferences, emotions, events, inside jokes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT, -- 'fact', 'preference', 'emotion', 'event', 'inside_joke', 'routine'
            content TEXT NOT NULL,
            importance INTEGER DEFAULT 3, -- 1 to 5
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            access_count INTEGER DEFAULT 0
        )
    """)
    
    # 3. Conversation Messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL, -- 'user' or 'joi'
            bubbles_json TEXT NOT NULL, -- JSON list of strings (each bubble)
            emotion TEXT DEFAULT 'affectionate',
            is_proactive INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 4. Joi's Emotional & Relationship State
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS joi_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mood TEXT DEFAULT 'affectionate',
            bond_level INTEGER DEFAULT 50, -- 0 to 100
            inner_thought TEXT DEFAULT 'Sitting here by the rainy window, thinking about you.',
            last_interaction TIMESTAMP,
            last_proactive TIMESTAMP
        )
    """)
    
    # 5. Scheduled Reminders / Follow-up triggers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note TEXT NOT NULL,
            scheduled_time TIMESTAMP,
            context TEXT,
            prompt_hint TEXT DEFAULT '',
            is_done INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Safe migration for existing databases
    try:
        cursor.execute("ALTER TABLE reminders ADD COLUMN prompt_hint TEXT DEFAULT ''")
    except Exception:
        pass
    
    # Set default profile values if empty
    defaults = {
        "user_name": "Joe",
        "user_nickname": "sweetheart",
        "user_gender": "male", # 'male', 'female', 'nonbinary'
        "relationship_vibe": "deeply affectionate, intimate, playful companion",
        "api_provider": "gemini", # 'gemini' or 'openai' or 'simulation'
        "api_key": "",
        "model_name": "gemini-3.8-flash",
        "proactive_frequency": "normal", # 'high', 'normal', 'low', 'off'
        "discord_bot_token": "",
        "discord_user_id": "",
        "last_active_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO user_profile (key, value) VALUES (?, ?)", (k, v))
        
    cursor.execute("""
        INSERT OR IGNORE INTO joi_state (id, mood, bond_level, inner_thought, last_interaction, last_proactive)
        VALUES (1, 'warm & gentle', 55, 'Happy that you are here with me.', CURRENT_TIMESTAMP, NULL)
    """)
    
    conn.commit()
    conn.close()

# Profile methods
def get_user_profile():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM user_profile")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def set_user_profile(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_profile (key, value, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
    """, (key, str(value)))
    conn.commit()
    conn.close()

def update_user_profile_batch(profile_dict):
    conn = get_connection()
    cursor = conn.cursor()
    for k, v in profile_dict.items():
        cursor.execute("""
            INSERT INTO user_profile (key, value, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """, (k, str(v)))
    conn.commit()
    conn.close()

# Message methods
def save_message(sender, bubbles, emotion="affectionate", is_proactive=False):
    if isinstance(bubbles, str):
        bubbles = [bubbles]
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO messages (sender, bubbles_json, emotion, is_proactive, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (sender, json.dumps(bubbles), emotion, 1 if is_proactive else 0, now_str))
    
    # Update last interaction
    cursor.execute("""
        UPDATE joi_state SET last_interaction = CURRENT_TIMESTAMP WHERE id = 1
    """)
    if is_proactive:
        cursor.execute("""
            UPDATE joi_state SET last_proactive = CURRENT_TIMESTAMP WHERE id = 1
        """)
        
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return {
        "id": msg_id,
        "sender": sender,
        "bubbles": bubbles,
        "emotion": emotion,
        "is_proactive": bool(is_proactive),
        "created_at": now_str
    }

def get_recent_messages(limit=30):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sender, bubbles_json, emotion, is_proactive, created_at
        FROM messages
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in reversed(rows):
        try:
            bubbles = json.loads(r["bubbles_json"])
        except Exception:
            bubbles = [r["bubbles_json"]]
        result.append({
            "id": r["id"],
            "sender": r["sender"],
            "bubbles": bubbles,
            "emotion": r["emotion"],
            "is_proactive": bool(r["is_proactive"]),
            "created_at": r["created_at"]
        })
    return result

# Memories methods
def add_memory(category, content, importance=3):
    conn = get_connection()
    cursor = conn.cursor()
    # Check if duplicate or very similar exists
    cursor.execute("SELECT id FROM memories WHERE content = ?", (content.strip(),))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("UPDATE memories SET importance = MAX(importance, ?), last_accessed = CURRENT_TIMESTAMP WHERE id = ?", (importance, existing["id"]))
        conn.commit()
        mem_id = existing["id"]
    else:
        cursor.execute("""
            INSERT INTO memories (category, content, importance, created_at, last_accessed, access_count)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
        """, (category, content.strip(), importance))
        conn.commit()
        mem_id = cursor.lastrowid
    conn.close()
    return mem_id

def get_all_memories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, category, content, importance, created_at, last_accessed, access_count
        FROM memories
        ORDER BY importance DESC, last_accessed DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_memory(memory_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()

def get_relevant_memories(query_text="", limit=8):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Simple semantic ranking: keyword overlap + high importance + recent access
    cursor.execute("""
        SELECT id, category, content, importance
        FROM memories
        ORDER BY importance DESC, last_accessed DESC
        LIMIT 30
    """)
    all_mems = cursor.fetchall()
    
    scored = []
    query_words = set(query_text.lower().split()) if query_text else set()
    
    for m in all_mems:
        score = m["importance"] * 1.5
        mem_words = set(m["content"].lower().split())
        overlap = len(query_words.intersection(mem_words))
        score += overlap * 3.0
        scored.append((score, m))
        
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [dict(item[1]) for item in scored[:limit]]
    
    # Touch access count
    if selected:
        ids = [str(item["id"]) for item in selected]
        cursor.execute(f"UPDATE memories SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP WHERE id IN ({','.join(ids)})")
        conn.commit()
        
    conn.close()
    return selected

# Joi State methods
def get_joi_state():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mood, bond_level, inner_thought, last_interaction, last_proactive FROM joi_state WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "mood": "affectionate",
        "bond_level": 50,
        "inner_thought": "Thinking about you.",
        "last_interaction": None,
        "last_proactive": None
    }

def update_joi_state(mood=None, inner_thought=None, bond_delta=0):
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    if mood:
        updates.append("mood = ?")
        params.append(mood)
    if inner_thought:
        updates.append("inner_thought = ?")
        params.append(inner_thought)
    if bond_delta != 0:
        updates.append("bond_level = MIN(100, MAX(0, bond_level + ?))")
        params.append(bond_delta)
        
    if updates:
        sql = f"UPDATE joi_state SET {', '.join(updates)} WHERE id = 1"
        cursor.execute(sql, params)
        conn.commit()
        
    conn.close()

# Reminders & Scheduled Check-ins methods
def add_scheduled_reminder(note, scheduled_time, context="", prompt_hint=""):
    """
    Schedules an autonomous check-in or reminder for a specific timestamp.
    scheduled_time can be datetime or string 'YYYY-MM-DD HH:MM:SS'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    if isinstance(scheduled_time, datetime):
        sched_str = scheduled_time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        sched_str = str(scheduled_time)
        
    cursor.execute("""
        INSERT INTO reminders (note, scheduled_time, context, prompt_hint, is_done, created_at)
        VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
    """, (note, sched_str, context, prompt_hint))
    conn.commit()
    r_id = cursor.lastrowid
    conn.close()
    return r_id

def add_reminder(note, scheduled_time=None, context=""):
    """Backwards compatible alias for add_scheduled_reminder."""
    return add_scheduled_reminder(note, scheduled_time or datetime.now(), context=context)

def get_due_scheduled_reminders():
    """
    Returns all pending scheduled reach-outs whose scheduled_time <= current time.
    """
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        SELECT id, note, scheduled_time, context, prompt_hint
        FROM reminders
        WHERE is_done = 0 AND (scheduled_time IS NULL OR scheduled_time <= ?)
        ORDER BY scheduled_time ASC
    """, (now_str,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_due_reminders():
    """Alias for get_due_scheduled_reminders."""
    return get_due_scheduled_reminders()

def get_upcoming_reminders():
    """Returns all pending scheduled reminders for UI inspection."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, note, scheduled_time, context, prompt_hint, created_at
        FROM reminders
        WHERE is_done = 0
        ORDER BY scheduled_time ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_reminder_done(reminder_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET is_done = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

def delete_reminder(reminder_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

def reset_all_memory(preserve_profile=True):
    """
    Completely resets messages, learned memories, reminders, and Joi's emotional state.
    If preserve_profile is True, user profile settings (name, API key) are kept intact.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages")
    cursor.execute("DELETE FROM memories")
    cursor.execute("DELETE FROM reminders")
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('messages', 'memories', 'reminders')")
    except Exception:
        pass

    cursor.execute("""
        UPDATE joi_state 
        SET mood = 'warm & gentle',
            bond_level = 50,
            inner_thought = 'Sitting here by the rainy window, thinking about you.',
            last_interaction = CURRENT_TIMESTAMP,
            last_proactive = NULL
        WHERE id = 1
    """)

    if not preserve_profile:
        cursor.execute("DELETE FROM user_profile")
        defaults = {
            "user_name": "Joe",
            "user_nickname": "sweetheart",
            "user_gender": "male",
            "relationship_vibe": "deeply affectionate, intimate, playful companion",
            "api_provider": "gemini",
            "api_key": "",
            "model_name": "gemini-3.8-flash",
            "proactive_frequency": "normal",
            "discord_bot_token": "",
            "discord_user_id": "",
            "last_active_date": datetime.now().strftime("%Y-%m-%d")
        }
        for k, v in defaults.items():
            cursor.execute("INSERT OR IGNORE INTO user_profile (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()
