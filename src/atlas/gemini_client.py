"""
Gemini API client for video analysis
"""

import asyncio
import os
from typing import Optional

from google import genai
from google.genai import types

from .utils import RetryConfig, logger, process_time, retry


class GeminiClient:
    """Client for Google Gemini API"""

    _client: Optional[genai.Client] = None

    @classmethod
    def get_client(cls) -> genai.Client:
        """Get or create Gemini client"""
        if cls._client is None:
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
    async def upload_file_async(self, file_path: str) -> types.File:
        """Upload a file to Gemini asynchronously"""
        return await asyncio.to_thread(
            self.client.files.upload,
            file_path,
        )

    @process_time()
    @retry(RetryConfig(max_retries=2, delay=5, backoff=1.5))
    async def get_file_part(self, file_path: str, mime_type: str) -> types.Part:
        """Get a file part for Gemini API"""
        file = await self.upload_file_async(file_path)
        return types.Part.from_uri(file_uri=file.uri, mime_type=mime_type)

    @process_time()
    async def describe_media_from_file(
        self,
        file_part: types.Part,
        system_prompt: str,
        prompt: str = "Now, describe the video.",
    ) -> str:
        """Describe audio/video media file using Gemini"""

        @retry(RetryConfig(max_retries=1, delay=3, backoff=1.5))
        def _handler(model_name: str) -> str:
            response = self.client.models.generate_content(
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
            return await asyncio.to_thread(_handler, "gemini-2.5-flash-lite")
        except Exception as e:
            logger.error(f"Error with gemini-2.5-flash-lite: {e}. Falling back to gemini-2.5-flash")
            return await asyncio.to_thread(_handler, "gemini-2.5-flash")

    @process_time()
    async def generate_summary(
        self,
        content: str,
        system_prompt: str,
        model: str = "gemini-2.5-flash-lite",
    ) -> str:
        """Generate text using Gemini"""

        @retry(RetryConfig(max_retries=2, delay=5, backoff=1.5))
        def _handler() -> str:
            response = self.client.models.generate_content(
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

        return await asyncio.to_thread(_handler)
