# Atlas-Video — Architecture & Overview

## What it does

Atlas is a multimodal video understanding engine. Given a video file it can:

1. **Extract** structured semantic insights from every chunk (visual cues, audio analysis, interactions, contextual information, transcript/summary)
2. **Index** those insights into a local HNSW vector store for persistent retrieval
3. **Search** across all indexed videos or within a single video using natural language
4. **Chat** with an indexed video — each answer is grounded in the top-k semantically relevant segments
5. **Transcribe** a video or audio file with Groq Whisper, streaming output in real time

## Core models

| Task                           | Model                      |
| ------------------------------ | -------------------------- |
| Multimodal analysis (extract)  | Google Gemini (multimodal) |
| Text embeddings (index/search) | Google Gemini embeddings   |
| Transcription                  | Groq Whisper               |

## Environment variables

| Variable         | Required for                         | Where to get                                               |
| ---------------- | ------------------------------------ | ---------------------------------------------------------- |
| `GEMINI_API_KEY` | `extract`, `index`, `search`, `chat` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `GROQ_API_KEY`   | `transcribe`, `extract`, `index`     | [Groq Console](https://console.groq.com/keys)              |
| `ENABLE_LOGGING` | optional — verbose logs              | set to `true`                                              |

## System requirements

- Python 3.12
- `ffmpeg` installed (for video clipping)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: `winget install ffmpeg`
- Platforms supported: Linux (x86_64, ARM64) and macOS (ARM64)

## Vector store layout

All data persists at `~/.atlas/index/` using [zvec](https://github.com/alibaba/zvec) (local HNSW):

```
~/.atlas/index/
├── video_index/   # multimodal insights per segment (all videos)
└── video_chat/    # chat history keyed by video_id
```

No external service is required — the index is fully local. Use a Docker named volume to persist across container restarts.

## Performance benchmarks

| Operation                  | Typical time | Notes                                  |
| -------------------------- | ------------ | -------------------------------------- |
| Gemini multimodal analysis | ~5s          | Per 15s chunk with multiple attributes |
| Groq Whisper transcription | ~5s          | Full video (any length)                |
| ffmpeg clip extraction     | ~0.1s        | Per chunk                              |
| zvec query                 | milliseconds | ~8× faster than Pinecone               |

For a ~5-minute video with 15s chunks (~20 chunks), wall-clock time for `atlas index` is typically **~90s** because chunks are processed concurrently.

## Processing pipeline

```
video.mp4
   └─ ffmpeg splits into overlapping chunks (CLI default: 15s, 1s overlap; Python API default: 15s, 1s overlap)
       └─ Concurrently per chunk:
           ├─ Gemini multimodal: visual_cues, audio_analysis, interactions,
           │                     contextual_information, transcript, summary
           └─ (index only) → embed text → upsert into zvec video_index
```

## Installation

```bash
# From PyPI
pip install atlas-video

# From source
git clone https://github.com/nwaughachukwuma/atlas.git
cd atlas
pip install -e ".[dev]"
```

## API keys reference (quick lookup)

| Command       | `GEMINI_API_KEY` | `GROQ_API_KEY` |
| ------------- | ---------------- | -------------- |
| `transcribe`  | ❌               | ✅             |
| `extract`     | ✅               | ✅             |
| `index`       | ✅               | ✅             |
| `search`      | ✅               | ❌             |
| `chat`        | ✅               | ❌             |
| `get-video`   | ❌               | ❌             |
| `list-videos` | ❌               | ❌             |
| `list-chat`   | ❌               | ❌             |
| `stats`       | ❌               | ❌             |
| `queue`       | ❌               | ❌             |
