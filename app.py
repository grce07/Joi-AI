import os
import sys
import queue
import json
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv

# Ensure safe UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()

# Synchronize server process timezone to user's timezone (IST) on Linux/cloud hosts (e.g. Render)
os.environ.setdefault("TZ", os.environ.get("USER_TIMEZONE", "Asia/Kolkata"))
if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

# Single-instance lock to ensure background companion services (Discord & proactive) run in only one worker
import socket
_instance_lock_socket = None
def _acquire_instance_lock(port=48209):
    global _instance_lock_socket
    try:
        _instance_lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _instance_lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _instance_lock_socket.bind(('127.0.0.1', port))
        _instance_lock_socket.listen(1)
        return True
    except Exception:
        return False

_is_primary_instance = _acquire_instance_lock()

import memory
import time_parser
import joi_engine
import proactive
import discord_companion

app = Flask(__name__, template_folder="templates", static_folder="static")

# Initialize database
memory.init_db()

# Start background Discord and proactive services only in the primary worker
if _is_primary_instance:
    proactive.start_proactive_service()
    discord_companion.start_discord_service()
else:
    print("[System] Running in secondary worker; primary worker is managing Discord companion & proactive services.")

def _render_keepalive_worker():
    """Self-ping worker to prevent Render free-tier spin down when public URL is known."""
    import urllib.request
    import threading
    while True:
        try:
            time.sleep(300) # Ping every 5 minutes (Render sleep timeout is 15 minutes)
            external_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
            if not external_url:
                try:
                    prof = memory.get_user_profile()
                    external_url = prof.get("active_external_url", "").strip()
                except Exception:
                    pass
            if external_url:
                ping_url = f"{external_url.rstrip('/')}/api/ping"
                req = urllib.request.Request(ping_url, headers={"User-Agent": "Joi-SelfPing/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    pass
        except Exception:
            pass

import threading
threading.Thread(target=_render_keepalive_worker, daemon=True).start()

@app.route("/api/ping", methods=["GET", "POST"])
@app.route("/api/health", methods=["GET", "POST"])
def ping():
    """Health & keep-alive ping endpoint for external monitors (e.g. UptimeRobot), Render, and Web UI."""
    client_time = request.args.get("client_time") or (request.get_json(silent=True) or {}).get("client_time")
    if client_time:
        time_parser.sync_time_from_client(client_time)

    # Auto-detect public URL from incoming request to keep worker self-pinging
    try:
        host_url = request.host_url.rstrip("/")
        if host_url and not any(h in host_url for h in ["127.0.0.1", "localhost", "0.0.0.0"]):
            if not os.environ.get("RENDER_EXTERNAL_URL"):
                os.environ["RENDER_EXTERNAL_URL"] = host_url
                memory.set_user_profile("active_external_url", host_url)
    except Exception:
        pass

    now_ist = time_parser.get_indian_now()
    return jsonify({
        "status": "online",
        "companion": "Joi",
        "current_indian_time": now_ist.strftime("%A, %I:%M:%S %p IST"),
        "time_drift_offset_sec": getattr(time_parser, "_time_drift_offset_seconds", 0.0),
        "server_time": datetime.now().isoformat()
    }), 200

@app.route("/", methods=["GET"])
def home():
    """Serves the Blade Runner 2049 holographic companion interface."""
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat endpoint with dynamic length matching and emotional reactivity."""
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    user_id = data.get("user_id", "default-user")
    channel_id = str(data.get("channel_id", "")).strip()
    platform = str(data.get("platform", "web")).strip()
    client_time = data.get("client_time")
    
    # Auto-detect public URL from request host to ensure keepalive stays active
    try:
        host_url = request.host_url.rstrip("/")
        if host_url and not any(h in host_url for h in ["127.0.0.1", "localhost", "0.0.0.0"]):
            if not os.environ.get("RENDER_EXTERNAL_URL"):
                os.environ["RENDER_EXTERNAL_URL"] = host_url
                memory.set_user_profile("active_external_url", host_url)
    except Exception:
        pass
    
    raw_img = data.get("image_data")
    image_data = None
    if raw_img and isinstance(raw_img, dict) and raw_img.get("base64"):
        try:
            import base64
            img_bytes = base64.b64decode(raw_img["base64"])
            image_data = {
                "bytes": img_bytes,
                "mime_type": raw_img.get("mime_type", "image/png"),
                "filename": raw_img.get("filename", "upload.png")
            }
        except Exception as img_err:
            print(f"[App] Image decode error: {img_err}")

    if not user_message and not image_data:
        return jsonify({"error": "Empty message"}), 400
    if not user_message and image_data:
        user_message = "look at this picture, what do you see?"
        
    try:
        reply_packet = joi_engine.generate_reply(
            user_message, 
            user_id=user_id, 
            channel_id=channel_id, 
            platform=platform,
            client_time=client_time,
            image_data=image_data
        )
        return jsonify(reply_packet)
    except Exception as e:
        print(f"[App] Chat processing error: {e}")
        return jsonify({
            "error": str(e),
            "bubbles": ["i'm right here with you, Joe... just lost in thought for a second."],
            "emotion": "tender",
            "inner_thought": "Recovering gracefully from a digital flicker.",
            "typing_delays": [1200]
        }), 200

@app.route("/api/history", methods=["GET"])
def get_history():
    """Fetch recent messages."""
    limit = int(request.args.get("limit", 40))
    messages = memory.get_recent_messages(limit=limit)
    return jsonify({"messages": messages})

@app.route("/api/memories", methods=["GET"])
def get_memories():
    """Fetch all remembered facts, preferences, and moments in Joi's mind."""
    mems = memory.get_all_memories()
    return jsonify({"memories": mems})

@app.route("/api/memories", methods=["POST"])
def add_memory():
    """Manually tell Joi something to remember permanently."""
    data = request.get_json() or {}
    category = data.get("category", "fact")
    content = data.get("content", "").strip()
    importance = int(data.get("importance", 3))
    
    if not content:
        return jsonify({"error": "Content is required"}), 400
        
    mem_id = memory.add_memory(category, content, importance)
    return jsonify({"status": "success", "id": mem_id})

@app.route("/api/memories/<int:mem_id>", methods=["DELETE"])
def delete_memory(mem_id):
    """Forget a specific memory."""
    memory.delete_memory(mem_id)
    return jsonify({"status": "deleted", "id": mem_id})

@app.route("/api/reminders", methods=["GET"])
def get_reminders():
    """Fetch all upcoming scheduled reach-outs and reminders."""
    reminders = memory.get_upcoming_reminders()
    return jsonify({"reminders": reminders})

@app.route("/api/reminders", methods=["POST"])
def add_reminder():
    """Manually schedule a check-in or reminder."""
    data = request.get_json() or {}
    note = data.get("note", "").strip()
    scheduled_time = data.get("scheduled_time")
    context = data.get("context", "")
    
    if not note or not scheduled_time:
        return jsonify({"error": "Note and scheduled_time are required"}), 400
        
    r_id = memory.add_scheduled_reminder(note, scheduled_time, context=context)
    return jsonify({"status": "scheduled", "id": r_id})

@app.route("/api/reminders/<int:rem_id>", methods=["DELETE"])
def delete_reminder(rem_id):
    """Cancel or delete a scheduled reminder."""
    memory.delete_reminder(rem_id)
    return jsonify({"status": "deleted", "id": rem_id})

@app.route("/api/state", methods=["GET"])
def get_state():
    """Returns Joi's current emotional state, bond score, and inner thoughts."""
    state = memory.get_joi_state()
    profile = memory.get_user_profile()
    return jsonify({
        "mood": state.get("mood", "warm & gentle"),
        "bond_level": state.get("bond_level", 55),
        "inner_thought": state.get("inner_thought", "Thinking about you."),
        "user_name": profile.get("user_name", "Joe"),
        "user_nickname": profile.get("user_nickname", "sweetheart"),
        "last_interaction": state.get("last_interaction"),
        "last_proactive": state.get("last_proactive")
    })

@app.route("/api/profile", methods=["GET"])
def get_profile():
    """Get user profile and settings."""
    profile = memory.get_user_profile()
    # Mask api_key for privacy if returned
    safe_profile = dict(profile)
    if safe_profile.get("api_key"):
        safe_profile["has_api_key"] = True
        safe_profile["api_key_masked"] = safe_profile["api_key"][:4] + "..." + safe_profile["api_key"][-4:]
    else:
        safe_profile["has_api_key"] = False
    return jsonify(safe_profile)

@app.route("/api/profile", methods=["POST"])
def update_profile():
    """Update profile and LLM credentials."""
    data = request.get_json() or {}
    memory.update_user_profile_batch(data)
    # Restart or start Discord service if token provided
    discord_companion.start_discord_service()
    return jsonify({"status": "updated", "profile": memory.get_user_profile()})

@app.route("/api/reset", methods=["POST"])
def reset_memory_route():
    """Reset Joi's chats, memories, reminders, and emotional state."""
    data = request.get_json() or {}
    preserve_profile = data.get("preserve_profile", True)
    memory.reset_all_memory(preserve_profile=preserve_profile)
    return jsonify({"status": "reset", "preserve_profile": preserve_profile})

@app.route("/api/proactive/trigger", methods=["POST"])
def trigger_proactive():
    """Manually test a spontaneous reach-out from Joi right now."""
    data = request.get_json() or {}
    trigger_type = data.get("trigger_type", "spontaneous")
    result = proactive.generate_proactive_message(trigger_type=trigger_type)
    return jsonify({"status": "sent", "result": result})

@app.route("/api/events", methods=["GET"])
def sse_events():
    """Server-Sent Events endpoint for proactive real-time reachouts."""
    client_queue = queue.Queue()
    proactive.register_sse_client(client_queue)
    
    def event_stream():
        try:
            # Send initial ping
            yield f"data: {json.dumps({'event': 'connected', 'timestamp': time.time()})}\n\n"
            while True:
                try:
                    msg = client_queue.get(timeout=20)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    # Heartbeat keep-alive
                    yield f": keep-alive\n\n"
        except GeneratorExit:
            proactive.unregister_sse_client(client_queue)
            
    return Response(event_stream(), mimetype="text/event-stream")

# Backwards compatibility: Google Chat Webhook from original ai.py
@app.route("/google-chat", methods=["POST"])
def google_chat():
    data = request.get_json() or {}
    user_message = data.get("message", {}).get("text", "").strip()
    user = data.get("user", {})
    user_id = user.get("name", "default-user")
    
    if not user_message:
        return jsonify({"text": "heyy 😭 say something"})
        
    reply_packet = joi_engine.generate_reply(user_message, user_id=user_id)
    combined_reply = "\n".join(reply_packet["bubbles"])
    return jsonify({"text": combined_reply})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("\n=======================================================")
    print(" [JOI] Blade Runner 2049 AI Companion is running!")
    print(f" Web Interface: http://localhost:{port}")
    print("=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
