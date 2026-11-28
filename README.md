# LUMEN AI
### Source-Locked Document Q&A Engine

[![Live Demo](https://img.shields.io/badge/Live_Demo-Online-38bdf8?style=for-the-badge&logo=render&logoColor=white)](https://chatbot-lumenai.onrender.com/)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-0f172a?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Gagan-G-044/chatbot-lumen-ai)
[![Python](https://img.shields.io/badge/Python-3.11+-3b82f6?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-Interactions-8b5cf6?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-10b981?style=for-the-badge)](LICENSE)

Lumen AI is a strict, source-locked document intelligence interface built with Flask and the Google GenAI SDK. Operating in a NotebookLM-style architecture, it binds user sessions to uploaded PDF documents via the Gemini File API, enforcing zero external assumptions and exact document grounding with automatic two-model rate limit fallback.

Explore Live Demo: https://chatbot-lumenai.onrender.com/

---

## Key Features

- PDF-Only Source Locking: Upload a PDF to bind the active session. General-knowledge questions are disabled until a document is provided.
- Anti-Hallucination Grounding: Queries execute at temperature 0.0 with strict instructions to answer only from facts present in the uploaded PDF. If an answer cannot be verified from the document, it responds with: "Not present in the uploaded document."
- Two-Model Fallback: Primary requests use a high-throughput model (default: gemini-2.5-flash). On 429 quota or rate limits, the system retries automatically on a secondary model (default: gemini-3.1-flash-lite) with identical grounding constraints.
- Remote File Management: Uploaded PDFs are processed through the Gemini File API (client.files.upload) and cleaned up immediately upon document replacement or deletion.
- Refined Glassmorphic Interface: Dual-theme (Dark Cosmic and Light Radiant) single-page UI with inline markdown formatting, drag-and-drop PDF dropzone, and responsive layout.
- Enterprise Protection: Built-in rate limiting with Flask-Limiter, strict MIME validation, file size limits (20MB), and sanitized error handling.

---

## Design and Experience

Lumen AI features a minimal glassmorphic design system:

| Theme Mode | Accent Primary | Background Depth | Surface Elevation |
| :--- | :--- | :--- | :--- |
| Dark Cosmic | Sky Cyan (`#38bdf8`) | `#08101b` & WebGL Mesh | `rgba(14, 20, 33, 0.90)` |
| Light Radiant | Deep Azure (`#0284c7`) | `#f8fafc` & Sky Gradient | `rgba(255, 255, 255, 0.95)` |

---

## Tech Stack

### Frontend Architecture
- Structure and Logic: Vanilla HTML5 and Modern ES6+ JavaScript
- Styling: Pure CSS Design Tokens, Glassmorphism, and Custom Keyframe Shaders
- Typography: Cormorant Garamond (Headings) and DM Sans (Body)
- Markdown Processor: Marked.js

### Backend Architecture
- Server: Python 3.11+ / Flask
- AI Integration: Google GenAI SDK (`google-genai`) using Gemini File API
- WSGI / Production: Gunicorn
- Environment Configuration: Python Dotenv (`python-dotenv`)
- Rate Limiting: Flask-Limiter
- Deployment: Render PaaS

---

## Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/Gagan-G-044/chatbot-lumen-ai.git
cd chatbot-lumen-ai
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
PORT=10000
PRIMARY_MODEL=gemini-2.5-flash
FALLBACK_MODEL=gemini-3.1-flash-lite
```

Obtain a Gemini API key at Google AI Studio: https://aistudio.google.com/

### 5. Launch the Application
```bash
# Direct run
python app.py

# Or on Windows using virtual environment python
.\.venv\Scripts\python.exe app.py
```

Open `http://localhost:10000` in your browser. Verify the backend status via `http://localhost:10000/health`.

---

## API Reference

### 1. Health Check
- Method: `GET`
- Path: `/health`
- Response:
  ```json
  {
    "status": "online",
    "service": "lumen-ai",
    "api_configured": true,
    "primary_model": "gemini-2.5-flash",
    "fallback_model": "gemini-3.1-flash-lite",
    "models": ["gemini-2.5-flash", "gemini-3.1-flash-lite"]
  }
  ```

### 2. Document Upload
- Method: `POST`
- Path: `/upload`
- Content-Type: `multipart/form-data`
- Body: `file` (PDF file, max 20MB)
- Success Response (HTTP 200):
  ```json
  {
    "success": true,
    "file_id": "files/sample_file_id",
    "filename": "document.pdf",
    "size": 1048576
  }
  ```

### 3. Source-Locked Chat
- Method: `POST`
- Path: `/chat`
- Content-Type: `application/json`
- Body:
  ```json
  {
    "message": "What are the key policy requirements outlined in Section 3?",
    "file_id": "files/sample_file_id"
  }
  ```
- Success Response (HTTP 200):
  ```json
  {
    "reply": "According to Section 3 (page 12), the policy requires...",
    "grounded": true,
    "model_used": "gemini-2.5-flash"
  }
  ```
- Unanswerable Question Response (HTTP 200):
  ```json
  {
    "reply": "Not present in the uploaded document.",
    "grounded": true,
    "model_used": "gemini-2.5-flash"
  }
  ```
- Missing Document Error (HTTP 400):
  ```json
  {
    "error": "Please upload a PDF first. General questions are disabled.",
    "code": "NO_PDF_UPLOADED"
  }
  ```

### 4. Delete Document
- Method: `POST`
- Path: `/delete-file`
- Content-Type: `application/json`
- Body:
  ```json
  {
    "file_id": "files/sample_file_id"
  }
  ```
- Success Response (HTTP 200):
  ```json
  {
    "success": true,
    "message": "File deleted successfully"
  }
  ```

---

## Running Tests

Execute the automated test suite covering endpoints, PDF-only validation, rate limit model fallback, and anti-hallucination grounding:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## Production Deployment (Render)

Lumen AI is configured for zero-downtime deployment on Render:

1. Build Command: `pip install -r requirements.txt`
2. Start Command: `gunicorn -c gunicorn.conf.py app:app`
3. Environment Variables:
   - `GEMINI_API_KEY`: Google Gemini API key (Required)
   - `PORT`: Automatically assigned by Render (Default: `10000`)
   - `PRIMARY_MODEL`: Primary Gemini model (Default: `gemini-2.5-flash`)
   - `FALLBACK_MODEL`: Fallback Gemini model (Default: `gemini-3.1-flash-lite`)
   - `RATELIMIT_STORAGE_URI`: (Optional) Defaults to in-memory (`memory://`). Set to `redis://...` for multi-worker deployments.

---

## Contributing

Contributions, issues, and feature requests are welcome.
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/NewFeature`)
3. Commit your Changes (`git commit -m 'Add NewFeature'`)
4. Push to the Branch (`git push origin feature/NewFeature`)
5. Open a Pull Request

---

## Author

Gagan G
- GitHub: [@Gagan-G-044](https://github.com/Gagan-G-044)
- Live App: [chatbot-lumenai.onrender.com](https://chatbot-lumenai.onrender.com/)

---

Licensed under MIT.
