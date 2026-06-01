import React, { useState } from 'react';
import { useRagQuery } from './hooks/useRagQuery';
import { LatencyDashboard } from './components/LatencyDashboard';
import { SourceCard } from './components/SourceCard';
import './App.css';

export const App: React.FC = () => {
  const [query, setQuery] = useState('');
  const {
    status,
    answer,
    sources,
    provider,
    ttft,
    metrics,
    error,
    fallbackAlert,
    runQuery,
  } = useRagQuery();

  // Highlight index tracks which citation source is hovered (1-based index)
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || ['searching', 'reranking', 'generating'].includes(status)) return;
    runQuery(query);
  };

  const handleSuggestionClick = (suggestedQuery: string) => {
    setQuery(suggestedQuery);
    runQuery(suggestedQuery);
  };

  // Helper to parse citations like [1], [2] inside text segments
  const renderInlineCitations = (text: string, baseKey: string) => {
    const regex = /\[(\d+)\]/g;
    const elements: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      const matchIndex = match.index;
      
      // Add normal text part
      if (matchIndex > lastIndex) {
        elements.push(text.substring(lastIndex, matchIndex));
      }

      const indexNum = parseInt(match[1], 10);
      
      // Add interactive citation link
      elements.push(
        <span
          key={`cite-${baseKey}-${matchIndex}`}
          className={`citation-link ${highlightedIndex === indexNum ? 'highlighted' : ''}`}
          onMouseEnter={() => setHighlightedIndex(indexNum)}
          onMouseLeave={() => setHighlightedIndex(null)}
        >
          {indexNum}
        </span>
      );

      lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
      elements.push(text.substring(lastIndex));
    }

    return elements.length > 0 ? elements : [text];
  };

  // Helper to parse bold markdown ** inside text segments
  const renderInlineRichText = (text: string, baseKey: string) => {
    const boldParts = text.split('**');
    
    return boldParts.map((part, index) => {
      const isBold = index % 2 === 1;
      const partKey = `${baseKey}-bold-${index}`;
      
      const citationContent = renderInlineCitations(part, partKey);
      
      if (isBold) {
        return (
          <strong key={partKey} style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {citationContent}
          </strong>
        );
      }
      return <span key={partKey}>{citationContent}</span>;
    });
  };

  // Renders streamed text and transforms markdown lists/headers/rules/citations
  const renderTextWithCitations = (text: string) => {
    if (!text) return null;

    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let currentParagraphLines: string[] = [];

    const flushParagraph = (key: string) => {
      if (currentParagraphLines.length === 0) return null;
      const content = currentParagraphLines.join(' ');
      currentParagraphLines = [];
      return (
        <p key={key} style={{ marginBottom: '16px', lineHeight: '1.6', fontSize: '1rem', color: 'var(--text-primary)' }}>
          {renderInlineRichText(content, key)}
        </p>
      );
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) {
        const para = flushParagraph(`p-${i}`);
        if (para) elements.push(para);
        continue;
      }

      // Check for horizontal rule
      if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
        const para = flushParagraph(`p-prev-hr-${i}`);
        if (para) elements.push(para);
        elements.push(
          <hr
            key={`hr-${i}`}
            style={{
              border: 'none',
              borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
              margin: '20px 0'
            }}
          />
        );
        continue;
      }

      // Check for headers
      const headerMatch = line.match(/^(\s*)(#{1,6})\s+(.*)$/);
      if (headerMatch) {
        const para = flushParagraph(`p-prev-header-${i}`);
        if (para) elements.push(para);

        const level = headerMatch[2].length;
        const headerContent = headerMatch[3];
        const fontSize = level === 1 ? '1.8rem' : level === 2 ? '1.5rem' : level === 3 ? '1.25rem' : '1.1rem';
        
        elements.push(
          <div
            key={`header-${i}`}
            style={{
              fontSize,
              fontWeight: 600,
              marginTop: '20px',
              marginBottom: '10px',
              color: 'var(--text-primary)',
              lineHeight: '1.4'
            }}
          >
            {renderInlineRichText(headerContent, `header-content-${i}`)}
          </div>
        );
        continue;
      }

      // Check for bullet points (*, -, +)
      const bulletMatch = line.match(/^(\s*)[*+-]\s+(.*)$/);
      // Check for numbered lists (e.g. 1., 2.)
      const numberMatch = line.match(/^(\s*)(\d+)\.\s+(.*)$/);

      if (bulletMatch || numberMatch) {
        const para = flushParagraph(`p-prev-list-${i}`);
        if (para) elements.push(para);

        const listContent = bulletMatch ? bulletMatch[2] : numberMatch![3];
        const isNumbered = !!numberMatch;
        const prefix = isNumbered ? `${numberMatch![2]}.` : '•';

        elements.push(
          <div
            key={`list-${i}`}
            style={{
              display: 'flex',
              gap: '12px',
              paddingLeft: '20px',
              marginBottom: '8px',
              lineHeight: '1.6',
              fontSize: '1rem',
              color: 'var(--text-primary)',
              alignItems: 'flex-start'
            }}
          >
            <span style={{ color: 'var(--accent-primary)', fontWeight: 'bold', minWidth: isNumbered ? '20px' : 'auto', textAlign: isNumbered ? 'right' : 'center' }}>
              {prefix}
            </span>
            <span style={{ flex: 1 }}>
              {renderInlineRichText(listContent, `list-content-${i}`)}
            </span>
          </div>
        );
      } else {
        currentParagraphLines.push(trimmed);
      }
    }

    const lastPara = flushParagraph(`p-final`);
    if (lastPara) elements.push(lastPara);

    return elements;
  };

  const suggestions = [
    "What was the outcome of SpaceX Starship Flight 4?",
    "Explain Apple's Vision Pro hand tracking latency",
    "Latest breakthroughs in high-temperature superconductors (2025/2026)",
    "What did Nvidia announce at their latest GTC keynotes?"
  ];

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 20px', minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: '30px' }}>
      {/* Header */}
      <header style={{ textAlign: 'center', marginBottom: '10px' }}>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 700, marginBottom: '8px' }}>
          Sub-2-Second <span className="gradient-text">Web RAG</span>
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: '600px', margin: '0 auto' }}>
          An ultra-low latency Retrieval-Augmented Generation pipeline query-scoring Google/web documents with Cohere and streaming answers in real-time.
        </p>
      </header>

      {/* Main Search Input Form */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '12px' }}>
          <input
            type="text"
            className="input-glow"
            placeholder="Ask a question about current events or technical details..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={['searching', 'reranking', 'generating'].includes(status)}
            style={{ flex: 1, padding: '16px 20px', fontSize: '1.05rem' }}
            id="query-input"
          />
          <button
            type="submit"
            disabled={!query.trim() || ['searching', 'reranking', 'generating'].includes(status)}
            style={{
              padding: '0 30px',
              fontSize: '1rem',
              fontWeight: 600,
              borderRadius: '12px',
              border: 'none',
              background: 'linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%)',
              color: 'var(--bg-main)',
              cursor: 'pointer',
              opacity: !query.trim() || ['searching', 'reranking', 'generating'].includes(status) ? 0.6 : 1,
              transition: 'opacity 0.2s',
              boxShadow: '0 4px 14px rgba(56, 189, 248, 0.3)'
            }}
            id="submit-btn"
          >
            {['searching', 'reranking', 'generating'].includes(status) ? 'Processing...' : 'Search'}
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

      {/* Main Content Layout Grid */}
      {status !== 'idle' && (
        <div className="content-grid">
          {/* Main Column - Answer Stream */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="glass-panel" style={{ padding: '30px', minHeight: '300px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid rgba(255, 255, 255, 0.06)', paddingBottom: '12px' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Generative Answer</h2>
                {status !== 'completed' && status !== 'error' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    <span className="status-dot active" />
                    <span>{status === 'searching' ? 'Web Searching...' : status === 'reranking' ? 'Cohere Reranking...' : 'Generating...'}</span>
                  </div>
                )}
              </div>

              {error && (
                <div 
                  style={{ 
                    padding: '16px', 
                    borderRadius: '8px', 
                    background: 'rgba(239, 68, 68, 0.08)', 
                    border: '1px solid rgba(239, 68, 68, 0.2)', 
                    color: 'var(--accent-error)',
                    fontSize: '0.9rem',
                    marginBottom: '16px'
                  }}
                >
                  ❌ {error}
                </div>
              )}

              {/* Shimmer states for initial pipeline stages */}
              {(status === 'searching' || status === 'reranking') && !answer && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1 }}>
                  <div className="shimmer-bg" style={{ height: '18px', width: '80%', borderRadius: '4px' }} />
                  <div className="shimmer-bg" style={{ height: '18px', width: '95%', borderRadius: '4px' }} />
                  <div className="shimmer-bg" style={{ height: '18px', width: '60%', borderRadius: '4px' }} />
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    {status === 'searching' 
                      ? 'Fetching documents from Tavily...' 
                      : 'Evaluating relevance with Cohere Rerank...'}
                  </div>
                </div>
              )}

              {/* Streamed Answer Area */}
              {answer && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <div className="answer-markdown" style={{ flex: 1 }}>
                    {renderTextWithCitations(answer)}
                  </div>
                  {status !== 'completed' && (
                    <span 
                      style={{ 
                        display: 'inline-block', 
                        width: '8px', 
                        height: '14px', 
                        background: 'var(--accent-primary)', 
                        animation: 'pulse-glow 1s infinite', 
                        marginLeft: '4px',
                        verticalAlign: 'middle'
                      }} 
                    />
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Diagnostics & Sources Side Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '30px', alignSelf: 'start' }} className="side-column">
            {/* Latency Diagnostic Metrics */}
            <LatencyDashboard
              status={status}
              metrics={metrics}
              provider={provider}
              ttft={ttft}
              fallbackAlert={fallbackAlert}
            />

            {/* Cited Context Sources Panel */}
            <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Supporting Sources</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{sources.length} total</span>
              </div>

              {sources.length === 0 && (
                <div style={{ padding: '30px 10px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  {status === 'searching' ? 'Web search in progress...' : 'No references cited.'}
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '450px', overflowY: 'auto', paddingRight: '4px' }}>
                {sources.map((src, index) => (
                  <SourceCard
                    key={index}
                    source={src}
                    index={index + 1}
                    isHighlighted={highlightedIndex === index + 1}
                    onHover={(hovered) => setHighlightedIndex(hovered ? index + 1 : null)}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
