# AIClipper Setup Guide

## Prerequisites

### All Platforms
- **Python 3.12** (not 3.13+ due to MediaPipe compatibility)
- **FFmpeg** (required for all video processing)
- **16GB RAM minimum** (recommended for Whisper small model)
- **10GB disk space** for models and output

### Optional
- **Ollama** for AI-powered metadata generation
- **YouTube API credentials** for YouTube Shorts upload
- **Facebook Developer App** for Facebook Reels upload

---

## Windows Setup

### 1. Install Python 3.12
Download from [python.org](https://www.python.org/downloads/).
Check "Add Python to PATH" during installation.

```powershell
python --version  # Should show 3.12.x
```

### 2. Install FFmpeg
Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (ffmpeg-release-essentials.zip).
Extract and add the `bin/` folder to your system PATH.

```powershell
ffmpeg -version  # Verify installation
```

### 3. Install AIClipper
```powershell
cd AIClipper
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m backend.utils.download_models
copy .env.example .env
```

### 4. Run
```powershell
# Terminal 1: Web server
uvicorn backend.api.app:app --reload --port 8000

# Terminal 2: Task queue
python -m backend.workers.consumer
```

---

## Linux Setup (Ubuntu/Debian)

```bash
# System dependencies
sudo apt update
sudo apt install -y python3.12 python3.12-venv ffmpeg

# Install AIClipper
cd AIClipper
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m backend.utils.download_models
cp .env.example .env

# Run
uvicorn backend.api.app:app --reload --port 8000 &
python -m backend.workers.consumer &
```

---

## macOS Setup

```bash
# Install via Homebrew
brew install python@3.12 ffmpeg

# Install AIClipper
cd AIClipper
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m backend.utils.download_models
cp .env.example .env

# Run
uvicorn backend.api.app:app --reload --port 8000 &
python -m backend.workers.consumer &
```

---

## Ollama Setup (Optional)

For AI-powered title/description/hashtag generation:

```bash
# Install Ollama
# Windows: Download from https://ollama.com/download
# Linux: curl -fsSL https://ollama.com/install.sh | sh
# macOS: brew install ollama

# Start Ollama
ollama serve

# Pull a model
ollama pull qwen2    # Recommended
# or: ollama pull llama3, ollama pull gemma2
```

---

## YouTube API Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable **YouTube Data API v3**
4. Configure **OAuth Consent Screen** (add yourself as test user)
5. Create **OAuth 2.0 Client ID** (Desktop app type)
6. Download `client_secret.json` → save as `configs/client_secret_youtube.json`

---

## Facebook API Setup (Optional)

1. Go to [Meta Developer Portal](https://developers.facebook.com/)
2. Create a new app (Business type)
3. Add **Facebook Login** product
4. Request permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
5. Generate a **Page Access Token** with CREATE_CONTENT task
6. Add token and page ID to `.env`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `MediaPipe not found` | Ensure Python 3.12 (not 3.13+) |
| `FFmpeg not found` | Add FFmpeg to PATH, restart terminal |
| `Whisper model not found` | Run `python -m backend.utils.download_models` |
| `Ollama connection refused` | Start Ollama: `ollama serve` |
| `Port 8000 in use` | Use `--port 8001` or kill existing process |
