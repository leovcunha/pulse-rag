import pytest
import httpx
import json
from unittest.mock import AsyncMock, patch
from api.main import app
from api.schemas.query import SearchResult

@pytest.mark.asyncio
@patch("api.routes.query.classify_intent")
@patch("api.routes.query.stream_llm_response")
async def test_intent_routing_chitchat(mock_stream_llm, mock_classify):
    """
    Tests that chitchat intent skips search and rerank entirely.
    """
    # 1. Mock classify_intent to return chitchat
    mock_classify.return_value = "chitchat"

    # 2. Mock LLM generator
    async def mock_generator(*args, **kwargs):
        yield {"type": "token", "token": "Hello! I am a RAG chatbot. How can I help you?"}
    mock_stream_llm.return_value = mock_generator()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("api.routes.query.search_web_async") as mock_search, \
             patch("api.routes.query.rerank_results_async") as mock_rerank:
            
            response = await ac.post("/api/query", json={"query": "hello there"})
            assert response.status_code == 200
            
            # Verify search and rerank were never called
            mock_search.assert_not_called()
            mock_rerank.assert_not_called()
            
            # Verify classify_intent was called with query and no history
            mock_classify.assert_called_once_with("hello there", None)

@pytest.mark.asyncio
@patch("api.routes.query.classify_intent")
@patch("api.routes.query.rewrite_query")
@patch("api.routes.query.search_web_async", new_callable=AsyncMock)
@patch("api.routes.query.rerank_results_async", new_callable=AsyncMock)
@patch("api.routes.query.stream_llm_response")
async def test_intent_routing_search(
    mock_stream_llm, mock_rerank, mock_search, mock_rewrite, mock_classify
):
    """
    Tests that real_time_search intent rewrites query, triggers search/rerank, and streams answer.
    """
    # 1. Mock intent and rewrite
    mock_classify.return_value = "real_time_search"
    mock_rewrite.return_value = "SQE1 UK law exam preparation strategies"

    # 2. Mock search & rerank
    mock_search.return_value = ([], 100.0)
    mock_rerank.return_value = ([], 50.0)

    # 3. Mock LLM generator
    async def mock_generator(*args, **kwargs):
        yield {"type": "token", "token": "To pass SQE1..."}
    mock_stream_llm.return_value = mock_generator()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/query", json={
            "query": "how do I pass it",
            "history": [{"role": "user", "content": "Tell me about SQE1 UK law exam"}]
        })
        assert response.status_code == 200
        
        # Verify query was rewritten using history
        mock_rewrite.assert_called_once()
        assert mock_rewrite.call_args[0][0] == "how do I pass it"
        assert len(mock_rewrite.call_args[0][1]) == 1
        assert mock_rewrite.call_args[0][1][0].content == "Tell me about SQE1 UK law exam"

        # Verify search and rerank were called with rewritten query
        mock_search.assert_called_once_with("SQE1 UK law exam preparation strategies")
        mock_rerank.assert_called_once_with("SQE1 UK law exam preparation strategies", [])
