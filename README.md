<div align="center">

  <img src="https://raw.githubusercontent.com/Gagan-G-044/chatbot-lumen-ai/main/components/ui/banner.png" alt="Lumen AI Banner" width="100%" style="border-radius: 12px; margin-bottom: 20px;" onerror="this.style.display='none'"/>

  # ✦ LUMEN AI
  ### The Intelligent, Glassmorphic AI Chat Experience

  [![Live Demo](https://img.shields.io/badge/Live_Demo-Online-38bdf8?style=for-the-badge&logo=render&logoColor=white)](https://chatbot-lumenai.onrender.com/)
  [![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-0f172a?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Gagan-G-044/chatbot-lumen-ai)
  [![Python](https://img.shields.io/badge/Python-3.11+-3b82f6?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
  [![Google Gemini](https://img.shields.io/badge/Google_Gemini-Interactions-8b5cf6?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-10b981?style=for-the-badge)](LICENSE)

  <p align="center">
    <b>Lumen AI</b> is a high-performance conversational AI interface inspired by celestial glassmorphism, fluid micro-interactions, and real-time generative intelligence powered by the <b>Google Gemini API</b>.
  </p>

  <p align="center">
    <a href="https://chatbot-lumenai.onrender.com/"><strong>Explore Live Demo »</strong></a>
    <br />
    <br />
    <a href="#-key-features">Key Features</a> •
    <a href="#-design--experience">Design & UI</a> •
    <a href="#-tech-stack">Tech Stack</a> •
    <a href="#-getting-started">Getting Started</a> •
    <a href="#-configuration">Configuration</a>
  </p>
</div>

---

## 🌟 Key Features

- **⚡ Google Gemini Multi-Model Fallback**: Direct integration with Gemini 2.5 / 3.1 Flash series models with automated failover logic for resilient, uninterrupted response delivery.
- **💫 Magic UI Border Beam & Ambient Effects**: Custom perimeter-following glowing light beams and WebGL animated simplex-noise topographic contour mesh.
- **💎 Refined Glassmorphism UI**: High-contrast, dark/light celestial themes using tokenized typography (`Cormorant Garamond` + `DM Sans`) and backdrop blur filters.
- **🛡️ Intelligent Rate-Limiting & Security**: Built-in request cooldown throttles and payload caps to protect against malicious abuse.
- **📝 Rich Markdown & Code Formatting**: High-fidelity markdown rendering with marked.js for mathematical expressions, code blocks, lists, and formatted tables.
- **📱 Fully Responsive**: Fluid adaptive layout tested across mobile, tablet, and ultra-wide desktop viewports.

---

## 🎨 Design & Experience

Lumen AI is built upon an intentional design system defined in [`.agents/skills/brand-identity`](.agents/skills/brand-identity/SKILL.md):

| Theme Mode | Accent Primary | Background Depth | Surface Elevation |
| :--- | :--- | :--- | :--- |
| **Dark Cosmic** | Sky Cyan (`#38bdf8`) | `#08101b` & WebGL Mesh | `rgba(14, 20, 33, 0.90)` |
| **Light Radiant** | Deep Azure (`#0284c7`) | `#f8fafc` & Sky Gradient | `rgba(255, 255, 255, 0.95)` |

---

## 🛠 Tech Stack

### Frontend Architecture
- **Structure & Logic:** Vanilla HTML5 & Modern ES6+ JavaScript
- **Styling Engine:** Pure CSS Design Tokens, Glassmorphism & Custom Keyframe Shaders
- **Micro-Components:** Custom Web Components (`<border-beam>`) inspired by Magic UI
- **Typography:** Cormorant Garamond (Editorial Headings) & DM Sans (UI Body)
- **Markdown Processor:** Marked.js

### Backend Architecture
- **Server:** Python 3.11+ / Flask Framework
- **AI Integration:** Google GenAI SDK (`google-genai`)
- **WSGI / Production:** Gunicorn Engine
- **Environment Management:** Python Dotenv (`python-dotenv`)
- **Hosting:** Render PaaS

---

## 🚀 Getting Started

Follow these steps to get a local instance up and running in minutes:

### 1. Clone the Repository
```bash
git clone https://github.com/Gagan-G-044/chatbot-lumen-ai.git
cd chatbot-lumen-ai
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
PORT=10000
```

> [!TIP]
> Obtain a Gemini API key at [Google AI Studio](https://aistudio.google.com/).

### 5. Launch the Application
```bash
# Directly with Python
python app.py

# Or on Windows with venv interpreter
.\venv\Scripts\python.exe app.py
```

Visit **`http://localhost:10000`** in your browser. Verify the backend with the health endpoint at `http://localhost:10000/health`.

---

## 📡 API Reference

### Health Check
- **Endpoint:** `GET /health`
- **Response:**
  ```json
  { "status": "online" }
  ```

### Chat Completion
- **Endpoint:** `POST /chat`
- **Headers:** `Content-Type: application/json`
- **Body:**
  ```json
  { "message": "Explain quantum entanglement in simple terms" }
  ```
- **Response:**
  ```json
  { "reply": "Quantum entanglement occurs when..." }
  ```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 👨‍💻 Author

**Gagan G**
- GitHub: [@Gagan-G-044](https://github.com/Gagan-G-044)
- Live App: [chatbot-lumenai.onrender.com](https://chatbot-lumenai.onrender.com/)

---

<div align="center">
  <sub>Built with care & aesthetic excellence © 2026 Gagan G. Licensed under MIT.</sub>
</div>
