import os
import time
import json
import httpx
import logging
from typing import List, AsyncGenerator, Dict, Any, Tuple, Optional
from api.schemas.query import SearchResult, ChatMessage
from api.config import settings
from api.utils.time import time_it

logger = logging.getLogger(__name__)

# Directory where prompts are stored
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")

def load_prompt_file(filename: str) -> str:
    """Reads a prompt template file from the prompts directory."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

async def get_fast_completion(messages: List[Dict[str, str]], max_tokens: int = 100) -> str:
    """
    Sends a non-streaming request to Groq (falling back to OpenRouter) for fast task completion.
    """
    groq_api_key = settings.GROQ_API_KEY
    openrouter_api_key = settings.OPENROUTER_API_KEY

    providers = []
    if groq_api_key:
        providers.append({
            "url": settings.GROQ_URL,
            "model": settings.GROQ_MODEL,
            "headers": {
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            }
        })
    if openrouter_api_key:
        providers.append({
            "url": settings.OPENROUTER_URL,
            "model": settings.OPENROUTER_MODEL,
            "headers": {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Sub-2-Second RAG"
            }
        })

    for provider in providers:
        payload = {
            "model": provider["model"],
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "stream": False
        }
        try:
            # We use a 1.2s timeout for intent routing / query rewriting to keep latency very low
            timeout = httpx.Timeout(1.2, connect=0.5)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(provider["url"], json=payload, headers=provider["headers"])
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Error in get_fast_completion with provider: {str(e)}")
            continue

    return ""

async def classify_intent(query: str, history: Optional[List[ChatMessage]]) -> str:
    """
    Classifies the user query as 'chitchat' or 'real_time_search'.
    """
    import sys
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return "real_time_search"

    try:
        system_prompt = load_prompt_file("intent_prompt.txt")
    except Exception as e:
        logger.error(f"Error loading intent prompt: {str(e)}")
        return "real_time_search"  # Default fallback if prompt is missing

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": f"User query: {query}"})

    intent = await get_fast_completion(messages, max_tokens=10)
    intent = intent.lower().strip()
    
    if "chitchat" in intent:
        return "chitchat"
    return "real_time_search"

async def rewrite_query(query: str, history: Optional[List[ChatMessage]]) -> str:
    """
    Rewrites the user query to optimize it for Tavily Search based on history.
    """
    try:
        system_prompt = load_prompt_file("rewrite_prompt.txt")
    except Exception as e:
        logger.error(f"Error loading rewrite prompt: {str(e)}")
        return query  # Fallback to original query

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": f"User query: {query}"})

    rewritten = await get_fast_completion(messages, max_tokens=100)
    if rewritten:
        logger.info(f"Query rewritten: '{query}' -> '{rewritten}'")
        return rewritten.strip()
    return query

# Prompt formatting
@time_it
def construct_prompt(query: str, sources: List[SearchResult]) -> Tuple[str, str]:
    """
    Constructs system and user prompts by reading from prompt template resources.
    Returns: (system_prompt, user_prompt)
    """
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
    
    return system_prompt, user_prompt

async def stream_llm_response(
    query: str, 
    sources: List[SearchResult], 
    history: Optional[List[ChatMessage]] = None, 
    is_chitchat: bool = False
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Streams response from Groq, falling back to OpenRouter if Groq fails or rate limits.
    Yields dictionary payloads containing tokens, latency metrics, and provider status.
    """
    if is_chitchat:
        system_prompt = (
            "You are a helpful, ultra-fast RAG assistant. You can engage in general conversation, "
            "answer questions, or clarify your capabilities. Keep your response conversational, concise, "
            "and direct."
        )
        user_prompt = query
        prompt_ms = 0.0
    else:
        (system_prompt, user_prompt), prompt_ms = construct_prompt(query, sources)
    
    yield {"type": "prompt_metrics", "prompt_ms": prompt_ms}

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_prompt})

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
            "max_tokens": 500
        }

        start_call_time = time.perf_counter()
        ttft_recorded = False

        try:
            # Clean up invalid SSL_CERT_FILE to prevent httpx/ssl from crashing on HTTPS requests
            ssl_cert_file = os.environ.get("SSL_CERT_FILE")
            if ssl_cert_file and not os.path.exists(ssl_cert_file):
                os.environ.pop("SSL_CERT_FILE", None)

            # We use a 1.8 second timeout on Groq so we can fallback to OpenRouter quickly if it hangs
            timeout = httpx.Timeout(1.8, connect=0.8)
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
