import os
from dotenv import load_dotenv
from google import genai

# This looks for your .env file and loads the variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

# Create chat session
chat = client.chats.create(model="gemini-2.0-flash")


print("🤖 AI Chatbot started (type 'exit' to quit)\n")

while True:
    user_input = input("You: ")

    if user_input.lower() == "exit":
        print("Bot: Goodbye 👋")
        break

    try:
        response = chat.send_message(user_input)
        print("Bot:", response.text)
        print()

    except Exception as e:
        print("Error:", e)