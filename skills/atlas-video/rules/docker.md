# Atlas-Video — Docker Usage

Docker is the zero-setup option. No Python, no ffmpeg, no local dependencies needed.

```
Image: nwaughachukwuma/atlas-video
Tags:  latest, 0.1.0, ...
Platforms: linux/amd64, linux/arm64
```

---

## Pull the image

```bash
docker pull nwaughachukwuma/atlas-video

# Pin to a specific version
docker pull nwaughachukwuma/atlas-video:0.1.0
```

---

## General pattern

```bash
docker run --rm -it \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e GROQ_API_KEY="$GROQ_API_KEY" \
  -v "$(pwd)/videos:/data" \
  nwaughachukwuma/atlas-video <command> [args]
```

Mount local video directories with `-v "$(pwd)/videos:/data"` and reference them as `/data/video.mp4` inside the container.

---

## Environment variables

| Variable         | Required for                 | Notes                                               |
| ---------------- | ---------------------------- | --------------------------------------------------- |
| `GEMINI_API_KEY` | extract, index, search, chat | [AI Studio](https://aistudio.google.com/app/apikey) |
| `GROQ_API_KEY`   | transcribe, extract, index   | [Groq Console](https://console.groq.com/keys)       |
| `ENABLE_LOGGING` | optional                     | set `true` for verbose logs                         |

---

## Quick one-liner examples

```bash
# Transcribe (queued by default)
docker run --rm -it \
  -e GROQ_API_KEY="$GROQ_API_KEY" \
  -v "$(pwd)/videos:/data" \
  nwaughachukwuma/atlas-video transcribe /data/video.mp4

# Transcribe — stream directly to terminal
docker run --rm -it \
  -e GROQ_API_KEY="$GROQ_API_KEY" \
  -v "$(pwd)/videos:/data" \
  nwaughachukwuma/atlas-video transcribe /data/video.mp4 --no-queue

# Extract multimodal insights (stream)
docker run --rm -it \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e GROQ_API_KEY="$GROQ_API_KEY" \
  -v "$(pwd)/videos:/data" \
  nwaughachukwuma/atlas-video extract /data/video.mp4 --no-queue

# Index a video (persist with a named volume)
docker run --rm -it \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e GROQ_API_KEY="$GROQ_API_KEY" \
  -v atlas-data:/home/atlas/.atlas \
  -v "$(pwd)/videos:/data" \
  nwaughachukwuma/atlas-video index /data/video.mp4

# Semantic search
docker run --rm -it \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -v atlas-data:/home/atlas/.atlas \
  nwaughachukwuma/atlas-video search "machine learning demo"

# Chat with an indexed video
docker run --rm -it \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -v atlas-data:/home/atlas/.atlas \
  nwaughachukwuma/atlas-video chat <video_id> "What topics are covered?"

# List all indexed videos
docker run --rm -it \
  -v atlas-data:/home/atlas/.atlas \
  nwaughachukwuma/atlas-video list-videos

# List queued tasks
docker run --rm \
  nwaughachukwuma/atlas-video queue list

# Show help / version
docker run --rm nwaughachukwuma/atlas-video --help
docker run --rm nwaughachukwuma/atlas-video --version
```

---

## Persistent vector store

The container stores its index at `/home/atlas/.atlas`. Use a **named volume** to persist across runs:

```bash
# Create the volume once
docker volume create atlas-data

# Index a video (shares the same atlas-data volume)
docker run --rm -it \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e GROQ_API_KEY="$GROQ_API_KEY" \
  -v atlas-data:/home/atlas/.atlas \
  -v "$(pwd)/videos:/data" \
  nwaughachukwuma/atlas-video index /data/video.mp4

# Search uses the same volume — no extra flags needed for videos
docker run --rm -it \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -v atlas-data:/home/atlas/.atlas \
  nwaughachukwuma/atlas-video search "product demo"
```

---

## Using a `.env` file

```bash
# .env
GEMINI_API_KEY=your-key-here
GROQ_API_KEY=your-key-here
ENABLE_LOGGING=false
```

```bash
docker run --rm -it \
  --env-file .env \
  -v atlas-data:/home/atlas/.atlas \
  -v "$(pwd)/videos:/data" \
  nwaughachukwuma/atlas-video extract /data/video.mp4
```

---

## Run as HTTP server

```bash
# Start Atlas HTTP API — detached, port 8000
docker run --rm -d \
  --name atlas-server \
  -p 8000:8000 \
  --env-file .env \
  -v atlas-data:/home/atlas/.atlas \
  nwaughachukwuma/atlas-video serve -H 0.0.0.0 -p 8000

# Health check
curl http://localhost:8000/health

# Stop
docker stop atlas-server
```

Or pass keys inline:

```bash
docker run --rm -d \
  --name atlas-server \
  -p 8000:8000 \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e GROQ_API_KEY="$GROQ_API_KEY" \
  -v atlas-data:/home/atlas/.atlas \
  nwaughachukwuma/atlas-video serve -H 0.0.0.0 -p 8000
```

See `rules/http-api.md` for all available REST endpoints.
