from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.text_embedding import embed_text


@pytest.mark.asyncio
async def test_embed_text_uses_loop_safe_gemini_accessor():
    mock_result = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.values = [0.1, 0.2, 0.3]
    mock_result.embeddings = [mock_embedding]

    mock_aclient = MagicMock()
    mock_aclient.models.embed_content = AsyncMock(return_value=mock_result)

    with patch("atlas.gemini_client.get_gemini_aio_client", return_value=mock_aclient):
        result = await embed_text("hello", "RETRIEVAL_QUERY")

    assert result == [0.1, 0.2, 0.3]
    mock_aclient.models.embed_content.assert_awaited_once()
