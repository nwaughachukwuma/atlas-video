# Atlas-Video — Python API

Atlas exposes a fully async Python API for programmatic control over all features.

## Installation

```bash
pip install atlas-video
```

Set API keys before use:

```bash
export GEMINI_API_KEY=your-gemini-key
export GROQ_API_KEY=your-groq-key
```

---

## Extract multimodal insights — `VideoProcessor`

```python
import asyncio
from atlas import VideoProcessor, VideoProcessorConfig

async def main():
    config = VideoProcessorConfig(
        video_path="video.mp4",
        chunk_duration=15,       # seconds per chunk
        overlap=1,               # seconds of overlap
        description_attrs=[      # which attributes to extract
            "visual_cues",
            "contextual_information",
            "audio_analysis",
            "transcript",
            "interactions",
        ],
        include_summary=True,
    )
    async with VideoProcessor(config) as processor:
        result = await processor.process()

    print(f"Segments: {len(result.video_descriptions)}")
    for seg in result.video_descriptions:
        print(f"{seg.start:.1f}s–{seg.end:.1f}s  {seg.summary}")

asyncio.run(main())
```

### Real-time streaming with `on_segment`

```python
from atlas import VideoProcessor, VideoProcessorConfig

async def realtime():
    config = VideoProcessorConfig(video_path="video.mp4", chunk_duration=15)
    async with VideoProcessor(config) as processor:
        result = await processor.process(
            on_segment=lambda desc: print(
                f"{desc.start:.1f}s–{desc.end:.1f}s  ready ✓"
            )
        )

import asyncio
asyncio.run(realtime())
```

---

## Index a video — `index_video`

```python
from atlas.vector_store import index_video
import asyncio

async def main():
    video_id, indexed_count, result = await index_video(
        "video.mp4",
        chunk_duration=15,
        overlap=1,
    )
    print(f"video_id : {video_id}")
    print(f"segments : {indexed_count}")

asyncio.run(main())
```

`video_id` is a randomly generated identifier. Store it for later `search` and `chat` calls.

The `on_segment` callback can be passed to receive each `VideoDescription` as it completes:

```python
video_id, count, result = await index_video(
    "video.mp4",
    on_segment=lambda desc: print(f"{desc.start:.0f}s–{desc.end:.0f}s indexed"),
)
```

---

## Search indexed videos — `search_video`

```python
from atlas.vector_store import search_video
import asyncio

async def main():
    # Search across ALL indexed videos
    results = await search_video("machine learning demo", top_k=5)

    # Search within ONE video
    results = await search_video(
        "the login screen",
        top_k=5,
        video_id="abc123def456",
    )

    for r in results:
        print(f"{r.score:.3f}  [{r.video_id}]  {r.content[:120]}")

asyncio.run(main())
```

---

## Chat with a video — `chat_with_video`

`chat_with_video` is an **async generator** — it yields text chunks as they stream from Gemini.

```python
from atlas.chat_handler import chat_with_video
import asyncio

async def main():
    video_id = "abc123def456"
    answer = ""
    async for chunk in chat_with_video(video_id, "What tools are shown in this video?"):
        print(chunk, end="", flush=True)
        answer += chunk
    # use answer e.g., ingest to your DB, observability or validation pipeline
    print()  # final newline

asyncio.run(main())
```

Context is assembled from:

1. Top-k semantic hits from `video_index` (`top_k_context`, default 10)
2. Last 20 messages from chat history
3. Top-k semantic hits from prior chat turns, deduped (`top_k_chat`, default 10)

---

## Transcription — `get_video_transcript`

```python
from atlas.transcript import get_video_transcript
import asyncio

# One-shot — returns the full transcript string
async def one_shot():
    transcript = await get_video_transcript("video.mp4", format="srt")
    print(transcript)

# Streaming — callback called as each Groq chunk arrives
async def streaming():
    await get_video_transcript(
        "video.mp4",
        format="text",
        on_chunk=lambda chunk: print(chunk, end="", flush=True),
    )

asyncio.run(one_shot())
asyncio.run(streaming())
```

Supported formats: `"text"`, `"vtt"`, `"srt"`.

---

## `VideoProcessorConfig` reference

| Field               | Type        | Default | Description                       |
| ------------------- | ----------- | ------- | --------------------------------- |
| `video_path`        | `str`       | —       | Path to the video file (required) |
| `chunk_duration`    | `int`       | `15`    | Seconds per chunk                 |
| `overlap`           | `int`       | `1`     | Seconds of overlap between chunks |
| `description_attrs` | `list[str]` | all 5   | Attributes to extract             |
| `include_summary`   | `bool`      | `True`  | Generate per-segment summary      |

## Full example — extract then index then chat

```python
import asyncio
from atlas import VideoProcessor, VideoProcessorConfig
from atlas.vector_store import index_video, search_video
from atlas.chat_handler import chat_with_video

VIDEO = "video.mp4"

async def main():
    # 1. Extract insights (streaming)
    config = VideoProcessorConfig(video_path=VIDEO, chunk_duration=15)
    async with VideoProcessor(config) as processor:
        result = await processor.process(
            on_segment=lambda d: print(f"{d.start:.0f}s–{d.end:.0f}s done")
        )

    # 2. Index for search
    video_id, count, _ = await index_video(VIDEO)
    print(f"Indexed {count} segments → video_id={video_id}")

    # 3. Search
    hits = await search_video("main demo workflow", top_k=3, video_id=video_id)
    for h in hits:
        print(f"  [{h.score:.3f}] {h.content[:80]}")

    # 4. Chat (streaming)
    print("\nAnswer: ", end="")
    async for chunk in chat_with_video(video_id, "What is the video about?"):
        print(chunk, end="", flush=True)
    print()

asyncio.run(main())
```
