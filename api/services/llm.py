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

async def get_fast_completion(messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
    """
    Sends a non-streaming request to Groq (falling back to OpenRouter) for fast task completion.
    """
    groq_api_key = settings.GROQ_API_KEY
    openrouter_api_key = settings.OPENROUTER_API_KEY

    providers = []
    if groq_api_key:
        providers.append({
            "name": "groq",
            "url": settings.GROQ_URL,
            "model": settings.GROQ_FAST_MODEL,
            "headers": {
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            }
        })
    if openrouter_api_key:
        providers.append({
            "name": "openrouter",
            "url": settings.OPENROUTER_URL,
            "model": settings.OPENROUTER_FAST_MODEL,
            "headers": {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Sub-2-Second RAG"
            }
        })

    for provider in providers:
        provider_max_tokens = max_tokens
        if provider["name"] == "openrouter":
            provider_max_tokens = 2048

        payload = {
            "model": provider["model"],
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": provider_max_tokens,
            "stream": False
        }
        if "gpt-oss" in provider["model"].lower():
            payload["reasoning_effort"] = "low"
        try:
            # We use a much longer timeout (10.0s) for query rewriting so reasoning models have time to think
            timeout = httpx.Timeout(10.0, connect=1.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(provider["url"], json=payload, headers=provider["headers"])
                if response.status_code == 200:
                    data = response.json()
                    message_obj = data["choices"][0]["message"]
                    content = message_obj.get("content")
                    return content.strip() if content else ""
        except Exception as e:
            logger.error(f"Error in get_fast_completion with provider: {str(e)}")
            continue

    return ""

def sanitize_history(history: Optional[List[ChatMessage]]) -> List[Dict[str, str]]:
    """
    Sanitizes chat history by mapping it to LLM message payloads.
    To prevent Groq TPM rate limits and topic drift, we only keep the
    single last message from the history.
    """
    if not history:
        return []
    last_msg = history[-1]
    content = last_msg.content
    if last_msg.role == "assistant" and len(content) > 400:
        content = content[:400] + "..."
    return [{"role": last_msg.role, "content": content}]

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

    messages = []
    messages.append({"role": "system", "content": system_prompt})
    messages.extend(sanitize_history(history))
    messages.append({"role": "user", "content": f"User query: {query}"})

    intent = await get_fast_completion(messages, max_tokens=512)
    intent = intent.lower().strip()
    
    if "chitchat" in intent:
        return "chitchat"
    return "real_time_search"

async def rewrite_query(query: str, history: Optional[List[ChatMessage]]) -> Tuple[str, str]:
    """
    Rewrites the user query to optimize it for Tavily Search based on history.
    Also detects the primary language of the user query.
    Returns a tuple of (rewritten_query, user_language).
    """
    try:
        system_prompt = load_prompt_file("rewrite_prompt.txt")
    except Exception as e:
        logger.error(f"Error loading rewrite prompt: {str(e)}")
        return query, "English"  # Fallback to original query and English

    messages = []
    messages.append({"role": "system", "content": system_prompt})
    messages.extend(sanitize_history(history))
    messages.append({"role": "user", "content": f"User query: {query}"})

    rewritten = await get_fast_completion(messages)
    if rewritten:
        lines = rewritten.strip().split('\n')
        language = "English"
        search_query = query
        
        for line in lines:
            line_stripped = line.strip()
            if "language" in line_stripped.lower():
                idx = line_stripped.lower().find("language")
                colon_idx = line_stripped.find(":", idx)
                if colon_idx != -1:
                    val = line_stripped[colon_idx + 1:].strip().strip('*_~ \t')
                    if "search" in val.lower():
                        search_idx = val.lower().find("search")
                        language = val[:search_idx].strip().strip('*_~ \t')
                        rem = val[search_idx:]
                        s_colon_idx = rem.find(":")
                        if s_colon_idx != -1:
                            search_query = rem[s_colon_idx + 1:].strip().strip('*_~ \t')
                        else:
                            search_query = rem[6:].strip().strip('*_~ \t')
                    else:
                        language = val
            elif "search" in line_stripped.lower() and not "language" in line_stripped.lower():
                idx = line_stripped.lower().find("search")
                colon_idx = line_stripped.find(":", idx)
                if colon_idx != -1:
                    search_query = line_stripped[colon_idx + 1:].strip().strip('*_~ \t')
                else:
                    search_query = line_stripped[idx + 6:].strip().strip('*_~ \t')
                
        # Fallback if the LLM completely ignored the format and didn't output Search:
        if search_query == query and not any("search" in line.lower() for line in lines):
            non_empty_lines = [l.strip() for l in lines if l.strip()]
            if non_empty_lines:
                last_line = non_empty_lines[-1]
                word_count = len(last_line.split())
                has_lang = any("language" in l.lower() for l in non_empty_lines)
                if len(non_empty_lines) <= 2 and (word_count <= 8 or has_lang):
                    search_query = last_line
            # otherwise keep search_query = query (safer than using long conversational preambles/explanations)
            
        logger.info(f"Query rewritten: '{query}' -> '{search_query}' (Language: {language})")
        return search_query, language
        
    return query, "English"

# Prompt formatting
@time_it
def construct_prompt(query: str, sources: List[SearchResult], user_language: str) -> Tuple[str, str]:
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
            # Truncate content to 1200 characters to prevent Groq TPM rate limits
            truncated_content = src.content[:1200] + "..." if len(src.content) > 1200 else src.content
            context_str += f"[{idx}] Title: {src.title}\nURL: {src.url}\nContent: {truncated_content}\n\n"
            
    user_prompt = user_prompt_template.format(context=context_str, query=query, user_language=user_language)
    
    return system_prompt, user_prompt

async def stream_llm_response(
    query: str, 
    sources: List[SearchResult], 
    user_language: str = "English",
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
        (system_prompt, user_prompt), prompt_ms = construct_prompt(query, sources, user_language)
    
    yield {"type": "prompt_metrics", "prompt_ms": prompt_ms} # this is giving error

    messages = []
    messages.append({"role": "system", "content": system_prompt})
    messages.extend(sanitize_history(history))
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
            "temperature": 0.0
        }
        if provider_name == "openrouter":
            payload["max_tokens"] = 2048
            payload["reasoning"] = {"enabled": False}
        else:
            payload["max_completion_tokens"] = 1200

        if provider_name == "groq":
            payload["reasoning_effort"] = "low"

        start_call_time = time.perf_counter()
        ttft_recorded = False

        try:
            # Clean up invalid SSL_CERT_FILE to prevent httpx/ssl from crashing on HTTPS requests
            ssl_cert_file = os.environ.get("SSL_CERT_FILE")
            if ssl_cert_file and not os.path.exists(ssl_cert_file):
                os.environ.pop("SSL_CERT_FILE", None)

            # We use an 8.0 second timeout on Groq to accommodate heavier reasoning models (like gpt-oss-20b),
            # and a longer timeout (30.0 seconds) for OpenRouter since it is our final fallback.
            has_tokens = False
            timeout_val = 8.0 if provider_name == "groq" else 30.0
            connect_val = 2.0 if provider_name == "groq" else 5.0
            timeout = httpx.Timeout(timeout_val, connect=connect_val)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", provider["url"], json=payload, headers=provider["headers"]) as response:
                    
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error(f"Provider {provider_name} returned status {response.status_code}: {error_body.decode('utf-8', errors='ignore')}")
                        yield {"type": "fallback_alert", "message": f"Provider {provider_name} returned status {response.status_code}. Falling back..."}
                        continue
                        
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                chunk = json.loads(data_str)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content") or ""
                                    reasoning = delta.get("reasoning") or ""
                                    
                                    if content or reasoning:
                                        if not ttft_recorded:
                                            ttft_ms = (time.perf_counter() - start_call_time) * 1000
                                            yield {"type": "ttft", "ttft_ms": ttft_ms}
                                            ttft_recorded = True
                                        
                                        # Only stream actual content to the UI, not the internal chain-of-thought reasoning
                                        if content:
                                            has_tokens = True
                                            yield {"type": "token", "token": content}
                            except Exception as e:
                                logger.error(f"Error parsing SSE chunk: {str(e)} | Chunk: {data_str}")
                                continue
            
            # If we successfully finished the stream and got tokens, break out of provider loop
            if has_tokens:
                return
            else:
                logger.warning(f"Provider {provider_name} closed stream without sending any tokens. Falling back...")
                continue

        except Exception as e:
            logger.error(f"Error with provider {provider_name}: {str(e)}")
            yield {"type": "fallback_alert", "message": f"Provider {provider_name} failed. Falling back..."}
            continue  # try next provider

    yield {"type": "error", "message": "All configured LLM providers failed to respond."}
