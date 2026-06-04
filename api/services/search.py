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
async def search_web_async(query: str, max_results: int = 15) -> List[SearchResult]:
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

    def is_annoying_content(title_str: str, url_str: str, content_str: str) -> bool:
        t_lower = title_str.lower()
        u_lower = url_str.lower()
        c_lower = content_str.lower()
        
        # Annoying URL, path, or domain patterns
        annoying_url_patterns = [
            "/jobs/", "/careers/", "/career/", "/vacancy/", "/vacancies/", 
            "skool.com", "recruitment", "recruiting", "hiring", "job-description",
            "dealroom.co", "crunchbase.com", "pitchbook.com", "/candidate/", "/candidates/",
            "job-seeker", "cv-library"
        ]
        for pat in annoying_url_patterns:
            if pat in u_lower:
                return True
                
        # Annoying keywords in title (e.g. job titles, career portals, company databases)
        annoying_title_keywords = [
            "hiring", "careers", "jobs", "job vacancy", "job description", "salary range", "apply here",
            "apply now", "recruitment", "recruiting", "recruitment agency", "career opportunities",
            "candidate", "resume", "cv", "vacancy", "vacancies", "internship", "internships", "recruit",
            "sign up today", "automated client acquisition", "marketing agency", "sponsored", "advertisement",
            "company profile", "funding & investors"
        ]
        for kw in annoying_title_keywords:
            if kw in t_lower:
                return True
                
        # Annoying keywords in content (clear matches to filter job postings/marketing noise)
        annoying_content_keywords = [
            "job description", "apply here", "apply now", "recruitment agency", "salary range",
            "automated client acquisition", "sign up today", "candidate background", "negotiable salary",
            "employers and jobs", "job-seeker", "hiring decision", "resume", "request this candidate",
            "job platform", "job marketplace", "hiring platform", "talent acquisition", "recruiters",
            "career paths", "join our free community", "sponsored", "advertisement", "skool.com",
            "automated-client-acquisition"
        ]
        for kw in annoying_content_keywords:
            if kw in c_lower:
                return True
                
        return False

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(settings.TAVILY_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            results = []
            seen_titles = set()
            seen_urls = set()
            for item in data.get("results", []):
                title = item.get("title", "")
                url = item.get("url", "")
                content = item.get("content", "")
                
                # Filter out annoying job descriptions or promotional noise
                if is_annoying_content(title, url, content):
                    logger.info(f"Filtered out annoying result: {title} ({url})")
                    continue
                    
                title_lower = title.strip().lower()
                # Normalize URL to check for duplicates (strip query params, fragments, and trailing slashes)
                url_normalized = url.split("?")[0].split("#")[0].rstrip("/")
                
                if title_lower in seen_titles or url_normalized in seen_urls:
                    continue
                seen_titles.add(title_lower)
                seen_urls.add(url_normalized)
                
                results.append(SearchResult(
                    title=title,
                    url=url,
                    content=content,
                    score=item.get("score", 0.0)
                ))
            return results
    except Exception as e:
        logger.error(f"Error during Tavily Search: {str(e)}")
        # Return empty list on failure rather than crashing the pipeline
        return []
