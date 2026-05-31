import asyncio
import httpx
import logging
from typing import List
from api.schemas.query import SearchResult
from api.config import settings

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"

async def search_web_async(query: str, max_results: int = 10) -> List[SearchResult]:
    """
    Asynchronously queries the Tavily Search API.
    Returns a list of SearchResult models.
    """
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        logger.warning("TAVILY_API_KEY is not set in settings. Returning empty results.")
        return []

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "ultra-fast",
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "max_results": max_results
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(settings.TAVILY_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0.0)
                ))
            return results
    except Exception as e:
        logger.error(f"Error during Tavily Search: {str(e)}")
        # Return empty list on failure rather than crashing the pipeline
        return []
