# AIClipper Pro 🎬✨

An AI-powered, completely local, CPU-friendly desktop application that automatically cuts, crops, and edits long videos into viral, short-form clips (YouTube Shorts, TikTok, Reels).

## 🌟 Features

* **Smart Video Clipping:** Analyzes video for highlights using visual and audio cues.
* **Auto-Editor Pipeline:** One-click generation of fully edited Shorts, including:
  * 3-second animated intro.
  * Face-aware vertical (9:16) cropping and Shorts-style blurred backgrounds.
  * Cinematic color grading and sharpening.
  * **Dynamic Subtitles:** Large, bouncing word-by-word karaoke-style subtitles.
  * **Clickbait Thumbnails:** Automatically selects the most active frame and overlays punchy, high-contrast title text.
* **Local AI Brain:** Uses Ollama (running entirely locally on your CPU) to generate catchy titles, descriptions, and SEO hashtags.
* **No GPU Required:** Heavily optimized FFmpeg pipelines ensure it runs smoothly on standard consumer laptops and CPUs.

## 📋 Prerequisites

Before you begin, ensure you have the following installed on your system:
1. **Python 3.12+** ([Download](https://www.python.org/downloads/))
2. **FFmpeg** (Must be installed and added to your system's PATH)
3. **Ollama** ([Download](https://ollama.com/)) - *Required for the local AI brain.*
4. **Git** (For cloning the repository)

## 🚀 Installation & Setup

### 1. Download the Project
Open your terminal (or Command Prompt/PowerShell) and clone the repository:
```bash
git clone https://github.com/studymatter010-creator/AIclipper_pro.git
cd AIclipper_pro
```

### 2. Open in VS Code (or your preferred editor)
```bash
code .
```

### 3. Setup Virtual Environment
It is highly recommended to use a Python virtual environment to manage dependencies.
**Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
```
**Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Setup the AI Brain (Ollama)
Ensure the Ollama app is running in the background on your computer, then open a terminal and run the following command to download the lightweight, fast AI model used by AIClipper:
```bash
ollama run qwen2.5:1.5b
```
*(You can close the chat prompt that appears by typing `/bye`)*

### 6. Environment Variables
If the project includes a `.env.example` file, copy it to a new file named `.env` and adjust the settings as needed. By default, the app is pre-configured to work out-of-the-box.

---

## 💻 Running the App

1. Ensure your virtual environment is activated.
2. Start the FastAPI backend server by running:
```bash
python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```
3. Open your web browser and navigate to:
👉 **http://localhost:8000**

You are now ready to start clipping! ✂️

## 🛠️ Tech Stack
* **Backend:** FastAPI, Python, SQLAlchemy, SQLite
* **Frontend:** Vanilla JavaScript (SPA), HTML5, CSS3
* **Video Processing:** FFmpeg
* **AI & ML:** Ollama (Qwen2.5), Whisper.cpp, MediaPipe (Face Tracking)
