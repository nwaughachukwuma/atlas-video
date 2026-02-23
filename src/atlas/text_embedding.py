"""
Text embedding using Gemini API
"""

from __future__ import annotations

from .utils import logger


class TextEmbedding:
    """Get text embeddings using Gemini"""

    def __init__(self, content: str):
        self.content = content

    async def get_embedding(self, dimensionality: int = 768) -> list[float]:
        """Get text embedding using Gemini embedding model
        Args:
            dimensionality: Output dimension (768 or 3072 for gemini-embedding-001)
        Returns:
            List of embedding values
        """
        from google.genai import types

        from .gemini_client import GeminiClient

        try:
            result = await GeminiClient.get_client().aio.models.embed_content(
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


async def embed_text(content: str, dimensionality=768) -> list[float]:
    """Convenience method to get text embedding
    Args:
        content: Text content to embed
        dimensionality: Output dimension (768 or 3072)
    Returns:
        List of embedding values
    """
    return await TextEmbedding(content).get_embedding(dimensionality)
