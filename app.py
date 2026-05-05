from flask import Flask, request, jsonify, send_from_directory
import os
import time
from dotenv import load_dotenv

try:
    from google import genai
    from google.genai.errors import ClientError
except ImportError:
    genai = None
    ClientError = None

load_dotenv()
app = Flask(__name__, static_folder='.')

# 1. Initialize the client ONCE outside the route to save resources
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if genai and api_key else None

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        if not api_key or not client:
            return jsonify({"error": "Gemini API Client not initialized. Check API Key."}), 500

        if not request.is_json:
            return jsonify({"error": "Request body must be JSON"}), 400

        data = request.get_json(silent=True)
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"error": "Message must not be empty"}), 400

        # 2. Call the model
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_message
        )

        reply = getattr(response, "text", None)
        if not reply:
            return jsonify({"error": "Generated response was empty"}), 502

        return jsonify({"reply": reply})

    except Exception as e:
        # 3. Specific handling for Quota/Rate Limits
        if ClientError is not None and isinstance(e, ClientError):
            # Check for 429 specifically
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                app.logger.warning("Quota exhausted (429). Informing the user.")
                return jsonify({
                    "error": "The AI is currently at maximum capacity for its free tier. Please try again in a few minutes.",
                    "code": "QUOTA_EXCEEDED"
                }), 429 # Return 429 instead of 500

            return jsonify({"error": str(e)}), 400

        app.logger.exception("Internal Server Error")
        return jsonify({"error": "An unexpected server error occurred."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)