import React, { useState } from 'react';
import { SearchSource } from '../hooks/useRagQuery';

interface SourceCardProps {
  source: SearchSource;
  index: number; // 1-based index
  isHighlighted: boolean;
  onHover: (hovered: boolean) => void;
}

export const SourceCard: React.FC<SourceCardProps> = ({
  source,
  index,
  isHighlighted,
  onHover,
}) => {
  const [expanded, setExpanded] = useState(false);

  // Extract domain name from URL
  const getDomain = (url: string) => {
    try {
      const hostname = new URL(url).hostname;
      return hostname.startsWith('www.') ? hostname.substring(4) : hostname;
    } catch {
      return url;
    }
  };

  const scorePercentage = Math.round(source.score * 100);
  const isCohereScore = source.score <= 1.0; // Cohere Rerank returns [0..1], Tavily can be raw search score

  return (
    <div
      className="glass-panel"
      style={{
        padding: '16px',
        borderLeft: isHighlighted 
          ? '4px solid var(--accent-primary)' 
          : expanded 
            ? '4px solid rgba(255, 255, 255, 0.3)' 
            : '1px solid var(--border-glow)',
        background: isHighlighted 
          ? 'rgba(56, 189, 248, 0.08)' 
          : 'var(--bg-card)',
        transform: isHighlighted ? 'translateY(-2px)' : 'none',
        boxShadow: isHighlighted ? '0 8px 24px rgba(56, 189, 248, 0.1)' : 'none',
        transition: 'all 0.2s ease-in-out',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
          {/* Index Badge */}
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justify-content: 'center',
              width: '24px',
              height: '24px',
              borderRadius: '6px',
              background: isHighlighted ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.08)',
              color: isHighlighted ? 'var(--bg-main)' : 'var(--text-primary)',
              fontWeight: 600,
              fontSize: '0.85rem',
              flexShrink: 0
            }}
          >
            {index}
          </span>
          <div>
            <h4 
              style={{ 
                fontSize: '0.9rem', 
                fontWeight: 600, 
                color: isHighlighted ? 'var(--accent-primary)' : 'var(--text-primary)',
                lineHeight: '1.3',
                marginBottom: '2px'
              }}
            >
              {source.title || 'Untitled Source'}
            </h4>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()} // don't toggle expand when clicking link
              style={{
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
                textDecoration: 'none',
                wordBreak: 'break-all'
              }}
            >
              {getDomain(source.url)} ↗
            </a>
          </div>
        </div>

        {/* Score Badge */}
        {source.score > 0 && (
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              color: scorePercentage >= 60 ? 'var(--accent-success)' : 'var(--accent-warning)',
              background: scorePercentage >= 60 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
              padding: '2px 8px',
              borderRadius: '20px',
              border: `1px solid ${scorePercentage >= 60 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)'}`,
              whiteSpace: 'nowrap',
              flexShrink: 0
            }}
            title={isCohereScore ? 'Cohere Rerank Relevance Score' : 'Tavily Search Score'}
          >
            {isCohereScore ? `Rerank: ${scorePercentage}%` : `Score: ${source.score.toFixed(2)}`}
          </span>
        )}
      </div>

      {/* Snippet Panel */}
      <div 
        style={{ 
          fontSize: '0.8rem', 
          color: 'var(--text-secondary)',
          lineHeight: '1.5',
          maxHeight: expanded ? '200px' : '36px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: expanded ? 'block' : '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          transition: 'all 0.3s ease-in-out',
          fontStyle: expanded ? 'normal' : 'italic',
          paddingTop: '4px'
        }}
      >
        {source.content || 'No snippet available.'}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
        {expanded ? 'Click to collapse' : 'Click to expand snippet'}
      </div>
    </div>
  );
};
