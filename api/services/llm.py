import os
import time
import json
import httpx
import logging
from typing import List, AsyncGenerator, Dict, Any
from api.schemas.query import SearchResult
from api.config import settings

logger = logging.getLogger(__name__)

# Directory where prompts are stored
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")

def load_prompt_file(filename: str) -> str:
    """Reads a prompt template file from the prompts directory."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

# Prompt formatting
def construct_prompt(query: str, sources: List[SearchResult]) -> tuple[str, str, float]:
    """
    Constructs system and user prompts by reading from prompt template resources.
    Returns: (system_prompt, user_prompt, duration_ms)
    """
    start_time = time.perf_counter()
    
    try:
        system_prompt = load_prompt_file("system_prompt.txt")
        user_prompt_template = load_prompt_file("user_prompt_template.txt")
    except Exception as e:
        logger.error(f"Error loading prompt resource files: {str(e)}. Using fallback instructions.")
        system_prompt = (
            "You are an ultra-fast, precise RAG assistant. You must answer the user query "
            "ONLY using the context sources provided below.\n"
            "For every claim or fact you state, you MUST append a citation index in brackets, "
            "such as [1], [2], or [3], matching the source index from the context.\n"
            "If the context does not contain the answer, you must respond exactly with: "
            "\"I do not know based on the provided sources.\""
        )
        user_prompt_template = "Context Sources:\n{context}\nUser Query: {query}\nAnswer:"
    
    context_str = ""
    if not sources:
        context_str = "No search results found.\n"
    else:
        for idx, src in enumerate(sources, 1):
            context_str += f"[{idx}] Title: {src.title}\nURL: {src.url}\nContent: {src.content}\n\n"
            
    user_prompt = user_prompt_template.format(context=context_str, query=query)
    
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000.0
    return system_prompt, user_prompt, duration_ms

async def stream_llm_response(query: str, sources: List[SearchResult]) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Streams response from Groq, falling back to OpenRouter if Groq fails or rate limits.
    Yields dictionary payloads containing tokens, latency metrics, and provider status.
    """
    system_prompt, user_prompt, prompt_ms = construct_prompt(query, sources)
    
    yield {"type": "prompt_metrics", "prompt_ms": prompt_ms}

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    groq_api_key = settings.GROQ_API_KEY
    openrouter_api_key = settings.OPENROUTER_API_KEY

    # Determine provider sequence
    providers = []
    if groq_api_key:
        providers.append({
            "name": "groq",
            "url": settings.GROQ_URL,
            "key": groq_api_key,
            "model": settings.GROQ_MODEL,
            "headers": {
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            }
        })
    else:
        logger.warning("GROQ_API_KEY is not set. Skipping Groq.")

    if openrouter_api_key:
        providers.append({
            "name": "openrouter",
            "url": settings.OPENROUTER_URL,
            "key": openrouter_api_key,
            "model": settings.OPENROUTER_MODEL,
            "headers": {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Sub-2-Second RAG"
            }
        })
    else:
        logger.warning("OPENROUTER_API_KEY is not set. openrouter fallback will not be available.")

    if not providers:
        yield {"type": "error", "message": "No LLM API keys configured (GROQ_API_KEY / OPENROUTER_API_KEY)."}
        return

    # Attempt providers sequentially
    for provider in providers:
        provider_name = provider["name"]
        logger.info(f"Attempting LLM inference with provider: {provider_name}")
        yield {"type": "provider", "provider": provider_name}

        payload = {
            "model": provider["model"],
            "messages": messages,
            "stream": True,
            "temperature": 0.0,
            "max_tokens": 512
        }

        start_call_time = time.perf_counter()
        ttft_recorded = False

        try:
            # Clean up invalid SSL_CERT_FILE to prevent httpx/ssl from crashing on HTTPS requests
            ssl_cert_file = os.environ.get("SSL_CERT_FILE")
            if ssl_cert_file and not os.path.exists(ssl_cert_file):
                os.environ.pop("SSL_CERT_FILE", None)

            # We use a 2.5 second timeout on Groq so we can fallback to OpenRouter quickly if it hangs
            timeout = httpx.Timeout(2.5, connect=1.5)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", provider["url"], json=payload, headers=provider["headers"]) as response:
                    
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error(f"Provider {provider_name} returned status {response.status_code}: {error_body.decode('utf-8', errors='ignore')}")
                        # Fall to next provider
                        continue

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                chunk_json = json.loads(data_str)
                                choices = chunk_json.get("choices", [])
                                if not choices:
                                    continue
                                
                                delta = choices[0].get("delta", {})
                                token = delta.get("content", "")
                                
                                if token:
                                    if not ttft_recorded:
                                        ttft_time = (time.perf_counter() - start_call_time) * 1000.0
                                        yield {"type": "ttft", "ttft_ms": ttft_time}
                                        ttft_recorded = True
                                    
                                    yield {"type": "token", "token": token}
                            except json.JSONDecodeError:
                                # Sometimes empty or malformed chunks happen in streaming
                                continue
            
            # If we successfully finished the stream, break out of provider loop
            return

        except Exception as e:
            logger.error(f"Error with provider {provider_name}: {str(e)}")
            yield {"type": "fallback_alert", "message": f"Provider {provider_name} failed. Falling back..."}
            continue  # try next provider

    yield {"type": "error", "message": "All configured LLM providers failed to respond."}
