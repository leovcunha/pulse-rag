import React from 'react';
import { QueryStatus } from '../hooks/useRagQuery';

/**
 * Props for the QueryForm component.
 */
export interface QueryFormProps {
  /** The current search query string */
  query: string;
  /** Callback to update the query string state in the parent container */
  setQuery: (query: string) => void;
  /** Current status of the RAG pipeline */
  status: QueryStatus;
  /** Callback when the form is submitted or a suggestion chip is clicked */
  onSubmit: (submittedQuery: string) => void;
}

/**
 * QueryForm component renders the search text input, search button,
 * and pre-populated suggestion chips when the application is idle.
 * 
 * @param {QueryFormProps} props The props for the component.
 * @returns {React.ReactElement} The rendered search form and chips.
 */
export const QueryForm: React.FC<QueryFormProps> = ({
  query,
  setQuery,
  status,
  onSubmit,
}) => {
  const suggestions = [
    "What was the outcome of SpaceX Starship Flight 4?",
    "Explain Apple's Vision Pro hand tracking latency",
    "Latest breakthroughs in high-temperature superconductors (2025/2026)",
    "What did Nvidia announce at their latest GTC keynotes?"
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || ['searching', 'reranking', 'generating'].includes(status)) return;
    onSubmit(query.trim());
  };

  const handleSuggestionClick = (suggestedQuery: string) => {
    setQuery(suggestedQuery);
    onSubmit(suggestedQuery);
  };

  const isProcessing = ['searching', 'reranking', 'generating'].includes(status);

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '12px' }}>
        <input
          type="text"
          className="input-glow"
          placeholder="Ask a question about current events or technical details..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={isProcessing}
          style={{ flex: 1, padding: '16px 20px', fontSize: '1.05rem' }}
          id="query-input"
        />
        <button
          type="submit"
          disabled={!query.trim() || isProcessing}
          style={{
            padding: '0 30px',
            fontSize: '1rem',
            fontWeight: 600,
            borderRadius: '12px',
            border: 'none',
            background: 'linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%)',
            color: 'var(--bg-main)',
            cursor: 'pointer',
            opacity: !query.trim() || isProcessing ? 0.6 : 1,
            transition: 'opacity 0.2s',
            boxShadow: '0 4px 14px rgba(56, 189, 248, 0.3)'
          }}
          id="submit-btn"
        >
          {isProcessing ? 'Processing...' : 'Search'}
        </button>
      </form>

      {/* Suggestion Chips */}
      {status === 'idle' && (
        <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Try asking:</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {suggestions.map((s, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSuggestionClick(s)}
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '20px',
                  padding: '6px 14px',
                  fontSize: '0.8rem',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                className="suggestion-chip"
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(56, 189, 248, 0.3)';
                  e.currentTarget.style.background = 'rgba(56, 189, 248, 0.03)';
                  e.currentTarget.style.color = 'var(--text-primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)';
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
                  e.currentTarget.style.color = 'var(--text-secondary)';
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
