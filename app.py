from flask import Flask, request, jsonify, send_from_directory
import os
import time
import traceback
from functools import wraps
from google import genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.')

API_KEY = os.getenv("GEMINI_API_KEY")

MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite"
]

REQUEST_COOLDOWN = 3
MAX_MESSAGE_LENGTH = 2000

user_last_request = {}

def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr
        now = time.time()

        if ip in user_last_request:
            if now - user_last_request[ip] < REQUEST_COOLDOWN:
                return jsonify({"reply": "⏳ Wait a few seconds"}), 200

        user_last_request[ip] = now
        return f(*args, **kwargs)

    return decorated

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
@rate_limit
def chat():
    if not API_KEY:
        return jsonify({"reply": "❌ Missing API key"}), 200

    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()

        if not message:
            return jsonify({"reply": "Say something 🙂"}), 200

        if len(message) > MAX_MESSAGE_LENGTH:
            return jsonify({"reply": "Too long 🚫"}), 200

        client = genai.Client(api_key=API_KEY)

        response = None

        for model in MODELS:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=message
                    )
                    break

                except Exception as e:
                    err = str(e).lower()

                    if "429" in err or "quota" in err:
                        time.sleep(3)
                        continue

                    if "404" in err:
                        response = None
                        break

                    raise

            if response:
                break

        if not response:
            return jsonify({"reply": "⚠️ Server busy. Try again later."}), 200

        return jsonify({"reply": response.text}), 200

    except Exception:
        app.logger.error(traceback.format_exc())
        return jsonify({"reply": "🔧 Error occurred"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)