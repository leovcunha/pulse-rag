import { useState, useCallback } from 'react';
import { API_URL } from '../config';

export interface SearchSource {
  title: string;
  url: string;
  content: string;
  score: number;
}

export interface LatencyMetrics {
  search_ms: number;
  rerank_ms: number;
  prompt_ms: number;
  llm_ttft_ms: number;
  total_ms: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export type QueryStatus = 'idle' | 'routing' | 'expanding' | 'searching' | 'reranking' | 'generating' | 'completed' | 'error';

/**
 * Custom React hook that orchestrates querying the backend RAG pipeline.
 * Manages request lifecycle state, Server-Sent Events parsing, and capped chat history.
 * 
 * @returns {object} State values and the runQuery execution function.
 */
export const useRagQuery = () => {
  const [status, setStatus] = useState<QueryStatus>('idle');
  const [answer, setAnswer] = useState<string>('');
  const [sources, setSources] = useState<SearchSource[]>([]);
  const [provider, setProvider] = useState<string>('');
  const [ttft, setTtft] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<LatencyMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fallbackAlert, setFallbackAlert] = useState<string | null>(null);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [transformedQuery, setTransformedQuery] = useState<string | null>(null);

  /**
   * Triggers the backend RAG pipeline, streams tokens/metrics via SSE, 
   * and tracks conversation history.
   * 
   * @param {string} query The user raw query input.
   */
  const runQuery = useCallback(async (query: string) => {
    // Reset state for new query
    setStatus('routing');
    setAnswer('');
    setSources([]);
    setProvider('');
    setTtft(null);
    setMetrics(null);
    setError(null);
    setFallbackAlert(null);
    setTransformedQuery(null);

    let answerAccumulator = '';

    try {
      // Send only the last 5 turns (10 messages) to avoid token context bloat and control latency
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          query,
          history: history.slice(-10)
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) {
        throw new Error('ReadableStream not supported on this browser.');
      }

      let buffer = '';
      let currentEvent = 'message';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep the last partial line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith('event: ')) {
            currentEvent = trimmed.slice(7).trim();
          } else if (trimmed.startsWith('data: ')) {
            const dataStr = trimmed.slice(5).trim();
            try {
              const parsed = JSON.parse(dataStr);
              
              switch (currentEvent) {
                case 'status':
                  setStatus(parsed.status);
                  if (parsed.transformed_query) {
                    setTransformedQuery(parsed.transformed_query);
                  }
                  break;
                case 'sources':
                  setSources(parsed.sources || []);
                  break;
                case 'provider':
                  setProvider(parsed.provider || '');
                  break;
                case 'ttft':
                  setTtft(parsed.ttft_ms);
                  break;
                case 'token':
                  const tok = parsed.token || '';
                  answerAccumulator += tok;
                  setAnswer((prev) => prev + tok);
                  break;
                case 'fallback_alert':
                  setFallbackAlert(parsed.message || 'LLM error. Falling back...');
                  break;
                case 'metrics':
                  setMetrics(parsed);
                  break;
                case 'error':
                  setError(parsed.message || 'An error occurred during generation.');
                  setStatus('error');
                  break;
                default:
                  break;
              }
            } catch (err) {
              console.error('Error parsing SSE data chunk:', err, dataStr);
            }
          }
        }
      }
      
      setStatus('completed');
      setHistory((prev) => [
        ...prev,
        { role: 'user', content: query },
        { role: 'assistant', content: answerAccumulator }
      ]);
    } catch (err: any) {
      console.error('Query execution failed:', err);
      setError(err?.message || 'Failed to connect to RAG server.');
      setStatus('error');
    }
  }, [history]);

  return {
    status,
    answer,
    sources,
    provider,
    ttft,
    metrics,
    error,
    fallbackAlert,
    transformedQuery,
    runQuery,
  };
};

export default useRagQuery;
