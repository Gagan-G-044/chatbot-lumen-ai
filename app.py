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
import tempfile
from typing import Optional
from werkzeug.utils import secure_filename

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

# Primary and fallback model configuration (strictly 2-model fallback, configurable via env)
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL") or os.getenv("GEMINI_PRIMARY_MODEL")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL") or os.getenv("GEMINI_FALLBACK_MODEL")

if not PRIMARY_MODEL or not FALLBACK_MODEL:
    legacy_models = [
        m.strip()
        for m in os.getenv("GEMINI_MODELS", "gemini-2.5-flash,gemini-3.1-flash-lite").split(",")
        if m.strip()
    ]
    if not PRIMARY_MODEL:
        PRIMARY_MODEL = legacy_models[0] if len(legacy_models) > 0 else "gemini-2.5-flash"
    if not FALLBACK_MODEL:
        FALLBACK_MODEL = legacy_models[1] if len(legacy_models) > 1 else "gemini-3.1-flash-lite"

MODELS = [PRIMARY_MODEL, FALLBACK_MODEL]
MAX_MESSAGE_LENGTH = 2000

# Allowed file formats & size limits for PDF-only document QA
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB limit

STRICT_GROUNDING_INSTRUCTION = (
    "You are a strict, source-locked document Q&A assistant (NotebookLM style).\n"
    "CRITICAL INSTRUCTIONS:\n"
    "1. Answer the user's question using ONLY explicit facts directly mentioned in the attached PDF.\n"
    "2. Cite exact page numbers, section titles, or verbatim quote evidence from the PDF wherever available.\n"
    "3. Make ZERO assumptions, extrapolations, or outside world knowledge.\n"
    "4. If the answer is not explicitly supported by the attached PDF, you MUST respond EXACTLY with the phrase:\n"
    "   'Not present in the uploaded document.'\n"
    "5. Never attempt to answer from general knowledge."
)

