import asyncio
import httpx
import logging
from typing import List
from api.schemas.query import SearchResult
from api.config import settings
from api.utils.time import time_it

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"

@time_it
async def search_web_async(query: str, max_results: int = 8) -> List[SearchResult]:
    """
    Asynchronously queries the Tavily Search API.
    Returns a list of SearchResult models.
    """
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        logger.warning("TAVILY_API_KEY is not set in settings. Returning empty results.")
        return []

    # Append negative constraints to filter out job boards/commercial recruiting noise
    refined_query = f"{query} -jobs -careers -recruitment"

    payload = {
        "api_key": api_key,
        "query": refined_query,
        "search_depth": "ultra-fast",
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "max_results": max_results,
        "exclude_domains": [
            "jobeka.com", "jobeka.co.uk", "indeed.com", "glassdoor.com", 
            "linkedin.com", "ziprecruiter.com", "monster.com", "simplyhired.com", 
            "careerbuilder.com", "totaljobs.com", "reed.co.uk", "jobsite.co.uk"
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(settings.TAVILY_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            results = []
            seen_titles = set()
            seen_urls = set()
            for item in data.get("results", []):
                title = item.get("title", "").strip().lower()
                # Normalize URL to check for duplicates (strip query params, fragments, and trailing slashes)
                url_normalized = item.get("url", "").split("?")[0].split("#")[0].rstrip("/")
                
                if title in seen_titles or url_normalized in seen_urls:
                    continue
                seen_titles.add(title)
                seen_urls.add(url_normalized)
                
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
