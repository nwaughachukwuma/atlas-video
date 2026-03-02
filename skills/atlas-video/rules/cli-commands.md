# Atlas-Video — CLI Commands Reference

All commands are invoked as `atlas <command> [args] [options]`.  
Long-running commands (`extract`, `index`) are **queued by default**. Add `--no-queue` to any command to run it synchronously and stream output to the terminal.

---

## `atlas extract`

Extract multimodal insights from a video without indexing it. Results stream in real time when run with `--no-queue`.

```
atlas extract VIDEO_PATH [OPTIONS]

Options:
  -c, --chunk-duration DUR     Chunk size (e.g. 15s, 1m)   [default: 15s]
  -l, --overlap DUR            Overlap between chunks       [default: 1s]
  -a, --attrs ATTR             Attribute to extract; repeat for multiple
  -o, --output FILE            Save full output to a JSON file
  -f, --format FMT             json | text                  [default: text]
      --include-summary BOOL   Per-segment summary          [default: true]
      --benchmark              Print timing breakdown at end
      --no-queue               Run directly, stream to terminal
```

**Available `--attrs` values:**

| Attribute                | What it captures                               |
| ------------------------ | ---------------------------------------------- |
| `visual_cues`            | Visual elements, entities, their attributes    |
| `interactions`           | Movements, gestures, dynamics between entities |
| `contextual_information` | Production setting, atmosphere                 |
| `audio_analysis`         | Speech, music, sound effects, ambience         |
| `transcript`             | Verbatim spoken content (via Gemini per chunk) |

> For high-quality standalone transcripts, prefer `atlas transcribe` (Groq Whisper).

**Examples:**

```bash
# Stream text to terminal with all default attributes
atlas extract video.mp4 --no-queue

# JSON output saved to file with custom chunk size
atlas extract video.mp4 --chunk-duration=10s --overlap=1s --format=json --output=insights.json

# Only visual and audio attributes, skip summary, print timing
atlas extract video.mp4 --attrs visual_cues --attrs audio_analysis \
  --include-summary false --benchmark

# Queue-based (default) — returns a task ID immediately
atlas extract video.mp4
```

---

## `atlas index`

Index a video for semantic search. Prints the **video_id** on completion — save it for `search`, `chat`, and `get-video`.

```
atlas index VIDEO_PATH [OPTIONS]

Options:
  -c, --chunk-duration DUR     [default: 15s]
  -o, --overlap DUR            [default: 1s]
  -a, --attrs ATTR             Attribute to extract; repeat for multiple
      --include-summary BOOL   [default: true]
      --benchmark              Print timing breakdown
      --no-queue               Run directly
```

**Examples:**

```bash
atlas index video.mp4
atlas index video.mp4 --chunk-duration=10s --overlap=2s --benchmark
atlas index video.mp4 --no-queue   # stream progress, print video_id when done
```

> Save the printed `video_id` — it is used as the first argument to `search`, `chat`, `get-video`, `list-chat`.

---

## `atlas search`

Semantic search over all indexed videos, or scoped to a single video.

```
atlas search [VIDEO_ID] QUERY [OPTIONS]

Arguments:
  VIDEO_ID   (optional) Restrict search to this video
  QUERY      Natural-language query string

Options:
  -k, --top-k N   Number of results to return   [default: 10]
```

**Examples:**

```bash
# Global search
atlas search "people discussing machine learning"

# Scoped to one video (first positional arg is the video_id)
atlas search abc123def456 "the login screen demo" --top-k 5
```

---

## `atlas chat`

Ask a question about a previously indexed video. Grounded with:

1. Top-k semantic hits from `video_index`
2. Last 20 messages from `video_chat` history
3. Top-k semantic hits from prior chat turns (deduped)

```
atlas chat VIDEO_ID QUERY
```

**Examples:**

```bash
atlas chat abc123def456 "What is the main topic of this video?"
atlas chat abc123def456 "Who are the people speaking?"
```

---

## `atlas transcribe`

Transcribe a video or audio file using Groq Whisper. Output streams to the terminal in real time.

```
atlas transcribe VIDEO_PATH [OPTIONS]

Options:
  -f, --format FMT   text | vtt | srt   [default: text]
  -o, --output FILE  Save output to file
      --no-queue     Run directly and stream output
```

**Examples:**

```bash
atlas transcribe video.mp4
atlas transcribe video.mp4 --format=srt --output=transcript.srt
atlas transcribe audio.mp3 --format=vtt --no-queue
```

---

## `atlas get-video`

Retrieve all indexed data for a video in the same shape as `extract` output.

```
atlas get-video VIDEO_ID [OPTIONS]

Options:
  -o, --output FILE   Save JSON to file (default: stdout)
```

**Examples:**

```bash
atlas get-video abc123def456
atlas get-video abc123def456 --output data.json
```

---

## `atlas list-videos`

List all videos indexed in the local vector store.

```bash
atlas list-videos
```

---

## `atlas list-chat`

Show chat history for a given video.

```
atlas list-chat VIDEO_ID [OPTIONS]

Options:
  -n, --last-n N   Max messages to show   [default: 20]
```

```bash
atlas list-chat abc123def456
atlas list-chat abc123def456 --last-n 50
```

---

## `atlas stats`

Show vector store statistics: collection paths, document counts.

```bash
atlas stats
```

---

## `atlas queue`

Manage the background task queue.

```bash
atlas queue list                          # list all queued tasks
atlas queue list --status=pending         # filter by status
atlas queue status --task-id TASK_ID      # check a specific task
```

Bypass the queue on any command with `--no-queue`:

```bash
atlas index video.mp4 --no-queue
atlas extract video.mp4 --no-queue
```

---

## `atlas serve`

Start an HTTP API server that exposes all Atlas commands as REST endpoints.

```
atlas serve [OPTIONS]

Options:
  -H, --host HOST        Bind interface          [default: 0.0.0.0]
  -p, --port PORT        Port                    [default: 8000]
      --env-file PATH    Load env vars from file
```

**Examples:**

```bash
atlas serve                                          # all interfaces, port 8000
atlas serve -H 127.0.0.1 -p 9000                   # localhost only
atlas serve -H 0.0.0.0 -p 8000 --env-file .env     # load API keys from file
```

See `rules/http-api.md` for all REST endpoints.
