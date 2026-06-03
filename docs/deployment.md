# AIClipper Deployment Guide

## Local Development

```bash
# Install
pip install -e ".[dev]"
python -m backend.utils.download_models

# Run (two terminals)
uvicorn backend.api.app:app --reload --port 8000
python -m backend.workers.consumer
```

## Docker Deployment

### One-command startup:
```bash
cd docker
docker-compose up -d
```

### Post-startup:
```bash
# Pull Ollama model
docker exec aiclipper-ollama ollama pull qwen2

# Download Whisper model into container
docker exec aiclipper-app python -m backend.utils.download_models
```

### Check logs:
```bash
docker-compose logs -f aiclipper-app
docker-compose logs -f aiclipper-worker
```

### Stop:
```bash
docker-compose down
```

### Persistent data:
Docker volumes store uploads, outputs, database, and models across restarts.

## Production Considerations

### Behind a Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name aiclipper.local;

    client_max_body_size 4G;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Resource Requirements

| Component | CPU | RAM | Disk |
|-----------|-----|-----|------|
| Whisper (small) | 4 cores | 4 GB | 500 MB |
| MediaPipe | 1 core | 500 MB | 50 MB |
| Ollama (7B) | 4 cores | 8 GB | 4 GB |
| FFmpeg | 2 cores | 1 GB | — |
| **Total** | **4+ cores** | **16 GB** | **5 GB** |

### Security Notes

- Change `SECRET_KEY` in `.env` for production
- Set `APP_DEBUG=false`
- Configure CORS origins in `app.py` for production
- Store API tokens securely
- Use HTTPS behind a reverse proxy
