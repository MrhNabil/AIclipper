# AIClipper API Reference

Base URL: `http://localhost:8000/api`

Interactive docs: `http://localhost:8000/docs`

## Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |

### Videos
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/upload` | Upload video (multipart/form-data) |
| GET | `/api/videos` | List videos (query: offset, limit, project_id) |
| GET | `/api/videos/{id}` | Get video details with clips and transcripts |

### Processing
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/process/{video_id}` | Start AI processing pipeline |
| GET | `/api/status/{video_id}` | Get processing status and progress |
| WS | `/api/ws/progress/{video_id}` | Real-time progress via WebSocket |

### Clips
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/clips` | List clips (query: offset, limit, video_id) |
| GET | `/api/clips/{id}` | Get clip details with subtitles/thumbnails |
| DELETE | `/api/clips/{id}` | Delete a clip |
| GET | `/api/clips/{id}/download` | Download clip file |

### Publishing
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/publish` | Publish clip to platform |
| GET | `/api/analytics` | Dashboard statistics |

### Projects
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |

### Settings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | Get current settings |
| PUT | `/api/settings` | Update settings |

## WebSocket Progress Format

Connect to `ws://localhost:8000/api/ws/progress/{video_id}`

Messages are JSON:
```json
{
  "video_id": 1,
  "status": "processing",
  "progress": 45,
  "step": "Analyzing audio..."
}
```

## Error Responses

```json
{
  "detail": "Error description"
}
```

HTTP status codes: 400 (bad request), 404 (not found), 409 (conflict), 500 (server error)
