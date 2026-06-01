import httpx
import logging
from typing import List
from api.schemas.query import SearchResult
from api.config import settings
from api.utils.time import time_it

logger = logging.getLogger(__name__)

@time_it
async def rerank_results_async(query: str, search_results: List[SearchResult], min_score: float = 0.6, top_n: int = 3) -> List[SearchResult]:
    """
    Reranks search results using the Cohere Rerank API.
    Filters out results with scores below min_score and returns top_n items.
    If API fails, falls back to returning the first top_n search results directly.
    """
    if not search_results:
        return []

    api_key = settings.COHERE_API_KEY
    if not api_key:
        logger.warning("COHERE_API_KEY is not set in settings. Falling back to default search rankings.")
        return search_results[:top_n]

    # Prepare document texts for the Rerank API
    documents = [res.content for res in search_results]
    
    payload = {
        "model": "rerank-english-v3.0",
        "query": query,
        "documents": documents,
        "top_n": top_n
    }
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        async with httpx.AsyncClient(timeout=0.8) as client:
            response = await client.post(settings.COHERE_RERANK_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            reranked_results = []
            for item in data.get("results", []):
                idx = item.get("index")
                score = item.get("relevance_score", 0.0)
                
                # Check score constraint (>= min_score)
                if score >= min_score:
                    original_result = search_results[idx]
                    # Update score to rerank score
                    original_result.score = score
                    reranked_results.append(original_result)
            
            # If everything was filtered out, we can fallback to the single highest scoring result
            if not reranked_results and search_results:
                logger.warning("All results were below Cohere score threshold. Returning highest search result.")
                return search_results[:1]

            return reranked_results[:top_n]
            
    except Exception as e:
        logger.error(f"Error during Cohere Reranking: {str(e)}. Falling back to default search rankings.")
        # Fallback: return the top_n results based on initial search scores
        return search_results[:top_n]
