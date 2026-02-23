# Atlas - Multimodal Video Understanding

[![PyPI version](https://img.shields.io/pypi/v/atlas-video.svg)](https://pypi.org/project/atlas-video/)
[![Python Versions](https://img.shields.io/pypi/pyversions/atlas-video.svg)](https://pypi.org/project/atlas-video/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Atlas** is an open-source multimodal insights engine for video understanding. Extract rich semantic insights from videos using AI, index them in a local vector store, and chat with your video content — all from the terminal.

## Features

- 🎬 **Multimodal Analysis**: Extract visual cues, interactions, contextual information, audio analysis, and transcripts from videos
- ⚡ **Real-time Streaming**: `extract` and `transcribe` stream results to the terminal as each segment completes — no waiting for the full video
- 🔍 **Semantic Search**: Index videos and search through content semantically using a local vector store (powered by [zvec](https://github.com/alibaba/zvec))
- 💬 **Video Chat**: Ask questions about indexed videos; context is drawn from the vector store and prior conversation history
- 🤖 **Powered by Gemini**: Uses Google's Gemini models for multimodal analysis and embeddings
- 🎙️ **Groq Whisper Transcription**: High-quality full-video transcription via the `transcribe` command
- 💻 **CLI First**: Clean, ergonomic command-line interface
- 🔒 **Local by default**: Vector index stored on disk (`~/.atlas/index`); your videos never leave your machine

## Installation

### Requirements

- Python 3.12
- ffmpeg (for video processing)

### Install from PyPI

```bash
pip install atlas-video
```

### Install from Source

```bash
git clone https://github.com/nwaughachukwuma/atlas.git
cd atlas
pip install -e ".[dev]"
```

## Quick Start

### 1. Set up API Keys

```bash
export GEMINI_API_KEY=your-gemini-api-key   # required for extract, index, search, chat
export GROQ_API_KEY=your-groq-api-key       # required only for `atlas transcribe`
export ENABLE_LOGGING=true
```

- Get a Gemini API key: [Google AI Studio](https://aistudio.google.com/app/apikey)
- Get a Groq API key: [Groq Console](https://console.groq.com/keys)

### 2. Extract Multimodal Insights (streams in real-time)

```bash
atlas extract video.mp4
atlas extract video.mp4 --chunk-duration=15s --overlap=1s --format=json
```

### 3. Index a Video

```bash
atlas index video.mp4
# Prints a video_id on completion — save it for search and chat
```

### 4. Search Indexed Videos

```bash
# Search all indexed content
atlas search "people discussing machine learning"

# Restrict to a specific video (video_id as first positional arg)
atlas search abc123def456 "demo of the new feature"
```

### 5. Chat with a Video

```bash
atlas chat abc123def456 "What tools are demonstrated in this video?"
```

### 6. Get All Indexed Data for a Video

```bash
atlas get-video abc123def456
atlas get-video abc123def456 --output data.json
```

### 7. Transcribe a Video (streams in real-time)

```bash
atlas transcribe video.mp4
atlas transcribe video.mp4 --format=srt --output=transcript.srt
```

---

## CLI Commands

### `atlas extract`

Extract multimodal insights from a video without indexing. Tasks are **queued by default**; use `--no-queue` to run directly and stream results to the terminal in real time.

```
atlas extract VIDEO_PATH [OPTIONS]

Options:
  -c, --chunk-duration DUR     Duration of each chunk (e.g. 15s, 1m) [default: 15s]
  -l, --overlap DUR            Overlap between chunks [default: 1s]
  -a, --attrs ATTR             Attribute to extract; repeat for multiple
  -o, --output FILE            Save full output to this JSON file
  -f, --format FMT             Output format: json or text [default: text]
      --include-summary BOOL   Generate a per-segment summary: true or false (default: true)
      --benchmark              Print a timing breakdown after completion
```

**Available attributes** (`--attrs`):

| Attribute                | Description                                        |
| ------------------------ | -------------------------------------------------- |
| `visual_cues`            | Visual elements, entities, and their attributes    |
| `interactions`           | Movements, gestures, dynamics between entities     |
| `contextual_information` | Production elements, setting, atmosphere           |
| `audio_analysis`         | Speech, music, sound effects, ambience             |
| `transcript`             | Verbatim spoken content (via Gemini within chunks) |

> **Note on `transcript` in `extract`**: Within the chunked extract flow, all five attributes — including `transcript` — are handled concurrently by Gemini for maximum throughput. For a high-quality, full-video verbatim transcript use `atlas transcribe` (Groq Whisper).

**Examples:**

```bash
# Stream text to terminal, default attrs
atlas extract video.mp4

# JSON output saved to file, custom chunks
atlas extract video.mp4 --chunk-duration=10s --overlap=1s --format=json --output=insights.json

# Only extract visual and audio
atlas extract video.mp4 --attrs visual_cues --attrs audio_analysis

# Disable summary, print benchmark timing
atlas extract video.mp4 --include-summary false --benchmark
```

---

### `atlas index`

Index a video for semantic search. Prints a **video_id** on completion — use it to filter searches, start chats, or retrieve data with `get-video`. Tasks are **queued by default**; use `--no-queue` to run directly.

```
atlas index VIDEO_PATH [OPTIONS]

Options:
  -c, --chunk-duration DUR     Duration of each chunk [default: 15s]
  -o, --overlap DUR            Overlap between chunks [default: 0s]
  -e, --embedding-dim N        Embedding dimension: 768 or 3072 [default: 768]
  -a, --attrs ATTR             Attribute to extract; repeat for multiple
      --include-summary BOOL  Generate a per-segment summary: true or false (default: true)
      --benchmark              Print a timing breakdown after completion
```

**Examples:**

```bash
atlas index video.mp4
atlas index video.mp4 --chunk-duration=10s --embedding-dim=3072
```

---

### `atlas search`

Search all indexed videos semantically. Pass a video ID as the first argument to scope the search to a single video.

```
atlas search [VIDEO_ID] QUERY [OPTIONS]

Arguments:
  VIDEO_ID   (optional) Video ID to restrict search to — returned by 'atlas index'
  QUERY      Natural-language search query

Options:
  -k, --top-k N   Number of results to return [default: 10]
```

**Examples:**

```bash
# Search across all indexed videos
atlas search "machine learning demonstration"

# Search within a specific video
atlas search abc123def456 "the login screen"
```

---

### `atlas transcribe`

Extract a transcript from a video or audio file using Groq Whisper. **Output streams to the terminal in real-time.**

```
atlas transcribe VIDEO_PATH [OPTIONS]

Options:
  -f, --format FMT   Output format: text, vtt, or srt [default: text]
  -o, --output FILE  Output file path
```

**Examples:**

```bash
atlas transcribe video.mp4
atlas transcribe video.mp4 --format=srt --output=transcript.srt
atlas transcribe audio.mp3 --format=vtt
```

---

### `atlas chat`

Ask a question about a previously indexed video. Context is assembled from:

1. **Top-k semantic hits** from the video index (multimodal insights)
2. **Recent chat history** from the chat vector store (last 20 messages)
3. **Top-k semantic hits** from prior chat turns (deduped against history)

```
atlas chat VIDEO_ID QUERY

Arguments:
  VIDEO_ID   Video ID returned by 'atlas index'
  QUERY      Your question about the video
```

**Examples:**

```bash
atlas chat abc123def456 "What is the main topic of this video?"
atlas chat abc123def456 "Who are the people speaking?"
```

---

### `atlas get-video`

Retrieve all indexed data for a video, returned in the same shape as the `extract` command. Useful for inspecting exactly what was stored during indexing.

```
atlas get-video VIDEO_ID [OPTIONS]

Arguments:
  VIDEO_ID   Video ID returned by 'atlas index'

Options:
  -o, --output FILE  Save JSON output to this file (default: print to stdout)
```

**Examples:**

```bash
atlas get-video abc123def456
atlas get-video abc123def456 --output data.json
```

---

### `atlas list-videos`

List all videos that have been indexed in the local vector store.

```
atlas list-videos
```

---

### `atlas list-chat`

Show the chat history for a given video.

```
atlas list-chat VIDEO_ID [OPTIONS]

Arguments:
  VIDEO_ID   Video ID to retrieve chat history for

Options:
  -n, --last-n N   Maximum number of messages to show [default: 20]
```

---

### `atlas stats`

Show statistics about the local vector store (collection paths, document counts).

```
atlas stats
```

---

### `atlas queue`

Manage the background task queue. Long-running commands (`index`, `extract`) are queued by default; use `--no-queue` on any command to run immediately.

```
atlas queue list                         # list all tasks
atlas queue status --task-id TASK_ID     # check status of a specific task
```

Use `--no-queue` on any command to bypass the queue and run synchronously:

```bash
atlas index video.mp4 --no-queue
```

---

## API Keys Reference

| Command       | `GEMINI_API_KEY` | `GROQ_API_KEY` |
| ------------- | ---------------- | -------------- |
| `extract`     | ✅ Required      | ❌ Not needed  |
| `index`       | ✅ Required      | ❌ Not needed  |
| `search`      | ✅ Required      | ❌ Not needed  |
| `transcribe`  | ❌ Not needed    | ✅ Required    |
| `chat`        | ✅ Required      | ❌ Not needed  |
| `get-video`   | ❌ Not needed    | ❌ Not needed  |
| `list-videos` | ❌ Not needed    | ❌ Not needed  |
| `list-chat`   | ❌ Not needed    | ❌ Not needed  |
| `stats`       | ❌ Not needed    | ❌ Not needed  |
| `queue`       | ❌ Not needed    | ❌ Not needed  |

---

## Python API

```python
import asyncio
from atlas import VideoProcessor, VideoProcessorConfig

async def main():
    # Extract insights
    config = VideoProcessorConfig(
        video_path="video.mp4",
        chunk_duration=15,
        overlap=1,
        description_attrs=["visual_cues", "contextual_information", "audio_analysis", "transcript"],
        include_summary=True,
    )
    async with VideoProcessor(config) as processor:
        result = await processor.process()

    print(f"Processed {len(result.video_descriptions)} segments")

    # Index for search — returns (video_id, indexed_count, result)
    from atlas.vector_store import index_video
    video_id, indexed_count, _ = await index_video("video.mp4")
    print(f"video_id: {video_id}  docs: {indexed_count}")

    # Search all videos
    from atlas.vector_store import search_video
    results = await search_video("people discussing AI", top_k=5)
    for r in results:
        print(f"{r.score:.3f}  [{r.video_id}]  {r.content[:80]}")

    # Search within a specific video
    results = await search_video("login screen", top_k=5, video_id=video_id)

    # Chat
    from atlas.vector_store import chat_with_video
    answer = await chat_with_video(video_id, "What tools are shown?")
    print(answer)

asyncio.run(main())
```

### Real-time Extract

Pass `on_segment` to receive results as each segment is processed:

```python
from atlas import VideoProcessor, VideoProcessorConfig

async def realtime_example():
    config = VideoProcessorConfig(video_path="video.mp4", chunk_duration=15)
    async with VideoProcessor(config) as processor:
        result = await processor.process(
            on_segment=lambda desc: print(f"{desc.start:.1f}s–{desc.end:.1f}s ready")
        )
```

### Transcription

```python
from atlas.video_processor import extract_transcript
import asyncio

# One-shot
transcript = asyncio.run(extract_transcript("video.mp4", format="srt"))

# Real-time callback
async def stream():
    await extract_transcript(
        "video.mp4",
        format="text",
        on_chunk=lambda chunk: print(chunk, end="", flush=True),
    )

asyncio.run(stream())
```

---

## Vector Store Layout

```
~/.atlas/index/
├── video_index/   # zvec collection — multimodal insights per segment
└── video_chat/    # zvec collection — chat history per video
```

All data (indexed segments, chat history, video metadata) is stored directly in the zvec collections — no sidecar files or external registries.

---

## Performance

| Function                   | Avg / call   | Notes                                     |
| -------------------------- | ------------ | ----------------------------------------- |
| Gemini multimodal analysis | ~21s         | 4–5 attrs gathered concurrently per chunk |
| Groq Whisper (transcribe)  | ~30s / video | Full video, one shot                      |
| ffmpeg clip                | ~0.3s        | Per chunk                                 |
| zvec query                 | sub-ms       | Local HNSW, ~8× faster than Pinecone      |

For a ~5 min video with 15s chunks (~24 chunks), wall time is typically **2–3 min** with default concurrency, as chunks are processed in parallel.

---

## Requirements

- **ffmpeg**: Required for video clipping.
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: `winget install ffmpeg`

---

## License

Apache License 2.0

## Contributing

Contributions welcome — please open a PR.

## Credits

Atlas was originally developed at [VeedoAI](https://veedo.ai) and is now open-sourced for the community.
