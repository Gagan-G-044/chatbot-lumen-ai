from flask import Flask, request, jsonify, send_from_directory
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            app.logger.error("GEMINI_API_KEY is not set")
            return jsonify({"error": "GEMINI_API_KEY is not set"}), 500

        if not request.is_json:
            return jsonify({"error": "Request body must be JSON"}), 400

        data = request.get_json(silent=True)
        if not data or "message" not in data:
            return jsonify({"error": "Missing 'message' in request body"}), 400

        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"error": "Message must not be empty"}), 400

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_message
        )

        reply = getattr(response, "text", None)
        if not reply:
            app.logger.error("Gemini response missing text: %s", response)
            return jsonify({"error": "Generated response was empty"}), 502

        return jsonify({"reply": reply})
    except Exception as e:
        app.logger.exception("Error in /chat route")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000)) # Render uses 10000
    app.run(host='0.0.0.0', port=port)