from flask import Flask, request, jsonify, send_from_directory
import os
import time
from dotenv import load_dotenv

# Try-except for imports to prevent crash on startup
try:
    from google import genai
    from google.genai.errors import ClientError, ServerError
except ImportError:
    genai = None

load_dotenv()
app = Flask(__name__, static_folder='.')

# Global Client
api_key = os.getenv("GEMINI_API_KEY")
client = None
if genai and api_key:
    client = genai.Client(api_key=api_key)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    # 1. Verification Check
    if not client:
        return jsonify({"reply": "System Error: API Key missing or library not installed."}), 200

    try:
        data = request.get_json(silent=True) or {}
        user_message = data.get("message", "").strip()
        
        if not user_message:
            return jsonify({"reply": "Say something! I can't read minds yet."}), 200

        # 2. Call the BEST Free Model (High Quota: 500 RPD)
        # Using the latest 2026 'flash-lite' model with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=user_message
                )
                break  # Success, exit retry loop
            except Exception as retry_e:
                error_str = str(retry_e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                        time.sleep(wait_time)
                        continue
                    else:
                        raise  # Re-raise after max retries
                else:
                    raise  # Not a quota error, raise immediately

        return jsonify({"reply": response.text})

    except Exception as e:
        # 3. The "No-Crash" Safety Net
        error_msg = str(e)
        app.logger.error(f"API Error: {error_msg}")

        # Handle Quota (429)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return jsonify({"reply": "⚠️ Limit reached! Please wait 15 seconds and try again."}), 200
        
        # Handle Google Server Errors (500/503)
        if "500" in error_msg or "503" in error_msg or "UNAVAILABLE" in error_msg:
            return jsonify({"reply": "🕒 Google's servers are busy. Let's try again in a moment."}), 200

        # Catch-all for any other weird errors
        return jsonify({"reply": "🔧 Something went wrong, but I'm still here! Try sending that again."}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)