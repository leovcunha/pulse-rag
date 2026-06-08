import time
import json
import structlog
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from api.schemas.query import QueryRequest, LatencyMetrics
from api.services.search import search_web_async
from api.services.rerank import rerank_results_async
from api.services.llm import stream_llm_response, classify_intent, rewrite_query
from api.utils.rate_limiter import limiter
from api.utils.citation_filter import filter_citations
from api.config import settings

# Get the structlog configured logger for routing telemetry
logger = structlog.get_logger()

router = APIRouter()

@router.post("/query")
@router.post("/search")
@limiter.limit(settings.SEARCH_RATE_LIMIT)
async def query_rag(request: Request, query_request: QueryRequest):
    """
    POST endpoint that triggers the RAG pipeline.
    Orchestrates search, rerank, prompt assembly, LLM streaming, and fallback.
    Streams results back to the client using Server-Sent Events (SSE).
    """
    # We define an inner async event_generator function that yields dictionaries.
    # EventSourceResponse from sse-starlette maps these yielded items into SSE protocol lines.
    async def event_generator():
        # Start a high-resolution timer to measure end-to-end request duration
        start_total = time.perf_counter()
        
        # Initialize telemetry metrics parameters to be captured upon connection close/end
        search_results = []
        reranked_results = []
        token_count = 0
        provider_failover = False
        providers_tried = []
        llm_ttft_ms = 0.0
        status_code = 200
        search_ms = 0.0
        rerank_ms = 0.0
        prompt_ms = 0.0
        ttft_recorded_at = None

        try:
            # === Phase 0: Intent Routing ===
            yield {
                "event": "status",
                "data": json.dumps({"status": "routing"})
            }
            intent = await classify_intent(query_request.query, query_request.history)
            logger.info("intent_routed", query=query_request.query, intent=intent)

            if intent == "chitchat":
                # Immediately reject chitchat and terminate the pipeline
                yield {
                    "event": "status",
                    "data": json.dumps({"status": "generating"})
                }
                
                providers_tried = ["system"]
                yield {
                    "event": "provider",
                    "data": json.dumps({"provider": "system"})
                }
                
                yield {
                    "event": "ttft",
                    "data": json.dumps({"ttft_ms": 0.0})
                }
                
                rejection_msg = "I am a real-time search assistant. I can only answer queries that require web search. Please ask a search-related question."
                token_count += 1
                yield {
                    "event": "token",
                    "data": json.dumps({"token": rejection_msg})
                }
            else:
                # === Phase 1: Query Expansion / Rewriting ===
                yield {
                    "event": "status",
                    "data": json.dumps({"status": "expanding"})
                }
                transformed_query, user_language = await rewrite_query(query_request.query, query_request.history)

                # Send status update with the transformed query so frontend shows what it is searching for
                yield {
                    "event": "status",
                    "data": json.dumps({
                        "status": "searching", 
                        "transformed_query": transformed_query
                    })
                }
                
                # Fetch search results asynchronously (returns list of SearchResult models and execution time in ms)
                search_results, search_ms = await search_web_async(transformed_query)
                
                # Send raw search results so client can render list of links early (optimistic rendering)
                yield {
                    "event": "sources",
                    "data": json.dumps({"sources": [s.model_dump() for s in search_results]})
                }
                
                # === Phase 2: Reranking ===
                # Send status update so frontend shows reranking progress
                yield {
                    "event": "status",
                    "data": json.dumps({"status": "reranking"})
                }
                # Use Cohere Rerank API to select top 3 most relevant search snippets
                reranked_results, rerank_ms = await rerank_results_async(transformed_query, search_results)
                
                # Send finalized reranked sources to update the sidebar links
                yield {
                    "event": "sources",
                    "data": json.dumps({"sources": [s.model_dump() for s in reranked_results]})
                }
                
                # === Phase 3: Prompt Synthesis and LLM Inference ===
                # Send status update so frontend indicates response text generation
                yield {
                    "event": "status",
                    "data": json.dumps({"status": "generating"})
                }
                
                ttft_recorded_at = None
                # Sentence buffer for citation deduplication.
                # Tokens are accumulated until a sentence boundary is detected,
                # then the buffer is deduped and flushed to the client.
                sentence_buffer = ""
                flushed_length = 0  # tracks how much of the answer has been flushed

                def flush_sentence_buffer(buffer: str) -> tuple:
                    """
                    Check the buffer for complete sentences, apply citation
                    deduplication, and return (text_to_yield, remaining_buffer).
                    """
                    # Find the last sentence-ending punctuation followed by a space or end
                    last_boundary = -1
                    for i, ch in enumerate(buffer):
                        if ch in '.!?' and (i + 1 >= len(buffer) or buffer[i + 1] in ' \n'):
                            last_boundary = i

                    if last_boundary == -1:
                        return "", buffer

                    complete = buffer[:last_boundary + 1]
                    remainder = buffer[last_boundary + 1:]
                    cleaned = filter_citations(complete)
                    return cleaned, remainder
                
                # Stream the LLM response asynchronously chunk by chunk
                async for event in stream_llm_response(
                    query_request.query, 
                    reranked_results, 
                    user_language,
                    history=query_request.history, 
                    is_chitchat=False
                ):
                    event_type = event.get("type")
                    
                    # 1. Prompt generation metrics event (indicates prompt text manipulation completed)
                    if event_type == "prompt_metrics":
                        prompt_ms = event.get("prompt_ms", 0.0)
                        
                    # 2. LLM Provider status (indicates which provider is running: groq or openrouter)
                    elif event_type == "provider":
                        prov = event.get("provider")
                        if prov not in providers_tried:
                            providers_tried.append(prov)
                        # If we tried more than 1 provider during the call, a failover occurred
                        if len(providers_tried) > 1:
                            provider_failover = True
                        yield {
                            "event": "provider",
                            "data": json.dumps({"provider": prov})
                        }
                        
                    # 3. Time-To-First-Token (TTFT) event
                    elif event_type == "ttft":
                        llm_ttft_ms = event.get("ttft_ms", 0.0)
                        ttft_recorded_at = time.perf_counter()
                        yield {
                            "event": "ttft",
                            "data": json.dumps({"ttft_ms": llm_ttft_ms})
                        }
                        
                    # 4. Content token chunk event — buffered for citation dedup
                    elif event_type == "token":
                        token_count += 1
                        raw_token = event.get("token", "")
                        sentence_buffer += raw_token

                        # Try to flush complete sentences
                        to_yield, sentence_buffer = flush_sentence_buffer(sentence_buffer)
                        if to_yield:
                            yield {
                                "event": "token",
                                "data": json.dumps({"token": to_yield})
                            }
                        
                    # 5. Fallback alert (emitted when primary LLM fails and fallback begins)
                    elif event_type == "fallback_alert":
                        provider_failover = True
                        yield {
                            "event": "fallback_alert",
                            "data": json.dumps({"message": event.get("message")})
                        }
                        
                    # 6. Provider-level errors
                    elif event_type == "error":
                        status_code = 500
                        yield {
                            "event": "error",
                            "data": json.dumps({"message": event.get("message")})
                        }

                # Flush any remaining text in the sentence buffer
                if sentence_buffer.strip():
                    cleaned_remainder = filter_citations(sentence_buffer)
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": cleaned_remainder})
                    }
                        
            # === Phase 4: Finalize Metrics ===
            # The RAG perceived latency SLA measures time up to the first token received
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
            
            # Send full performance metrics to the frontend
            yield {
                "event": "metrics",
                "data": json.dumps(metrics.model_dump())
            }
            
            # Final completion status
            yield {
                "event": "status",
                "data": json.dumps({"status": "completed"})
            }
            
        except Exception as e:
            # Catch server exceptions, log trace stack, and return 500 status code
            status_code = 500
            logger.exception("Exception in RAG pipeline generator", error=str(e))
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Server error: {str(e)}"})
            }
            
        finally:
            # The finally block is guaranteed to run upon stream completion or unexpected crashes.
            # We calculate final execution time and output a single structured JSON telemetry record.
            total_ms = (time.perf_counter() - start_total) * 1000.0
            cohere_rerank_drops = len(search_results) - len(reranked_results)
            logger.info(
                "rag_request",
                path=request.url.path,
                method=request.method,
                http_status=status_code,
                latency_ms=total_ms,
                token_count=token_count,
                ttft_ms=llm_ttft_ms,
                cohere_rerank_drops=cohere_rerank_drops,
                provider_failover=provider_failover,
                providers_tried=providers_tried
            )

    return EventSourceResponse(event_generator())

