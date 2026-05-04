from google import genai

client = genai.Client(api_key="api here ")

# Create chat session (with memory)
chat = client.chats.create(model="gemini-2.5-flash")

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