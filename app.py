"""
Lumen AI — Production-grade Flask backend for celestial conversational AI.
Features:
- Multi-turn conversation memory with server-side validation & role sanitization
- Robust multi-model failover with exponential backoff & jitter
- Configurable Flask-Limiter rate limiting (in-memory per-process fallback; Redis-ready)
- Proper HTTP status codes (200, 400, 413, 429, 500, 503) & consistent JSON error payloads
- Secure static file serving (no project root exposure)
- Independent, zero-dependency health check endpoint
- Production WSGI compatibility (Gunicorn)
"""

import os
import time
import random
import logging
from typing import List, Dict, Any, Optional

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

# Load environment variables
load_dotenv()

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lumen-ai")

# Base directory for safe static file resolution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Flask with static_folder=None to prevent root path traversal
app = Flask(__name__, static_folder=None)

# Enable CORS for cross-origin frontend interactions
CORS(app)

# Rate Limiter setup
# Note on production rate limiting:
# When RATELIMIT_STORAGE_URI is omitted or set to memory://, Flask-Limiter maintains
# an in-memory storage bounded per worker process. For multi-instance horizontal scaling
# or multi-worker WSGI pools on Render, configure a Redis URI (e.g. redis://...) in
# the RATELIMIT_STORAGE_URI environment variable.
storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
if storage_uri == "memory://":
    logger.info("Rate limiter using in-memory storage (per-process). For shared multi-process limiting, set RATELIMIT_STORAGE_URI.")

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=storage_uri,
    default_limits=["120 per minute"]
)

