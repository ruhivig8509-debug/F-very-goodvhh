"""
Web server module for Render.com deployment
Provides health check endpoint and keeps the service alive
"""

import logging
import threading
from flask import Flask, jsonify
from datetime import datetime

from config import PORT

logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Store bot status
bot_status = {
    "status": "initializing",
    "start_time": None,
    "last_health_check": None
}


@app.route('/')
def home():
    """Root endpoint - returns bot info"""
    return jsonify({
        "name": "Ruhi Ji Bot",
        "status": bot_status["status"],
        "version": "1.0.0",
        "description": "Savage Queen AI Telegram Bot 👑",
        "uptime": str(datetime.utcnow() - bot_status["start_time"]) if bot_status["start_time"] else "N/A"
    })


@app.route('/health')
def health():
    """Health check endpoint for Render and UptimeRobot"""
    bot_status["last_health_check"] = datetime.utcnow()
    return jsonify({
        "status": "healthy",
        "bot_status": bot_status["status"],
        "timestamp": datetime.utcnow().isoformat()
    }), 200


@app.route('/status')
def status():
    """Detailed status endpoint"""
    return jsonify({
        "bot_name": "Ruhi Ji",
        "status": bot_status["status"],
        "start_time": bot_status["start_time"].isoformat() if bot_status["start_time"] else None,
        "last_health_check": bot_status["last_health_check"].isoformat() if bot_status["last_health_check"] else None,
        "message": "Savage Queen is online! 👑💅"
    })


def update_status(new_status: str):
    """Update bot status"""
    bot_status["status"] = new_status
    if new_status == "running" and not bot_status["start_time"]:
        bot_status["start_time"] = datetime.utcnow()


def run_server():
    """Run Flask server in a separate thread"""
    logger.info(f"Starting web server on port {PORT}")
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False,
        use_reloader=False,
        threaded=True
    )


def start_web_server():
    """Start web server in background thread"""
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info("Web server thread started")
    return server_thread
