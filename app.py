"""
Lumen AI — Lightweight, Secure Flask Backend
Academic & Production-ready AI Chatbot Server

Architecture:
  Frontend -> Flask API (/chat) -> Google Gemini API -> JSON Response -> Frontend

Features:
- Single-turn AI inference (conversations are held strictly on client session)
- Singleton Google GenAI client
- Automatic failover between Gemini models (gemini-2.5-flash -> gemini-3.1-flash-lite)
- Built-in rate limiting (Flask-Limiter) to prevent API quota abuse
- Input validation & proper HTTP status codes (200, 400, 413, 429, 503)
- Isolated static file routing (no project root exposure)
"""

import os
import logging
from typing import Optional

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

# Load environment variables (.env)
load_dotenv()

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lumen-backend")

# Base directory for resolving static assets securely
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Flask app (static_folder=None prevents accidental root directory exposure)
app = Flask(__name__, static_folder=None)
CORS(app)

# In-memory per-process rate limiting (supports Redis via RATELIMIT_STORAGE_URI if configured)
storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=storage_uri,
    default_limits=["120 per minute"]
)

# Supported Gemini models in priority order
MODELS = [
    m.strip()
    for m in os.getenv("GEMINI_MODELS", "gemini-2.5-flash,gemini-3.1-flash-lite").split(",")
    if m.strip()
]
MAX_MESSAGE_LENGTH = 2000

# Singleton Google GenAI Client
_client: Optional[genai.Client] = None

def get_genai_client() -> Optional[genai.Client]:
    """Returns a shared Google GenAI client instance."""
    global _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    if _client is None:
        try:
            _client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=15000)
            )
            logger.info("Initialized Google GenAI client.")
        except Exception as e:
            logger.error(f"Failed to initialize GenAI client: {e}")
            return None
    return _client

# Custom error handlers for standard JSON responses
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "error": "Rate limit exceeded. Please wait a moment before sending another message.",
        "code": "RATE_LIMIT_EXCEEDED"
    }), 429

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "error": "Resource not found.",
        "code": "NOT_FOUND"
    }), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "error": "An internal server error occurred.",
        "code": "INTERNAL_ERROR"
    }), 500

# ── ROUTES ──────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """Serves the main chat application interface."""
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/components/<path:filename>", methods=["GET"])
def components_static(filename):
    """Serves static component files safely from the components directory."""
    return send_from_directory(os.path.join(BASE_DIR, "components"), filename)

@app.route("/health", methods=["GET"])
def health():
    """
    Lightweight health check endpoint.
    Indicates server operational status without making external API calls.
    """
    return jsonify({
        "status": "online",
        "service": "lumen-ai",
        "api_configured": bool(os.getenv("GEMINI_API_KEY")),
        "models": MODELS
    }), 200

@app.route("/chat", methods=["POST"])
@limiter.limit(os.environ.get("RATELIMIT_CHAT", "30 per minute; 5 per second"))
def chat():
    """
    Processes a user message and returns an AI-generated response.
    Validates the input and queries Gemini with automated model fallback.
    """
    # 1. Validate JSON body
    if not request.is_json:
        return jsonify({
            "error": "Request body must be valid application/json.",
            "code": "INVALID_JSON"
        }), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "error": "JSON body must be an object.",
            "code": "INVALID_REQUEST_BODY"
        }), 400

    # 2. Validate message field
    raw_message = data.get("message")
    if raw_message is None:
        return jsonify({
            "error": "Field 'message' is required.",
            "code": "MISSING_MESSAGE"
        }), 400

    if not isinstance(raw_message, str):
        return jsonify({
            "error": "Field 'message' must be a string.",
            "code": "INVALID_MESSAGE_TYPE"
        }), 400

    message = raw_message.strip()
    if not message:
        return jsonify({
            "error": "Message cannot be empty.",
            "code": "EMPTY_MESSAGE"
        }), 400

    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "error": f"Message exceeds maximum character length of {MAX_MESSAGE_LENGTH}.",
            "code": "MESSAGE_TOO_LONG"
        }), 413

    # 3. Verify API key & client
    client = get_genai_client()
    if not client:
        return jsonify({
            "error": "Gemini API key is not configured on the server.",
            "code": "API_KEY_MISSING"
        }), 503

    # 4. Generate AI response with model fallback
    response_text = None
    last_error = None

    for model in MODELS:
        try:
            logger.info(f"Generating response using model: {model}")
            res = client.models.generate_content(
                model=model,
                contents=message
            )
            if res and res.text:
                response_text = res.text
                break
        except genai_errors.ClientError as ce:
            last_error = str(ce)
            err_lower = last_error.lower()
            logger.warning(f"ClientError on model '{model}': {err_lower}")

            # If model is deprecated or not found, proceed to next model
            if "404" in err_lower or "not_found" in err_lower:
                continue

            # Authentication failure is unrecoverable via retry
            if "401" in err_lower or "403" in err_lower or "api_key" in err_lower:
                return jsonify({
                    "error": "Gemini API key authentication failed.",
                    "code": "AUTHENTICATION_FAILED"
                }), 503

            continue

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Error on model '{model}': {last_error}")
            continue

    if not response_text:
        logger.error(f"All models failed. Last error: {last_error}")
        return jsonify({
            "error": "All AI models are currently unavailable. Please try again shortly.",
            "code": "PROVIDER_UNAVAILABLE"
        }), 503

    return jsonify({
        "reply": response_text
    }), 200

# ── ENTRYPOINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    logger.info(f"Starting Lumen AI on port {port} (debug={debug})...")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        threaded=True
    )
