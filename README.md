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
|      - Drops noise, selects top 5     |
+---------------------------------------+
```

## System Mechanics

### Why is this a RAG System?
This application implements a **Retrieval-Augmented Generation (RAG)** pipeline using live web search:
1. **Retrieval**: When a query is submitted, the system queries the live web using the Tavily Search API. This makes it a **Web-Scale RAG** or **Search-RAG** system, drawing on current, real-time internet data instead of a static, pre-compiled vector index.
2. **Augmentation**: The retrieved search summaries are cross-evaluated, ranked, and the top 5 most relevant documents are formatted into a prompt context template.
3. **Generation**: The compiled prompt is sent to the LLM (Groq/OpenRouter), which synthesizes a response using *only* the provided context and attaches bracketed citation links (e.g., `[1]`, `[2]`) pointing to the sources in the sidebar.

### How does it run in under 2 seconds?
Achieving sub-2-second end-to-end execution requires optimizations at every pipeline stage:
- **Asynchronous Pipeline**: The FastAPI gateway is fully asynchronous (`httpx.AsyncClient` and `async/await`), preventing blocked threads while waiting for external API network responses.
- **Fast Web Search**: Configured with Tavily's `"ultra-fast"` search depth and limited to 10 sources, cutting web retrieval time to ~650ms.
- **Efficient Filtering**: Cohere Rerank acts as a semantic filter, selecting the top 5 relevant documents so we do not feed noise or overly large contexts to the LLM, keeping reranking under ~250ms.
- **High-Throughput Inference (Groq)**: The system defaults to Groq (`llama-3.1-8b-instant`), which leverages LPU hardware to achieve extremely low Time-to-First-Token (TTFT) (~200ms) and >200 tokens/second throughput.
- **SSE Streaming**: Rather than waiting for the entire answer to compile on the server, tokens are streamed to the React client via Server-Sent Events (SSE) as they are generated. The user sees the first characters rendering in **~700ms - 800ms**.

## Latency Budget Breakdown (Target: < 2.0s)

To guarantee a sub-2-second response, every component must fit into a strict time budget:

| Component | Target Latency | Description |
|---|---|---|
| **Search API** | 350ms | Async fetch and clean from Tavily/Exa |
| **Reranking Engine** | 150ms | Cohere cross-encoder relevance scoring |
| **Prompt Construction** | 5ms | In-memory Python string manipulation |
| **LLM Time-to-First-Token (TTFT)** | 200ms | Groq inference start time |
| **Initial Client Visual** | **~705ms** | User sees the answer starting to stream |

### Why the 1.8s/2.0s Target (Latency Buffer)
In high-performance API design, we maintain a distinction between the **Internal SLA Target** and the **User-Perceived SLA Limit** (2.0s):
- **Transit & Render Overhead**: Setting an internal budget of **1.8s** (scaled to **2.0s** for larger payloads) leaves a safety margin for network transit (DNS, TCP, TLS setup), client-side browser JSON parsing, and React rendering time.
- **Streaming Experience**: Because we use Server-Sent Events (SSE) to stream response tokens, the user starts seeing results within ~700ms (TTFT), making the overall perceived speed instantaneous, even if the final completion token finishes closer to 2.0s.

---

## Core Component Specifications

### 1. Async Ingestion Layer (FastAPI)
* **Role**: Handles incoming user requests and orchestrates the pipeline without blocking.
* **Key Design Pattern**: Uses Python’s `asyncio.gather()` to fetch data and `StreamingResponse` to stream tokens back to the client via Server-Sent Events (SSE).

### 2. Search & Clean Layer (Tavily / Exa)
* **Role**: Executes web search, bypasses anti-bot measures, and returns clean markdown/text content.
* **Optimization**: Configured to return a maximum of 10 results utilizing Tavily's `"ultra-fast"` search depth to minimize fetch time. This retrieves clean summaries of matching web pages, cutting retrieval latency down to ~650ms and speeding up downstream reranking.

### 3. Relevance Filter (Cohere Rerank)
* **Role**: Cross-encoder relevance filtering to clean out web clutter (navigation elements, cookie policies, etc.).
* **Optimization**: Drop any results with a relevance score below `0.6` and pass exactly the top 5 highest-scoring snippets to the LLM.

### 4. Dual-Provider LLM Engine (Groq + OpenRouter Fallback)
* **Role**: Generates the final answer with inline citations.
* **Resiliency**: Defaults to Groq (`llama-3.1-8b-instant` or similar) for high speed (>200 tokens/sec). If Groq returns a rate limit (`429`) or server error (`503`), the system instantly falls back to OpenRouter's free tier.

---

## System Sequence Flow

1. **Query Input**: The user submits a query (e.g., *"What happened in the OpenAI dev day yesterday?"*).
2. **Parallel Fetch**: FastAPI triggers the async search. Tavily fetches live web data.
3. **Compression & Rerank**: Cohere filters raw search data down to the 5 most relevant paragraphs.
4. **Prompt Assembly**: The system builds a structured prompt with strict constraints:
   > Answer only using the provided context. Append `[1]`, `[2]` to claims based on the source index. If the sources do not contain the answer, say you do not know.
5. **Streaming Response**: Groq processes the prompt, and the response is streamed to the user interface via SSE.
