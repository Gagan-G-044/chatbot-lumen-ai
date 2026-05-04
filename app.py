from flask import Flask, request, jsonify, send_from_directory
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
# The static_folder='.' tells Flask to look in the main folder for files
app = Flask(__name__, static_folder='.')

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
chat = client.chats.create(model="gemini-2.0-flash")

@app.route('/')
def index():
    # This replaces that "Server running" text with your actual HTML file
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    user_message = data.get("message")
    try:
        response = chat.send_message(user_message)
        return jsonify({"bot": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)