def allowed_file(filename: str) -> bool:
    """Returns True if the filename has an allowed extension (.pdf only)."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def is_rate_limit_error(exc: Exception) -> bool:
    """
    Checks if an exception represents a rate limit / quota exhaustion
    (e.g. HTTP 429 or RESOURCE_EXHAUSTED).
    """
    if isinstance(exc, genai_errors.ClientError):
        code = getattr(exc, "code", None)
        if code == 429:
            return True

    err_str = str(exc).lower()
    return (
        "429" in err_str
        or "resource_exhausted" in err_str
        or "quota" in err_str
        or "rate limit" in err_str
    )

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
                http_options=types.HttpOptions(api_version="v1beta", timeout=30000)
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
        "primary_model": PRIMARY_MODEL,
        "fallback_model": FALLBACK_MODEL,
        "models": MODELS
    }), 200

@app.route("/upload", methods=["POST"])
@limiter.limit("15 per minute")
def upload_file():
    """
    Uploads a document to Google Gemini File API for grounded document QA.
    Validates file format and size, stores in a temporary file, uploads to Gemini,
    and immediately deletes the local temporary file.
    """
    client = get_genai_client()
    if not client:
        return jsonify({
            "error": "Gemini API key is not configured on the server.",
            "code": "API_KEY_MISSING"
        }), 503

    if "file" not in request.files:
        return jsonify({
            "error": "No file part in request.",
            "code": "MISSING_FILE"
        }), 400

    file = request.files["file"]
    if not file or not file.filename or not file.filename.strip():
        return jsonify({
            "error": "No selected file.",
            "code": "EMPTY_FILENAME"
        }), 400

    original_filename = secure_filename(file.filename.strip())
    if not allowed_file(original_filename):
        return jsonify({
            "error": "Only PDF files are supported. Please upload a .pdf document.",
            "code": "INVALID_FILE_TYPE"
        }), 400

    content = file.read()
    if len(content) > MAX_FILE_SIZE:
        return jsonify({
            "error": f"File exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)} MB.",
            "code": "FILE_TOO_LARGE"
        }), 413

    suffix = "." + original_filename.rsplit(".", 1)[1].lower() if "." in original_filename else ""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name

    try:
        temp_file.write(content)
        temp_file.close()

        logger.info(f"Uploading file '{original_filename}' ({len(content)} bytes) to Gemini File API...")
        uploaded_file = client.files.upload(
            file=temp_path,
            config=types.UploadFileConfig(display_name=original_filename)
        )
        logger.info(f"Successfully uploaded to Gemini as '{uploaded_file.name}'")

        return jsonify({
            "file_id": uploaded_file.name,
            "file_name": original_filename,
            "mime_type": uploaded_file.mime_type or "application/octet-stream",
            "size_bytes": len(content)
        }), 200

    except Exception as e:
        logger.error(f"Failed to upload file to Gemini File API: {e}")
        return jsonify({
            "error": f"Failed to upload file to Gemini API: {str(e)}",
            "code": "UPLOAD_FAILED"
        }), 500

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as ex:
                logger.warning(f"Failed to remove temporary file {temp_path}: {ex}")

@app.route("/delete-file", methods=["POST"])
@limiter.limit("30 per minute")
def delete_file():
    """
    Deletes an uploaded file from Gemini File API when detached or session resets.
    """
    client = get_genai_client()
    if not client:
        return jsonify({
            "error": "Gemini API key is not configured on the server.",
            "code": "API_KEY_MISSING"
        }), 503

    if not request.is_json:
        return jsonify({
            "error": "Request body must be valid application/json.",
            "code": "INVALID_JSON"
        }), 400

    data = request.get_json(silent=True) or {}
    file_id = data.get("file_id")
    if not file_id or not isinstance(file_id, str) or not file_id.startswith("files/"):
        return jsonify({
            "error": "Field 'file_id' must be a valid Gemini file identifier (e.g. 'files/...').",
            "code": "INVALID_FILE_ID"
        }), 400

    try:
        logger.info(f"Deleting file '{file_id}' from Gemini...")
        client.files.delete(name=file_id)
        return jsonify({
            "status": "deleted",
            "file_id": file_id
        }), 200
    except Exception as e:
        logger.warning(f"Error deleting file '{file_id}': {e}")
        return jsonify({
            "status": "deleted_or_expired",
            "file_id": file_id
        }), 200

@app.route("/chat", methods=["POST"])
@limiter.limit(os.environ.get("RATELIMIT_CHAT", "30 per minute; 5 per second"))
def chat():
    """
    Processes a user message and returns an AI-generated response.
    Supports grounded document QA when file_id is provided, otherwise conversational mode.
    Validates input and queries Gemini with automated model fallback.
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

    # Mandatory file_id validation for source-locked PDF QA
    file_id = data.get("file_id")
    if not file_id:
        return jsonify({
            "error": "Please upload a PDF first. General questions are disabled.",
            "code": "NO_PDF_UPLOADED"
        }), 400

    if not isinstance(file_id, str) or not file_id.startswith("files/"):
        return jsonify({
            "error": "Field 'file_id' must be a valid Gemini file identifier.",
            "code": "INVALID_FILE_ID"
        }), 400

    # 3. Verify API key & client
    client = get_genai_client()
    if not client:
        return jsonify({
            "error": "Gemini API key is not configured on the server.",
            "code": "API_KEY_MISSING"
        }), 503

    # Retrieve remote PDF reference
    try:
        uploaded_file = client.files.get(name=file_id)
    except Exception as e:
        logger.error(f"Failed to retrieve file '{file_id}' from Gemini: {e}")
        return jsonify({
            "error": "The attached PDF could not be found or has expired. Please re-upload.",
            "code": "FILE_NOT_FOUND"
        }), 404

    # 4. Generate AI response with strictly 2-model fallback (no Live API)
    # Step 4a: Call PRIMARY_MODEL with temperature=0.0 and strict document grounding
    response_text = None
    model_used = None
    last_error = None

    try:
        logger.info(f"Generating source-locked response using primary model: {PRIMARY_MODEL}")
        res = client.models.generate_content(
            model=PRIMARY_MODEL,
            contents=[uploaded_file, message],
            config=types.GenerateContentConfig(
                system_instruction=STRICT_GROUNDING_INSTRUCTION,
                temperature=0.0
            )
        )
        if res and res.text:
            response_text = res.text
            model_used = PRIMARY_MODEL
    except genai_errors.ClientError as ce:
        last_error = ce
        err_lower = str(ce).lower()
        logger.warning(f"ClientError on primary model '{PRIMARY_MODEL}': {err_lower}")

        # Authentication failure cannot be recovered by model fallback
        if "401" in err_lower or "403" in err_lower or "api_key" in err_lower:
            return jsonify({
                "error": "Gemini API key authentication failed.",
                "code": "AUTHENTICATION_FAILED"
            }), 503

    except Exception as e:
        last_error = e
        logger.warning(f"Error on primary model '{PRIMARY_MODEL}': {e}")

    # Step 4b: Fallback to FALLBACK_MODEL if primary model failed (rate limit 429 / RESOURCE_EXHAUSTED or failure)
    if not response_text and FALLBACK_MODEL and FALLBACK_MODEL != PRIMARY_MODEL:
        try:
            logger.info(f"Attempting single fallback to model: {FALLBACK_MODEL}")
            res = client.models.generate_content(
                model=FALLBACK_MODEL,
                contents=[uploaded_file, message],
                config=types.GenerateContentConfig(
                    system_instruction=STRICT_GROUNDING_INSTRUCTION,
                    temperature=0.0
                )
            )
            if res and res.text:
                response_text = res.text
                model_used = FALLBACK_MODEL
        except genai_errors.ClientError as ce:
            last_error = ce
            err_lower = str(ce).lower()
            logger.warning(f"ClientError on fallback model '{FALLBACK_MODEL}': {err_lower}")

            if "401" in err_lower or "403" in err_lower or "api_key" in err_lower:
                return jsonify({
                    "error": "Gemini API key authentication failed.",
                    "code": "AUTHENTICATION_FAILED"
                }), 503

        except Exception as e:
            last_error = e
            logger.warning(f"Error on fallback model '{FALLBACK_MODEL}': {e}")

    if not response_text:
        logger.error(f"Both primary and fallback models failed. Last error: {last_error}")
        if last_error and is_rate_limit_error(last_error):
            return jsonify({
                "error": "Rate limit exceeded on all AI models. Please wait a moment before trying again.",
                "code": "RATE_LIMIT_EXCEEDED"
            }), 429

        return jsonify({
            "error": "All AI models are currently unavailable. Please try again shortly.",
            "code": "PROVIDER_UNAVAILABLE"
        }), 503

    return jsonify({
        "reply": response_text,
        "grounded": bool(uploaded_file),
        "model_used": model_used
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
