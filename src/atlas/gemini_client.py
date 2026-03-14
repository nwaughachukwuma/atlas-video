"""
Gemini API client for video analysis
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from google import genai

from .prompts import VideoAnalysisSchema
from .settings import settings
from .utils import RetryConfig, logger, process_time, retry

if TYPE_CHECKING:
    from google.genai import types as genai_types


api_key = os.environ["GEMINI_API_KEY"]


def get_gemini_client() -> genai.Client:
    """Create a Gemini client for the current call site."""
    return genai.Client(api_key=api_key)


def get_gemini_aio_client():
    """Return an async Gemini client bound to a fresh underlying client."""
    return get_gemini_client().aio


class GeminiMediaEngine:
    """Engine for analyzing media using Gemini"""

    def __init__(self):
        pass

    @process_time()
    @retry(RetryConfig(max_retries=2, delay=5, backoff=1.5))
    async def upload_file_async(self, file_path: str) -> "genai_types.File":
        """Upload a file to Gemini asynchronously"""
        return await get_gemini_aio_client().files.upload(file=file_path)

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
    ) -> VideoAnalysisSchema:
        """Describe audio/video media file using Gemini"""
        from google.genai import types

        @retry(RetryConfig(max_retries=1, delay=3, backoff=1.5))
        async def _handler(model_name: str) -> VideoAnalysisSchema:
            response = await get_gemini_aio_client().models.generate_content(
                model=model_name,
                contents=[file_part, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=VideoAnalysisSchema.model_json_schema(),
                ),
            )
            if not response.text:
                raise ValueError("Error describing media using Gemini")

            return VideoAnalysisSchema.model_validate_json(response.text)

        try:
            return await _handler(settings.gemini_model)
        except Exception as e:
            logger.error(f"Error with {settings.gemini_model}: {e}. Falling back")
            return await _handler(settings.gemini_fallback_model)

    @process_time()
    async def generate_summary(
        self,
        content: str,
        system_prompt: str,
    ) -> str:
        """Generate text using Gemini"""
        from google.genai import types

        @retry(RetryConfig(max_retries=2, delay=5, backoff=1.5))
        async def _handler() -> str:
            response = await get_gemini_aio_client().models.generate_content(
                model=settings.gemini_model,
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
