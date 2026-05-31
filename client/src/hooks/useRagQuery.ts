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

export type QueryStatus = 'idle' | 'searching' | 'reranking' | 'generating' | 'completed' | 'error';

export const useRagQuery = () => {
  const [status, setStatus] = useState<QueryStatus>('idle');
  const [answer, setAnswer] = useState<string>('');
  const [sources, setSources] = useState<SearchSource[]>([]);
  const [provider, setProvider] = useState<string>('');
  const [ttft, setTtft] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<LatencyMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fallbackAlert, setFallbackAlert] = useState<string | null>(null);

  const runQuery = useCallback(async (query: string) => {
    // Reset state for new query
    setStatus('searching');
    setAnswer('');
    setSources([]);
    setProvider('');
    setTtft(null);
    setMetrics(null);
    setError(null);
    setFallbackAlert(null);

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
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
                  setAnswer((prev) => prev + (parsed.token || ''));
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
    } catch (err: any) {
      console.error('Query execution failed:', err);
      setError(err?.message || 'Failed to connect to RAG server.');
      setStatus('error');
    }
  }, []);

  return {
    status,
    answer,
    sources,
    provider,
    ttft,
    metrics,
    error,
    fallbackAlert,
    runQuery,
  };
};
