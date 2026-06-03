#!/bin/bash
set -e

echo "================================================"
echo "   AIClipper - AI Video Clipper v1.0.0"
echo "================================================"
echo ""

# Check Python
if ! command -v python3.12 &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3.12 is required. Install from https://www.python.org/downloads/"
    exit 1
fi
PYTHON=$(command -v python3.12 || command -v python3)

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "[WARNING] FFmpeg not found. Install: sudo apt install ffmpeg (Ubuntu) or brew install ffmpeg (macOS)"
fi

# Create venv
if [ ! -d ".venv" ]; then
    echo "[SETUP] Creating virtual environment..."
    $PYTHON -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install deps
if [ ! -f ".venv/lib/python*/site-packages/fastapi/__init__.py" ] 2>/dev/null; then
    echo "[SETUP] Installing dependencies..."
    pip install -e ".[dev]" --quiet
fi

# Create directories
mkdir -p uploads outputs subtitles thumbnails logs data models temp

# .env
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "[SETUP] Created .env from template."
fi

# Download models
if [ ! -f "models/ggml-small.en.bin" ]; then
    echo ""
    echo "[MODELS] Downloading AI models..."
    python -m backend.utils.download_models
fi

echo ""
echo "================================================"
echo "   Starting AIClipper..."
echo "   Web UI: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Press Ctrl+C to stop"
echo "================================================"
echo ""

# Start worker in background
python -m backend.workers.consumer &
WORKER_PID=$!

# Cleanup on exit
trap "kill $WORKER_PID 2>/dev/null; exit" INT TERM

# Start web server
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

kill $WORKER_PID 2>/dev/null
