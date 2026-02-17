"""
Text embedding using Gemini API
"""

import os
from typing import Optional

from google import genai
from google.genai import types

from .utils import logger


class TextEmbedding:
    """Get text embeddings using Gemini"""

    def __init__(self, content: str):
        self.content = content
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Get Gemini client"""
        if self._client is None:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable is required")
            self._client = genai.Client(api_key=api_key)
        return self._client

    def get_embedding(self, dimensionality: int = 768) -> list[float]:
        """Get text embedding using Gemini embedding model

        Args:
            dimensionality: Output dimension (768 or 3072 for gemini-embedding-001)

        Returns:
            List of embedding values
        """
        try:
            result = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=self.content,
                config=types.EmbedContentConfig(
                    output_dimensionality=dimensionality,
                ),
            )

            if not result.embeddings or not result.embeddings[0].values:
                raise ValueError("Could not generate text embedding for your content")

            return result.embeddings[0].values

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def get_embedding_async(self, dimensionality: int = 768) -> list[float]:
        """Get text embedding asynchronously"""
        import asyncio

        return await asyncio.to_thread(self.get_embedding, dimensionality)


def embed_text(content: str, dimensionality: int = 768) -> list[float]:
    """Convenience function to get text embedding

    Args:
        content: Text content to embed
        dimensionality: Output dimension (768 or 3072)

    Returns:
        List of embedding values
    """
    embedder = TextEmbedding(content)
    return embedder.get_embedding(dimensionality)


async def embed_text_async(content: str, dimensionality: int = 768) -> list[float]:
    """Convenience function to get text embedding asynchronously"""
    embedder = TextEmbedding(content)
    return await embedder.get_embedding_async(dimensionality)
