@echo off
title AIClipper - AI Video Clipper
echo ================================================
echo    AIClipper - AI Video Clipper v1.0.0
echo ================================================
echo.

:: Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.12 from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg is not installed or not in PATH.
    echo Please install FFmpeg from https://ffmpeg.org/download.html
    echo The application may not function correctly without FFmpeg.
    echo.
)

:: Create virtual environment if not exists
if not exist ".venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    echo [SETUP] Virtual environment created.
)

:: Activate virtual environment
echo [SETUP] Activating virtual environment...
call .venv\Scripts\activate.bat

:: Install dependencies if needed
if not exist ".venv\Lib\site-packages\fastapi" (
    echo [SETUP] Installing dependencies (first run)...
    pip install -e ".[dev]" --quiet
    echo [SETUP] Dependencies installed.
)

:: Create required directories
if not exist "uploads" mkdir uploads
if not exist "outputs" mkdir outputs
if not exist "subtitles" mkdir subtitles
if not exist "thumbnails" mkdir thumbnails
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "models" mkdir models
if not exist "temp" mkdir temp

:: Copy .env if not exists
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [SETUP] Created .env from template.
    )
)

:: Check if models exist
if not exist "models\ggml-small.en.bin" (
    echo.
    echo [MODELS] AI models not found. Downloading...
    python -m backend.utils.download_models
    echo.
)

:: Start the application
echo.
echo ================================================
echo    Starting AIClipper...
echo    Web UI: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo    Press Ctrl+C to stop
echo ================================================
echo.

:: Start Huey worker in background
start /B "AIClipper Worker" python -m backend.workers.consumer

:: Start the web server (foreground)
python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

pause
