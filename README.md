# Atlas - Multimodal Video Understanding Engine

[![PyPI version](https://img.shields.io/pypi/v/atlas-video.svg)](https://pypi.org/project/atlas-video/)
[![Python Versions](https://img.shields.io/pypi/pyversions/atlas-video.svg)](https://pypi.org/project/atlas-video/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Atlas** is an open-source multimodal insights engine for video understanding. Extract rich semantic insights from videos using AI, and search through them with a fast local vector store.

## Features

- 🎬 **Multimodal Analysis**: Extract visual cues, interactions, contextual information, audio analysis, and transcripts from videos
- 🔍 **Semantic Search**: Index videos and search through content semantically using local vector storage (powered by zvec)
- ⚡ **Fast Transcription**: High-quality transcription using Groq Whisper
- 🤖 **Powered by Gemini**: Uses Google's Gemini models for multimodal understanding
- 💻 **CLI First**: Easy-to-use command line interface
- 🔒 **Privacy Focused**: All processing happens locally, your videos never leave your machine

## Installation

### Requirements

- Python 3.10 - 3.12
- ffmpeg (for video processing)

### Install from PyPI

```bash
pip install atlas-video
```

### Install from Source

```bash
git clone https://github.com/veedoai/atlas.git
cd atlas
pip install -e .
```

## Quick Start

### 1. Set up API Keys

Atlas requires API keys from Google Gemini (for video analysis) and Groq (for transcription):

```bash
export GEMINI_API_KEY=your-gemini-api-key
export GROQ_API_KEY=your-groq-api-key
```

- Get a Gemini API key: [Google AI Studio](https://aistudio.google.com/app/apikey)
- Get a Groq API key: [Groq Console](https://console.groq.com/keys)

### 2. Extract Multimodal Insights

Extract rich multimodal descriptions from a video:

```bash
atlas extract video.mp4 --chunk-duration=15s --overlap=1s
```

Output to JSON file:

```bash
atlas extract video.mp4 --output=insights.json --format=json
```

### 3. Index Videos for Search

Index a video for fast semantic search:

```bash
atlas index video.mp4 --chunk-duration=15s --overlap=1s
```

### 4. Search Indexed Videos

Search through your indexed video content:

```bash
atlas search "people discussing artificial intelligence"
```

Filter by specific video:

```bash
atlas search "meeting notes" --video=path/to/video.mp4
```

### 5. Extract Transcripts

Get transcripts in various formats:

```bash
# Plain text
atlas transcribe video.mp4

# SRT format
atlas transcribe video.mp4 --format=srt --output=transcript.srt

# VTT format
atlas transcribe video.mp4 --format=vtt --output=transcript.vtt
```

## CLI Commands

### `atlas extract`

Extract multimodal insights from a video.

```bash
atlas extract VIDEO_PATH [OPTIONS]

Options:
  -c, --chunk-duration TEXT  Duration of each chunk (e.g., 15s, 1m) [default: 10s]
  -o, --overlap TEXT         Overlap between chunks (e.g., 1s, 5s) [default: 0s]
  -a, --attrs TEXT           Attributes to extract (can be used multiple times)
  --output TEXT              Output file path (JSON format)
  --format [json|text]       Output format [default: text]
```

Available attributes:

- `visual_cues`: Visual elements, entities, and their attributes
- `interactions`: Movements, gestures, dynamics between entities
- `contextual_information`: Production elements, setting, atmosphere
- `audio_analysis`: Speech, music, sound effects, ambience
- `transcript`: Verbatim spoken content

### `atlas index`

Index a video for semantic search.

```bash
atlas index VIDEO_PATH [OPTIONS]

Options:
  -c, --chunk-duration TEXT  Duration of each chunk [default: 10s]
  -o, --overlap TEXT         Overlap between chunks [default: 0s]
  -s, --store-path TEXT      Path to store the vector index
  -e, --embedding-dim INT    Embedding dimension (768 or 3072) [default: 768]
```

### `atlas search`

Search indexed videos semantically.

```bash
atlas search QUERY [OPTIONS]

Options:
  -k, --top-k INTEGER    Number of results to return [default: 10]
  -v, --video TEXT       Filter by video path
  -s, --store-path TEXT  Path to the vector index
```

### `atlas transcribe`

Extract transcript from a video or audio file.

```bash
atlas transcribe VIDEO_PATH [OPTIONS]

Options:
  -f, --format [text|vtt|srt]  Output format [default: text]
  -o, --output TEXT            Output file path
```

### `atlas stats`

Show statistics about the local vector store.

```bash
atlas stats
```

## Python API

You can also use Atlas programmatically:

```python
import asyncio
from atlas import VideoProcessor, VideoProcessorConfig, VectorStore

async def main():
    # Extract insights
    config = VideoProcessorConfig(
        video_path="video.mp4",
        chunk_duration=15,
        overlap=1,
    )

    async with VideoProcessor(config) as processor:
        result = await processor.process()

    print(f"Processed {len(result.video_descriptions)} segments")

    # Index for search
    store = VectorStore()
    indexed = await store.index_video_result(result)
    print(f"Indexed {indexed} documents")

    # Search
    results = await store.search("people discussing AI", top_k=5)
    for r in results:
        print(f"{r.score:.3f}: {r.content[:100]}")

asyncio.run(main())
```

### Transcription Only

```python
from .video_processor import extract_transcript
import asyncio

async def get_transcript():
    transcript = await extract_transcript("video.mp4", format="srt")
    print(transcript)

asyncio.run(get_transcript())
```

### Text Embeddings

```python
from .text_embedding import TextEmbedding, embed_text

# Get embedding for text
embedding = embed_text("Hello, world!")
print(f"Embedding dimension: {len(embedding)}")

# Or use the class
embedder = TextEmbedding("Hello, world!")
embedding = embedder.get_embedding(dimensionality=768)
```

## Configuration

### Environment Variables

| Variable         | Required          | Description                                             |
| ---------------- | ----------------- | ------------------------------------------------------- |
| `GEMINI_API_KEY` | Yes               | Google Gemini API key for video analysis and embeddings |
| `GROQ_API_KEY`   | For transcription | Groq API key for Whisper transcription                  |

### Vector Store Location

By default, Atlas stores the vector index at `~/.atlas/index`. You can customize this with the `--store-path` option or when creating a `VectorStore` instance.

## How It Works

1. **Chunking**: Videos are split into configurable duration chunks (default: 10 seconds) with optional overlap
2. **Multimodal Analysis**: Each chunk is analyzed using Gemini models for:
   - Visual content and entities
   - Interactions and dynamics
   - Production context and atmosphere
   - Audio characteristics
   - Transcription
3. **Embedding**: Content is embedded using Gemini's embedding model
4. **Indexing**: Embeddings are stored in a local zvec vector database
5. **Search**: Queries are embedded and matched against the indexed content

## Requirements

- **ffmpeg**: Required for video processing. Install with:
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: `winget install ffmpeg`

## License

Apache License 2.0

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

Atlas was originally developed at [VeedoAI](https://veedoai.com) and is now open-sourced for the community.
