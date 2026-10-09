"""
Joi - Blade Runner 2049 AI Companion
Entry point for running the companion server.
"""
import os
import sys
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("\n=======================================================")
    print(" [JOI] Blade Runner 2049 AI Companion is running!")
    print(f" Web Interface: http://localhost:{port}")
    print("=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
