"""
Text embedding using Gemini API
"""

import asyncio

from google.genai import types

from .utils import logger
from .gemini_client import GeminiClient


class TextEmbedding:
    """Get text embeddings using Gemini"""

    def __init__(self, content: str):
        self.content = content
        self.client = GeminiClient.get_client()

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
        return await asyncio.to_thread(self.get_embedding, dimensionality)


def embed_text(content: str, dimensionality: int = 768) -> list[float]:
    """Convenience function to get text embedding
    Args:
        content: Text content to embed
        dimensionality: Output dimension (768 or 3072)
    Returns:
        List of embedding values
    """
    return TextEmbedding(content).get_embedding(dimensionality)


async def embed_text_async(content: str, dimensionality: int = 768) -> list[float]:
    """Convenience function to get text embedding asynchronously"""
    return await TextEmbedding(content).get_embedding_async(dimensionality)
