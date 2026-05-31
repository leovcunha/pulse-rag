from pydantic import BaseModel, Field
from typing import List, Optional

class QueryRequest(BaseModel):
    query: str = Field(..., description="The user query to search and answer")

class SearchResult(BaseModel):
    title: str = Field(..., description="The title of the webpage")
    url: str = Field(..., description="The URL of the webpage")
    content: str = Field(..., description="Clean markdown or text snippet from the page")
    score: float = Field(default=0.0, description="Relevance score (Tavily or Cohere score)")

class LatencyMetrics(BaseModel):
    search_ms: float = Field(0.0, description="Time taken to fetch web search results")
    rerank_ms: float = Field(0.0, description="Time taken to rerank search results")
    prompt_ms: float = Field(0.0, description="Time taken to construct the LLM prompt")
    llm_ttft_ms: float = Field(0.0, description="Time to First Token (TTFT)")
    total_ms: float = Field(0.0, description="Total execution time of the request")
