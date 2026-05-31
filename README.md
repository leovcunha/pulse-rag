# Sub-2-Second Web-Scale RAG System

This document outlines the architecture, data flow, and latency budget for the Sub-2-Second Web-Scale RAG System.

```
                  +---------------------------------------+
                  |           User Browser (UI)           |
                  +---------------------------------------+
                    ^                                   |
     [Server-Sent   |                                   | [HTTP POST]
      Events / SSE] |                                   v
                  +---------------------------------------+
                  |         FastAPI Gateway / App         |
                  +---------------------------------------+
                    |                                   |
          (Step 1)  | [Async Fetch]           (Step 4)  | [Stream Context]
                    v                                   v
+---------------------------------------+   +---------------------------------------+
|   Web Search API (Tavily / Exa)       |   |      LLM Inference Engine             |
|   - Fetches live web results           |   |      - Primary: Groq (Ultra-Fast)     |
|   - Strips HTML to clean Markdown     |   |      - Fallback: OpenRouter (Free)    |
+---------------------------------------+   +---------------------------------------+
                    |                                   ^
           [Raw Docs| & Snippets]                       | [Top 3 Ranked Docs]
                    v                                   |
+---------------------------------------+               |
|      Cohere Rerank API (Step 2)       |---------------+ (Step 3: Prompt Synthesis)
|      - Cross-encoder relevancy scoring|
|      - Drops noise, selects top 3     |
+---------------------------------------+
```

## Latency Budget Breakdown (Target: < 1.8s)

To guarantee a sub-2-second response, every component must fit into a strict time budget:

| Component | Target Latency | Description |
|---|---|---|
| **Search API** | 350ms | Async fetch and clean from Tavily/Exa |
| **Reranking Engine** | 150ms | Cohere cross-encoder relevance scoring |
| **Prompt Construction** | 5ms | In-memory Python string manipulation |
| **LLM Time-to-First-Token (TTFT)** | 200ms | Groq inference start time |
| **Initial Client Visual** | **~705ms** | User sees the answer starting to stream |

---

## Core Component Specifications

### 1. Async Ingestion Layer (FastAPI)
* **Role**: Handles incoming user requests and orchestrates the pipeline without blocking.
* **Key Design Pattern**: Uses Python’s `asyncio.gather()` to fetch data and `StreamingResponse` to stream tokens back to the client via Server-Sent Events (SSE).

### 2. Search & Clean Layer (Tavily / Exa)
* **Role**: Executes web search, bypasses anti-bot measures, and returns clean markdown/text content.
* **Optimization**: Configured to return a maximum of 5–7 results to keep payload sizes small and processing times low.

### 3. Relevance Filter (Cohere Rerank)
* **Role**: Cross-encoder relevance filtering to clean out web clutter (navigation elements, cookie policies, etc.).
* **Optimization**: Drop any results with a relevance score below `0.6` and pass exactly the top 3 highest-scoring snippets to the LLM.

### 4. Dual-Provider LLM Engine (Groq + OpenRouter Fallback)
* **Role**: Generates the final answer with inline citations.
* **Resiliency**: Defaults to Groq (`llama-3.1-8b-instant` or similar) for high speed (>200 tokens/sec). If Groq returns a rate limit (`429`) or server error (`503`), the system instantly falls back to OpenRouter's free tier.

---

## System Sequence Flow

1. **Query Input**: The user submits a query (e.g., *"What happened in the OpenAI dev day yesterday?"*).
2. **Parallel Fetch**: FastAPI triggers the async search. Tavily fetches live web data.
3. **Compression & Rerank**: Cohere filters raw search data down to the 3 most relevant paragraphs.
4. **Prompt Assembly**: The system builds a structured prompt with strict constraints:
   > Answer only using the provided context. Append `[1]`, `[2]` to claims based on the source index. If the sources do not contain the answer, say you do not know.
5. **Streaming Response**: Groq processes the prompt, and the response is streamed to the user interface via SSE.
