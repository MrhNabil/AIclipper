# AIClipper Architecture

## System Overview

AIClipper follows a modular pipeline architecture where each processing step is an independent service that can be replaced without affecting the overall system.

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Web Frontend                         │
│            (Vanilla HTML/CSS/JS SPA)                     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend                         │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │
│  │ Videos   │ │Processing│ │ Clips   │ │ Publishing │  │
│  │ Router   │ │ Router   │ │ Router  │ │ Router     │  │
│  └──────────┘ └──────────┘ └─────────┘ └────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              Huey Task Queue (SQLite)                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │ process_video_task │ upload_clip_task │ metadata  │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                Processing Pipeline                       │
│                                                          │
│  Transcription ──► Scene Detection ──► Audio Analysis    │
│       │                   │                  │           │
│       └───────── Face Tracking ─────────────┘           │
│                      │                                   │
│               Clip Scoring Engine                        │
│                      │                                   │
│  Clip Generation ──► Subtitles ──► Metadata ──► Thumbs  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   Storage Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ SQLite   │  │ File     │  │ Upload Registry      │  │
│  │ Database │  │ System   │  │ (YouTube, Facebook)  │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Task Queue: Huey over Celery
Huey with SQLite backend was chosen over Celery because:
- No external service dependency (no Redis/RabbitMQ)
- Works natively on Windows (RQ/Dramatiq don't)
- SQLite storage is persistent across restarts
- Ideal for single-machine local deployments

### FFmpeg: subprocess over ffmpeg-python
Direct subprocess calls instead of the ffmpeg-python wrapper because:
- ffmpeg-python hasn't been updated since ~2019
- subprocess gives full control over all FFmpeg features
- More reliable cross-platform behavior
- Easier to debug command-line arguments

### MediaPipe: Tasks API over Solutions API
Using the new Tasks API (`mediapipe.tasks.python.vision`) because:
- The Solutions API (`mp.solutions`) is deprecated
- Tasks API supports VIDEO running mode with timestamps
- Better performance and more accurate models

### Frontend: Vanilla JS over React/Vue
Single-page application using vanilla HTML/CSS/JS because:
- No Node.js build step required
- Served directly by FastAPI
- Simpler deployment
- Sufficient for a local tool's UI complexity

## Database Schema

Tables: `users`, `projects`, `videos`, `transcripts`, `scenes`, `clips`, `subtitles`, `thumbnails`, `uploads`, `settings`

All tables use auto-incrementing integer primary keys, created_at/updated_at timestamps, and cascade deletes via foreign keys.

## Modularity

Each AI service is a standalone module that can be replaced:
- **Transcription**: Swap Whisper.cpp for any STT engine
- **Scene Detection**: Swap PySceneDetect for custom detector
- **Face Tracking**: Swap MediaPipe for YOLO or other detectors
- **Metadata**: Swap Ollama for any LLM (OpenAI, local, etc.)
- **Upload**: Add new platforms via the BaseUploader interface
