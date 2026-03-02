# Atlas-Video — HTTP API

Start the server with `atlas serve` (see `rules/cli-commands.md`), then interact with these REST endpoints.

```bash
# Default: all interfaces, port 8000
atlas serve

# Load credentials from a file
atlas serve --env-file .env -H 0.0.0.0 -p 8000
```

---

## Endpoints

| Method | Path                      | Description                                |
| ------ | ------------------------- | ------------------------------------------ |
| `GET`  | `/health`                 | Health check                               |
| `POST` | `/extract`                | Extract multimodal insights                |
| `POST` | `/index`                  | Index a video for semantic search          |
| `POST` | `/transcribe`             | Transcribe a video                         |
| `POST` | `/search`                 | Semantic search across indexed videos      |
| `POST` | `/chat`                   | Chat with a video (SSE streaming)          |
| `GET`  | `/list-videos`            | List all indexed videos                    |
| `GET`  | `/list-chat/{video_id}`   | Chat history for a video                   |
| `GET`  | `/stats`                  | Vector store statistics                    |
| `GET`  | `/get-video/{video_id}`   | All indexed data for a video               |
| `GET`  | `/queue/list`             | List queued tasks (filter with `?status=`) |
| `GET`  | `/queue/status/{task_id}` | Status and result of a task                |

---

## Health check

```bash
curl http://localhost:8000/health
```

---

## `POST /extract`

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/data/video.mp4",
    "chunk_duration": 15,
    "overlap": 1,
    "attrs": ["visual_cues", "audio_analysis"],
    "include_summary": true,
    "format": "json"
  }'
```

---

## `POST /index`

```bash
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/data/video.mp4",
    "chunk_duration": 15,
    "overlap": 1
  }'
# Returns: { "video_id": "abc123def456", "indexed_count": 20 }
```

---

## `POST /transcribe`

```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/data/video.mp4",
    "format": "srt"
  }'
```

---

## `POST /search`

```bash
# Search across all videos
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning demo", "top_k": 5}'

# Search within one video
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "login screen", "top_k": 5, "video_id": "abc123def456"}'
```

Response:

```json
[
  {
    "score": 0.92,
    "video_id": "abc123def456",
    "content": "...",
    "start": 30.0,
    "end": 45.0
  }
]
```

---

## `POST /chat` — Server-Sent Events (SSE streaming)

`/chat` returns a `StreamingResponse` — tokens arrive as SSE events while Gemini generates.

```bash
# -sN: silent + no buffering
curl -sN -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"video_id": "abc123def456", "query": "What is this video about?"}'
```

**JavaScript (EventSource-compatible):**

```typescript
const response = await fetch("http://localhost:8000/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    video_id: "abc123def456",
    query: "Summarise the key points",
  }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  process.stdout.write(decoder.decode(value));
}
```

---

## `GET /list-videos`

```bash
curl http://localhost:8000/list-videos
# Returns: [{ "video_id": "abc123...", "title": "video.mp4", ... }, ...]
```

---

## `GET /get-video/{video_id}`

```bash
curl http://localhost:8000/get-video/abc123def456
# Returns: same shape as `atlas extract` output — all segments with their attributes
```

---

## `GET /list-chat/{video_id}`

```bash
curl "http://localhost:8000/list-chat/abc123def456?last_n=20"
```

---

## `GET /stats`

```bash
curl http://localhost:8000/stats
```

---

## `GET /queue/list`

```bash
curl "http://localhost:8000/queue/list"
curl "http://localhost:8000/queue/list?status=pending"
```

---

## `GET /queue/status/{task_id}`

```bash
curl http://localhost:8000/queue/status/TASK_ID
```
