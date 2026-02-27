"""
chat_handler — video chat pipeline.

This module is the single place that combines vector retrieval with Gemini
inference.

Pipeline for chat_with_video()
-------------------------------
1. Retrieve top-k multimodal context from VideoIndex (video segments).
2. Read the last N messages from VideoChat's JSONL sidecar (ordered history).
3. Retrieve top-k semantically similar past messages from VideoChat (deduped).
4. Build a system prompt and stream the response from Gemini.
5. Persist both turns via VideoChat.record_turn().
"""

from __future__ import annotations

from typing import AsyncGenerator

from .vector_store.video_chat import default_video_chat
from .vector_store.video_index import default_video_index


async def chat_with_video(
    video_id: str,
    query: str,
    top_k_context: int = 10,
    top_k_chat: int = 10,
) -> AsyncGenerator[str, None]:
    """Stream a single-turn chat response against an indexed video.

    Yields text chunks as they arrive from Gemini.

    Args:
        video_id: The video to chat about.
        query: The user's question.
        top_k_context: Number of multimodal segment hits from VideoIndex.
        top_k_chat: Number of semantic chat hits from VideoChat.

    Yields:
        Incremental text chunks from the model.
    """
    vi = default_video_index()
    vc = default_video_chat()

    # 1. Multimodal context from video segments
    segment_hits = await vi.search(query, top_k=top_k_context, video_id=video_id)
    video_context = [r.content for r in segment_hits]

    # 2. Ordered history from zvec (chronological by timestamp)
    history = vc.get_history(video_id, last_n=20)

    # 3. Semantic chat context, deduped against ordered history
    semantic_hits = await vc.search(query, video_id=video_id, top_k=top_k_chat)
    seen_contents = {msg["content"] for msg in history}
    extra_context = [r.content for r in semantic_hits if r.content not in seen_contents]

    # 4. Stream the response and collect chunks for persistence
    answer_parts: list[str] = []
    async for chunk in _stream_response(
        query=query,
        video_context=video_context,
        history=history,
        extra_context=extra_context,
    ):
        answer_parts.append(chunk)
        yield chunk

    # 5. Persist both turns after streaming completes
    answer = "".join(answer_parts)
    if not answer.strip():
        raise ValueError("Empty response from Gemini")
    await vc.record_turn(video_id, "user", query)
    await vc.record_turn(video_id, "assistant", answer)


async def _stream_response(
    query: str,
    video_context: list[str],
    history: list[dict],
    extra_context: list[str],
) -> AsyncGenerator[str, None]:
    """Build a system prompt and stream Gemini response.
    Args:
        query: The user's question.
        video_context: Snippets from video_index retrieval.
        history: Ordered chat history dicts (role, content, timestamp).
        extra_context: Semantically similar past messages (deduped).

    Yields:
        Text chunks from the model as they are produced.
    """
    from google.genai import types

    from .gemini_client import GeminiClient
    from .prompts import chat_system_prompt

    system_prompt = chat_system_prompt(
        video_context=video_context,
        chat_history=history,
        extra_context=extra_context,
    )

    config = types.GenerateContentConfig(
        temperature=0.4,
        max_output_tokens=1024,
        response_mime_type="text/plain",
        system_instruction=system_prompt,
    )

    aclient = GeminiClient.get_client().aio
    async for chunk in await aclient.models.generate_content_stream(
        model="gemini-2.5-flash-lite",
        contents=[query],
        config=config,
    ):
        if chunk.text:
            yield chunk.text
