import pytest
import httpx
import json
from unittest.mock import AsyncMock, patch
from api.main import app
from api.schemas.query import SearchResult

@pytest.mark.asyncio
@patch("api.routes.query.classify_intent")
async def test_intent_routing_chitchat(mock_classify):
    """
    Tests that chitchat intent is rejected immediately with a static message.
    """
    # 1. Mock classify_intent to return chitchat
    mock_classify.return_value = "chitchat"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("api.routes.query.search_web_async") as mock_search, \
             patch("api.routes.query.rerank_results_async") as mock_rerank, \
             patch("api.routes.query.stream_llm_response") as mock_stream_llm:
            
            # Use stream call to check yielded lines
            async with ac.stream("POST", "/api/query", json={"query": "hello there"}) as response:
                assert response.status_code == 200
                lines = []
                async for line in response.aiter_lines():
                    if line.strip():
                        lines.append(line.strip())
            
            # Verify search, rerank, and stream_llm_response were never called
            mock_search.assert_not_called()
            mock_rerank.assert_not_called()
            mock_stream_llm.assert_not_called()
            
            # Verify classify_intent was called with query and no history
            mock_classify.assert_called_once_with("hello there", None)

            # Verify that the static rejection message was sent in the token event
            assert any("I am a real-time search assistant. I can only answer queries that require web search." in l for l in lines)

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


from api.schemas.query import ChatMessage
from api.services.llm import rewrite_query, stream_llm_response

@pytest.mark.asyncio
@patch("api.services.llm.get_fast_completion")
async def test_rewrite_query_single_call(mock_get_completion):
    """
    Verifies that rewrite_query performs a single direct LLM query rewriting call.
    """
    mock_get_completion.return_value = "SQE1 law exam passing requirements"

    history = [ChatMessage(role="user", content="Tell me about the SQE1 law exam")]
    result = await rewrite_query("how do I pass it", history)

    assert result == "SQE1 law exam passing requirements"
    mock_get_completion.assert_called_once()
    
    # Check that it uses system prompt
    call_messages = mock_get_completion.call_args[0][0]
    assert any("query transformation" in m["content"] for m in call_messages if m["role"] == "system")


@pytest.mark.asyncio
@patch("api.services.llm.get_fast_completion")
@patch("httpx.AsyncClient.stream")
async def test_stream_llm_response_single_call(mock_http_stream, mock_get_completion):
    """
    Verifies that stream_llm_response streams the answer in a single call without separate planning calls.
    """
    mock_response = AsyncMock()
    mock_response.status_code = 200
    
    async def mock_iter_lines():
        yield "data: {\"choices\": [{\"delta\": {\"content\": \"Factual response text\"}}]}"
        yield "data: [DONE]"
        
    mock_response.aiter_lines = mock_iter_lines
    
    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_http_stream.return_value = mock_stream_ctx

    sources = [SearchResult(title="Source 1", url="http://src.com", content="Specific context details", score=0.9)]
    
    events = []
    async for event in stream_llm_response("Test query", sources, history=[]):
        events.append(event)
        
    # Verify no planning completion call was made
    mock_get_completion.assert_not_called()

    # Verify streaming call was made
    mock_http_stream.assert_called_once()
    post_payload = mock_http_stream.call_args[1]["json"]
    final_messages = post_payload["messages"]
    
    assert any("precise web search assistant" in m["content"] for m in final_messages if m["role"] == "system")
    assert any(e.get("type") == "token" and e.get("token") == "Factual response text" for e in events)


from api.services.llm import sanitize_history

def test_sanitize_history_keeps_only_last_message():
    """
    Verifies that sanitize_history only returns the last message from the history,
    truncating it if it is a long assistant message.
    """
    history = [
        ChatMessage(role="user", content="Query 1"),
        ChatMessage(role="assistant", content="Answer 1"),
        ChatMessage(role="user", content="Query 2"),
        ChatMessage(role="assistant", content="Answer 2 is a very long response " * 20)
    ]
    
    sanitized = sanitize_history(history)
    
    # It should only have 1 message (the last one)
    assert len(sanitized) == 1
    assert sanitized[0]["role"] == "assistant"
    # It should be truncated since it is over 400 characters
    assert len(sanitized[0]["content"]) <= 405  # 400 + "..."
    assert sanitized[0]["content"].endswith("...")

    # If history is empty
    assert sanitize_history([]) == []
    assert sanitize_history(None) == []