# Configuration constants
DEFAULT_MODELS = ["gemini-2.5-flash", "gemini-3.1-flash-lite"]
MODELS = [m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-2.5-flash,gemini-3.1-flash-lite").split(",") if m.strip()]
MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_ITEM_LENGTH = 4000
MAX_PAYLOAD_BYTES = 32 * 1024  # 32 KB

# Singleton GenAI Client
_client: Optional[genai.Client] = None

def get_genai_client() -> Optional[genai.Client]:
    """Retrieves or lazily instantiates the singleton GenAI client."""
    global _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    if _client is None:
        try:
            _client = genai.Client(api_key=api_key)
            logger.info("Initialized Google GenAI singleton client.")
        except Exception as e:
            logger.error(f"Failed to initialize GenAI client: {e}")
            return None
    return _client

# Custom error handlers for consistent JSON responses
@app.errorhandler(429)
def ratelimit_exceeded(e):
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
    logger.error(f"Unhandled server error: {e}")
    return jsonify({
        "error": "An internal server error occurred.",
        "code": "INTERNAL_ERROR"
    }), 500

# Route: Homepage
@app.route("/", methods=["GET"])
def index():
    """Serves the main application interface."""
    return send_from_directory(BASE_DIR, "index.html")

# Route: Static UI components
@app.route("/components/<path:filename>", methods=["GET"])
def components_static(filename):
    """Serves static assets located in the components/ folder."""
    return send_from_directory(os.path.join(BASE_DIR, "components"), filename)

# Route: Health check
@app.route("/health", methods=["GET"])
def health():
    """
    Lightweight health endpoint.
    Distinguishes application operational status from external API availability
    without leaking keys or invoking billable inference calls.
    """
    has_key = bool(os.getenv("GEMINI_API_KEY"))
    return jsonify({
        "status": "online",
        "service": "lumen-ai",
        "api_configured": has_key,
        "models": MODELS
    }), 200

# Route: Chat inference
@app.route("/chat", methods=["POST"])
@limiter.limit(os.environ.get("RATELIMIT_CHAT", "30 per minute; 5 per second"))
def chat():
    """
    Handles conversational interactions with Gemini multi-model fallback.
    Validates message payload and conversation history to prevent prompt
    injection, impersonation of system instructions, and buffer overflows.
    """
    # 1. Payload size check
    content_length = request.content_length
    if content_length and content_length > MAX_PAYLOAD_BYTES:
        return jsonify({
            "error": "Payload exceeds maximum allowed size (32KB).",
            "code": "PAYLOAD_TOO_LARGE"
        }), 413

    # 2. JSON validation
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

    # 3. Message validation
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

    # 4. History validation & role sanitization
    raw_history = data.get("history", [])
    if not isinstance(raw_history, list):
        return jsonify({
            "error": "Field 'history' must be an array of messages.",
            "code": "INVALID_HISTORY"
        }), 400

    # Cap history length to prevent token exhaustion
    bounded_history = raw_history[-MAX_HISTORY_MESSAGES:]
    validated_contents: List[types.Content] = []

    for item in bounded_history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")

        # Strict role restriction: Only 'user' and 'assistant' are permitted from client.
        # This prevents injection of arbitrary 'system' or 'admin' instructions.
        if role not in ("user", "assistant"):
            continue

        if not isinstance(content, str):
            continue

        sanitized_content = content.strip()
        if not sanitized_content:
            continue

        # Cap length per history item
        if len(sanitized_content) > MAX_HISTORY_ITEM_LENGTH:
            sanitized_content = sanitized_content[:MAX_HISTORY_ITEM_LENGTH]

        # Map frontend 'assistant' role to Gemini's internal 'model' role
        gemini_role = "user" if role == "user" else "model"
        validated_contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=sanitized_content)]
            )
        )

    # Append current message as the latest user turn
    validated_contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)]
        )
    )

    # 5. Client check
    client = get_genai_client()
    if not client:
        return jsonify({
            "error": "Gemini API key is not configured on the server.",
            "code": "API_KEY_MISSING"
        }), 503

    # 6. Model execution with multi-model fallback & exponential backoff
    response_text = None
    last_error_message = None

    for model in MODELS:
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                logger.info(f"Generating content with model '{model}' (attempt {attempt + 1}/{max_attempts})")
                response = client.models.generate_content(
                    model=model,
                    contents=validated_contents
                )
                if response and response.text:
                    response_text = response.text
                    break
            except genai_errors.ClientError as ce:
                err_str = str(ce).lower()
                last_error_message = ce.message if hasattr(ce, "message") else str(ce)
                logger.warning(f"ClientError on model '{model}': {err_str}")

                # If model is not found (404), break immediately to try next model in fallback list
                if "404" in err_str or "not_found" in err_str:
                    logger.warning(f"Model '{model}' not found or deprecated. Skipping.")
                    break

                # If rate-limited or quota exhausted, backoff and retry
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    if attempt < max_attempts - 1:
                        backoff = min(1.0 * (2 ** attempt) + random.uniform(0.1, 0.5), 4.0)
                        logger.info(f"Rate limited on '{model}'. Backing off for {backoff:.2f}s...")
                        time.sleep(backoff)
                        continue
                    break

                # For authentication errors, stop immediately
                if "401" in err_str or "403" in err_str or "api_key" in err_str:
                    logger.error("Authentication failure with Gemini API.")
                    return jsonify({
                        "error": "Gemini API authentication failed. Please verify the API key.",
                        "code": "AUTHENTICATION_FAILED"
                    }), 503

                break

            except genai_errors.APIError as ae:
                err_str = str(ae).lower()
                last_error_message = str(ae)
                logger.warning(f"APIError on model '{model}': {err_str}")
                if "503" in err_str or "unavailable" in err_str:
                    if attempt < max_attempts - 1:
                        backoff = min(1.0 * (2 ** attempt) + random.uniform(0.1, 0.5), 4.0)
                        logger.info(f"Service unavailable on '{model}'. Backing off for {backoff:.2f}s...")
                        time.sleep(backoff)
                        continue
                break

            except Exception as e:
                err_str = str(e).lower()
                last_error_message = str(e)
                logger.warning(f"Unexpected error with model '{model}': {err_str}")
                if attempt < max_attempts - 1 and ("timeout" in err_str or "connection" in err_str):
                    time.sleep(1.0)
                    continue
                break

        if response_text:
            break

    # 7. Check if response was successfully generated
    if not response_text:
        logger.error(f"All models failed. Last error: {last_error_message}")
        return jsonify({
            "error": "All AI models are currently busy or unavailable. Please try again shortly.",
            "code": "PROVIDER_UNAVAILABLE"
        }), 503

    return jsonify({
        "reply": response_text
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    logger.info(f"Starting Lumen AI development server on port {port} (debug={debug})...")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        threaded=True
    )
