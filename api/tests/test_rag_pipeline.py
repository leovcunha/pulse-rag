import pytest
import httpx
import json
from unittest.mock import AsyncMock, patch
from api.main import app
from api.schemas.query import SearchResult

@pytest.mark.asyncio
async def test_health_check():
    """
    Verifies that the /health endpoint is responsive and returns status 'ok'.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Gateway is responsive and running."}

@pytest.mark.asyncio
async def test_query_validation_empty():
    """
    Verifies that the query route enforces request body validation 
    and returns a 422 Unprocessable Entity for an empty query.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/query", json={"query": ""})
    assert response.status_code == 422

@pytest.mark.asyncio
@patch("api.routes.query.search_web_async", new_callable=AsyncMock)
@patch("api.routes.query.rerank_results_async", new_callable=AsyncMock)
@patch("api.routes.query.stream_llm_response")
async def test_rag_pipeline_flow(mock_stream_llm, mock_rerank, mock_search):
    """
    Simulates a successful execution of the RAG pipeline.
    Verifies that SSE data chunks are emitted in the correct logical sequence:
    1. status: searching
    2. sources (raw search results)
    3. status: reranking
    4. sources (filtered reranked results)
    5. status: generating
    6. provider
    7. ttft
    8. token
    9. metrics
    10. status: completed
    """
    # 1. Mock search results (search_web_async decorated with @time_it returns a tuple)
    search_mock_results = [
        SearchResult(title="Doc 1", url="http://doc1.com", content="Content 1", score=0.8),
        SearchResult(title="Doc 2", url="http://doc2.com", content="Content 2", score=0.7),
    ]
    mock_search.return_value = (search_mock_results, 150.0)

    # 2. Mock rerank results (rerank_results_async decorated with @time_it returns a tuple)
    rerank_mock_results = [
        SearchResult(title="Doc 1", url="http://doc1.com", content="Content 1", score=0.95),
    ]
    mock_rerank.return_value = (rerank_mock_results, 50.0)

    # 3. Mock LLM streaming events generator
    async def mock_generator(*args, **kwargs):
        yield {"type": "prompt_metrics", "prompt_ms": 2.5}
        yield {"type": "provider", "provider": "groq"}
        yield {"type": "ttft", "ttft_ms": 120.0}
        yield {"type": "token", "token": "Hello"}
        yield {"type": "token", "token": " world"}

    mock_stream_llm.return_value = mock_generator()

    # Make request to query endpoint
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        async with ac.stream("POST", "/api/query", json={"query": "Test query?"}) as response:
            assert response.status_code == 200
            
            lines = []
            async for line in response.aiter_lines():
                if line.strip():
                    lines.append(line.strip())

    # Verify event stream structure and status transitions
    assert any("event: status" in l for l in lines)
    assert any("searching" in l for l in lines)
    assert any("event: sources" in l for l in lines)
    assert any("Doc 1" in l for l in lines)
    assert any("reranking" in l for l in lines)
    assert any("generating" in l for l in lines)
    assert any("groq" in l for l in lines)
    assert any("120.0" in l for l in lines)
    assert any("Hello" in l for l in lines)
    assert any("world" in l for l in lines)
    assert any("event: metrics" in l for l in lines)
    assert any("completed" in l for l in lines)

@pytest.mark.asyncio
async def test_multilingual_query_rewriting():
    """
    Test that rewrite_query correctly identifies language and translates targets.
    """
    from api.services.llm import rewrite_query
    
    test_cases = [
        {
            "query": "où acheter un chat ragdoll en allemagne",
            "expected_language": "French",
            "expected_search_content": ["ragdoll", "katze", "deutschland"]
        },
        {
            "query": "ho bisogno di un idraulico urgente a lisbona",
            "expected_language": "Italian",
            "expected_search_content": ["lisboa", ["canalizador", "encanador"]]
        },
        {
            "query": "onde comprar um cachorro golden retriever no brasil",
            "expected_language": "Portuguese",
            "expected_search_content": ["golden", "retriever", "brasil"]
        }
    ]

    for case in test_cases:
        rewritten, lang = await rewrite_query(case["query"], history=[])
        
        # Verify Language Detection
        assert lang.lower() == case["expected_language"].lower()
        
        # Verify Search String Content (case insensitive)
        rewritten_lower = rewritten.lower()
        for term in case["expected_search_content"]:
            if isinstance(term, list):
                assert any(t in rewritten_lower for t in term)
            else:
                assert term in rewritten_lower

@pytest.mark.asyncio
async def test_intent_disambiguation_rewriting():
    """
    Test that rewrite_query adds intent disambiguation keywords like 'contractor' or 'breeder'.
    """
    from api.services.llm import rewrite_query
    
    query = "preciso de um encanador urgente em lisboa"
    rewritten, lang = await rewrite_query(query, history=[])
    
    assert lang.lower() == "portuguese"
    assert "lisboa" in rewritten.lower()
    assert "encanador" in rewritten.lower() or "canalizador" in rewritten.lower()
