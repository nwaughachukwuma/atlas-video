"""
Gemini API client for video analysis
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Literal, Optional

from .utils import RetryConfig, logger, process_time, retry

if TYPE_CHECKING:
    from google import genai
    from google.genai import types as genai_types


Model = Literal[
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-pro-preview",
]


class GeminiClient:
    """Client for Google Gemini API"""

    _client: Optional["genai.Client"] = None

    @classmethod
    def get_client(cls) -> "genai.Client":
        """Get Gemini client (lazy-initialised on first use)."""
        if cls._client is None:
            from google import genai

            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable is required")
            cls._client = genai.Client(api_key=api_key)
        return cls._client

    @classmethod
    def reset_client(cls) -> None:
        """Reset the client (useful for testing)"""
        cls._client = None


class GeminiMediaEngine:
    """Engine for analyzing media using Gemini"""

    def __init__(self):
        self.client = GeminiClient.get_client()

    @process_time()
    @retry(RetryConfig(max_retries=2, delay=5, backoff=1.5))
    async def upload_file_async(self, file_path: str) -> "genai_types.File":
        """Upload a file to Gemini asynchronously"""
        return await self.client.aio.files.upload(file=file_path)

    @process_time()
    @retry(RetryConfig(max_retries=2, delay=5, backoff=1.5))
    async def fetch_file_part(self, file_path: str, mime_type: str) -> "genai_types.Part":
        """Upload and retrieve a file part"""
        file = await self.upload_file_async(file_path)
        if not file.uri:
            raise Exception("Couldn't retrieve file uri")
        from google.genai import types

        return types.Part.from_uri(file_uri=file.uri, mime_type=mime_type)

    @process_time()
    @retry(RetryConfig(max_retries=2, delay=5, backoff=1.5))
    async def get_file_part(self, file_path: str, mime_type: str) -> "genai_types.Part":
        """
        Get file part from bytes
        """

        def handler():
            from google.genai import types

            with open(file_path, "rb") as f:
                data = f.read()
            return types.Part.from_bytes(data=data, mime_type=mime_type)

        return await asyncio.to_thread(handler)

    @process_time()
    async def describe_media_from_file(
        self,
        file_part: "genai_types.Part",
        system_prompt: str,
        prompt: str = "Now, describe the video.",
    ) -> str:
        """Describe audio/video media file using Gemini"""
        from google.genai import types

        @retry(RetryConfig(max_retries=1, delay=3, backoff=1.5))
        async def _handler(model_name: str) -> str:
            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=[file_part, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=240,
                    response_mime_type="text/plain",
                    system_instruction=system_prompt,
                ),
            )
            if not response.text:
                raise ValueError("Error describing media using Gemini")
            return response.text

        try:
            return await _handler("gemini-3.1-flash-lite-preview")
        except Exception as e:
            logger.error(f"Error with gemini-3.1-flash-lite-preview: {e}. Falling back to gemini-2.5-flash-lite")
            return await _handler("gemini-2.5-flash-lite")

    @process_time()
    async def generate_summary(
        self,
        content: str,
        system_prompt: str,
        model: Model = "gemini-3.1-flash-lite-preview",
    ) -> str:
        """Generate text using Gemini"""
        from google.genai import types

        @retry(RetryConfig(max_retries=2, delay=5, backoff=1.5))
        async def _handler() -> str:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=[content],
                config=types.GenerateContentConfig(
                    temperature=0.25,
                    max_output_tokens=256,
                    response_mime_type="text/plain",
                    system_instruction=system_prompt,
                ),
            )
            if not response.text:
                raise ValueError("Error generating summary")
            return response.text

        return await _handler()
