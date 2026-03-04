# Atlas-Video — HTTP API

Start the server with `atlas serve` (see `rules/cli-commands.md`), then interact with these REST endpoints.

> **Note:** The server defaults to running commands directly (`no_queue=true`), unlike the CLI which queues by default. The server also disables streaming by default (`no_streaming=true`).

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

Uses **multipart/form-data** file upload. The video is uploaded directly.

```bash
curl -X POST http://localhost:8000/extract \
  -F "video=@video.mp4" \
  -F "chunk_duration=15s" \
  -F "overlap=1s" \
  -F "attrs=visual_cues,audio_analysis" \
  -F "include_summary=true" \
  -F "format=json"
```

| Field             | Type    | Default | Description                         |
| ----------------- | ------- | ------- | ----------------------------------- |
| `video`           | file    | —       | Video file to upload (required)     |
| `chunk_duration`  | string  | `15s`   | Duration per chunk                  |
| `overlap`         | string  | `1s`    | Overlap between chunks              |
| `attrs`           | string  | all     | Comma-separated attributes          |
| `format`          | string  | `text`  | `json` or `text`                    |
| `include_summary` | boolean | `true`  | Include per-segment summary         |
| `benchmark`       | boolean | `false` | Print timing breakdown              |
| `no_queue`        | boolean | `true`  | Run directly (server default: true) |
| `no_streaming`    | boolean | `true`  | Disable streaming output            |

---

## `POST /index`

Uses **multipart/form-data** file upload.

```bash
curl -X POST http://localhost:8000/index \
  -F "video=@video.mp4" \
  -F "chunk_duration=15s" \
  -F "overlap=1s"
# Returns: { "ok": true, "output": "...", "error": "" }
```

| Field             | Type    | Default | Description                         |
| ----------------- | ------- | ------- | ----------------------------------- |
| `video`           | file    | —       | Video file to upload (required)     |
| `chunk_duration`  | string  | `15s`   | Duration per chunk                  |
| `overlap`         | string  | `1s`    | Overlap between chunks              |
| `attrs`           | string  | none    | Comma-separated attributes          |
| `include_summary` | boolean | `true`  | Include per-segment summary         |
| `benchmark`       | boolean | `false` | Print timing breakdown              |
| `no_queue`        | boolean | `true`  | Run directly (server default: true) |
| `no_streaming`    | boolean | `true`  | Disable streaming output            |

---

## `POST /transcribe`

Uses **multipart/form-data** file upload.

```bash
curl -X POST http://localhost:8000/transcribe \
  -F "video=@video.mp4" \
  -F "format=srt"
```

| Field          | Type    | Default | Description                           |
| -------------- | ------- | ------- | ------------------------------------- |
| `video`        | file    | —       | Video/audio file to upload (required) |
| `format`       | string  | `text`  | `text`, `vtt`, or `srt`               |
| `output`       | string  | none    | Output file path on server            |
| `benchmark`    | boolean | `false` | Print timing breakdown                |
| `no_queue`     | boolean | `true`  | Run directly (server default: true)   |
| `no_streaming` | boolean | `true`  | Disable streaming output              |

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
{
  "count": 3,
  "results": [
    {
      "score": 0.92,
      "video_id": "abc123def456",
      "content": "...",
      "start": 30.0,
      "end": 45.0
    }
  ]
}
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
