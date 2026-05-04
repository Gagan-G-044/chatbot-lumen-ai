from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

# ✅ NEW CLIENT
client = genai.Client(api_key="AIzaSyCEPqU1e0ICnwsRZ7JfkJrmDwEUOy2xVaQ")

@app.route("/")
def home():
    return "Server is running ✅"

@app.route("/chat", methods=["POST"])
def chat_api():
    try:
        data = request.get_json()
        msg = data.get("message")

        if not msg:
            return jsonify({"reply": "No message received"}), 400

        # 🔥 NEW API CALL
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=msg
        )

        return jsonify({"reply": response.text})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"reply": "Server error: " + str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)