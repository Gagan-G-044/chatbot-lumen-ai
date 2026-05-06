from flask import Flask, request, jsonify, send_from_directory
import os
import time
import traceback
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# 🔥 MODEL STACK (SAFE + FUTURE PROOF)
MODELS = [
    "gemini-2.5-flash",   # latest (if available)
    "gemini-3.1-flash-lite",   # stable fallback
]

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/chat', methods=['POST'])
def chat():

    if not client:
        return jsonify({"reply": "❌ Missing API key"}), 200

    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()

        if not message:
            return jsonify({"reply": "Say something 🙂"}), 200

        if len(message) > 2000:
            return jsonify({"reply": "Message too long 🚫"}), 200

        response = None

        # 🔁 Try models one by one (smart fallback system)
        for model in MODELS:

            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=message
                    )
                    break  # success → exit retry loop

                except Exception as e:
                    err = str(e)

                    # retry only for quota/server issues
                    if "429" in err or "503" in err or "RESOURCE_EXHAUSTED" in err:
                        time.sleep(min(4, 2 ** attempt))
                        continue

                    # model not found → try next model
                    if "404" in err or "NOT_FOUND" in err:
                        response = None
                        break

                    raise

            if response:
                break  # stop model loop if success

        # If nothing worked
        if not response:
            return jsonify({"reply": "⚠️ All models failed. Try again later."}), 200

        return jsonify({"reply": response.text}), 200

    except Exception:
        app.logger.error(traceback.format_exc())
        return jsonify({"reply": "🔧 Unexpected error"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)