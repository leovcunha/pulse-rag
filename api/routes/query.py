import time
import json
import logging
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from api.schemas.query import QueryRequest, LatencyMetrics
from api.services.search import search_web_async
from api.services.rerank import rerank_results_async
from api.services.llm import stream_llm_response

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/query")
async def query_rag(request: QueryRequest):
    """
    POST endpoint that triggers the RAG pipeline.
    Orchestrates search, rerank, prompt assembly, LLM streaming, and fallback.
    Streams results back to the client using Server-Sent Events (SSE).
    """
    async def event_generator():
        start_total = time.perf_counter()
        try:
            # Phase 1: Search
            yield {
                "event": "status",
                "data": json.dumps({"status": "searching"})
            }
            search_results, search_ms = await search_web_async(request.query)
            
            # Send raw search results so client has early visual feedback
            yield {
                "event": "sources",
                "data": json.dumps({"sources": [s.model_dump() for s in search_results]})
            }
            
            # Phase 2: Reranking
            yield {
                "event": "status",
                "data": json.dumps({"status": "reranking"})
            }
            reranked_results, rerank_ms = await rerank_results_async(request.query, search_results)
            
            # Send filtered and ranked sources
            yield {
                "event": "sources",
                "data": json.dumps({"sources": [s.model_dump() for s in reranked_results]})
            }
            
            # Phase 3: Prompt Synthesis and LLM Inference
            yield {
                "event": "status",
                "data": json.dumps({"status": "generating"})
            }
            
            prompt_ms = 0.0
            llm_ttft_ms = 0.0
            ttft_recorded_at = None
            
            # Stream the LLM response
            async for event in stream_llm_response(request.query, reranked_results):
                event_type = event.get("type")
                if event_type == "prompt_metrics":
                    prompt_ms = event.get("prompt_ms", 0.0)
                elif event_type == "provider":
                    yield {
                        "event": "provider",
                        "data": json.dumps({"provider": event.get("provider")})
                    }
                elif event_type == "ttft":
                    llm_ttft_ms = event.get("ttft_ms", 0.0)
                    ttft_recorded_at = time.perf_counter()
                    yield {
                        "event": "ttft",
                        "data": json.dumps({"ttft_ms": llm_ttft_ms})
                    }
                elif event_type == "token":
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": event.get("token")})
                    }
                elif event_type == "fallback_alert":
                    yield {
                        "event": "fallback_alert",
                        "data": json.dumps({"message": event.get("message")})
                    }
                elif event_type == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps({"message": event.get("message")})
                    }
                    
            # Phase 4: Finalize Metrics
            # The SLA measures the time up to the first token received (perceived latency)
            if ttft_recorded_at is not None:
                total_ms = (ttft_recorded_at - start_total) * 1000.0
            else:
                total_ms = (time.perf_counter() - start_total) * 1000.0
            
            metrics = LatencyMetrics(
                search_ms=search_ms,
                rerank_ms=rerank_ms,
                prompt_ms=prompt_ms,
                llm_ttft_ms=llm_ttft_ms,
                total_ms=total_ms
            )
            
            yield {
                "event": "metrics",
                "data": json.dumps(metrics.model_dump())
            }
            
            yield {
                "event": "status",
                "data": json.dumps({"status": "completed"})
            }
        except Exception as e:
            logger.exception("Exception in RAG pipeline generator")
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Server error: {str(e)}"})
            }

    return EventSourceResponse(event_generator())
