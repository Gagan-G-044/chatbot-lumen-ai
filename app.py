from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
import os
from dotenv import load_dotenv

# load env
load_dotenv()

# ✅ CREATE APP FIRST
app = Flask(__name__)
CORS(app)

# API key
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# ✅ THEN routes
@app.route("/")
def home():
    return "Server running ✅"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    msg = data.get("message")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=msg
    )

    return jsonify({"reply": response.text})

# ✅ LAST
if __name__ == "__main__":
    app.run(debug=True)