import pytest
import httpx
from fastapi import Request
from unittest.mock import Mock, patch
from api.utils.rate_limiter import get_real_ip, limiter
from api.main import app

def test_get_real_ip_x_forwarded_for():
    """
    Verifies that get_real_ip extracts the first IP address from the X-Forwarded-For header.
    """
    request = Mock(spec=Request)
    request.headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
    request.client = Mock()
    request.client.host = "127.0.0.1"
    
    ip = get_real_ip(request)
    assert ip == "203.0.113.195"

def test_get_real_ip_fallback_to_client_host():
    """
    Verifies that get_real_ip falls back to request.client.host if the X-Forwarded-For header is missing.
    """
    request = Mock(spec=Request)
    request.headers = {}
    request.client = Mock()
    request.client.host = "192.168.1.50"
    
    ip = get_real_ip(request)
    assert ip == "192.168.1.50"

def test_get_real_ip_no_client():
    """
    Verifies that get_real_ip defaults to '127.0.0.1' if client and X-Forwarded-For are both missing.
    """
    request = Mock(spec=Request)
    request.headers = {}
    request.client = None
    
    ip = get_real_ip(request)
    assert ip == "127.0.0.1"

@pytest.mark.asyncio
@patch("api.routes.query.search_web_async")
@patch("api.routes.query.rerank_results_async")
@patch("api.routes.query.stream_llm_response")
async def test_rate_limiting_query_endpoint(mock_stream, mock_rerank, mock_search):
    """
    Verifies that the /api/query endpoint enforces a rate limit (returns 429 after 10 requests).
    """
    limiter.reset()
    
    # Mock pipeline services to return empty metrics and stream immediately
    mock_search.return_value = ([], 0.0)
    mock_rerank.return_value = ([], 0.0)
    async def mock_generator(*args, **kwargs):
        yield {"type": "token", "token": "Test token"}
    mock_stream.return_value = mock_generator()
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Make 10 requests (under the 10/hour limit)
        for _ in range(10):
            response = await ac.post("/api/query", json={"query": "Test rate limiter"})
            assert response.status_code == 200
            
        # The 11th request must exceed the rate limit and return 429
        response = await ac.post("/api/query", json={"query": "Test rate limiter"})
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.text

@pytest.mark.asyncio
@patch("api.routes.query.search_web_async")
@patch("api.routes.query.rerank_results_async")
@patch("api.routes.query.stream_llm_response")
async def test_rate_limiting_search_alias_endpoint(mock_stream, mock_rerank, mock_search):
    """
    Verifies that the /api/search route alias also enforces the rate limit.
    """
    limiter.reset()
    
    mock_search.return_value = ([], 0.0)
    mock_rerank.return_value = ([], 0.0)
    async def mock_generator(*args, **kwargs):
        yield {"type": "token", "token": "Test token"}
    mock_stream.return_value = mock_generator()
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        for _ in range(10):
            response = await ac.post("/api/search", json={"query": "Test rate limiter"})
            assert response.status_code == 200
            
        response = await ac.post("/api/search", json={"query": "Test rate limiter"})
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.text
