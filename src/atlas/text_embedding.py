"""
Text embedding using Gemini API
"""

from __future__ import annotations

from typing import Literal

from .utils import logger

TaskType = Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT", "QUESTION_ANSWERING"]


class TextEmbedding:
    """Get text embeddings using Gemini"""

    def __init__(self, content: str):
        self.content = content

    async def get_embedding(
        self,
        task_type: TaskType,
        dimensionality=768,
    ) -> list[float]:
        """Get text embedding using Gemini embedding model
        Args:
            dimensionality: Output dimension (768 or 3072 for gemini-embedding-001)
        Returns:
            List of embedding values
        """
        from google.genai import types

        from .gemini_client import gemini_client

        try:
            result = await gemini_client.aio.models.embed_content(
                model="gemini-embedding-001",
                contents=self.content,
                config=types.EmbedContentConfig(
                    output_dimensionality=dimensionality,
                    task_type=task_type,
                ),
            )

            if not result.embeddings or not result.embeddings[0].values:
                raise ValueError("Could not generate text embedding for your content")

            return result.embeddings[0].values

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise


async def embed_text(
    content: str,
    task_type: TaskType,
    dimensionality=768,
) -> list[float]:
    """Convenience method to get text embedding
    Args:
        content: Text content to embed
        dimensionality: Output dimension (768 or 3072)
    Returns:
        List of embedding values
    """
    return await TextEmbedding(content).get_embedding(task_type, dimensionality)
