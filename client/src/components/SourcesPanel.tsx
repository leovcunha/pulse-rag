import React from 'react';
import { QueryStatus, SearchSource } from '../hooks/useRagQuery';
import { SourceCard } from './SourceCard';

/**
 * Props for the SourcesPanel component.
 */
export interface SourcesPanelProps {
  /** Current status of the RAG pipeline */
  status: QueryStatus;
  /** List of fetched search sources */
  sources: SearchSource[];
  /** Highlighted index representing the currently hovered source (1-based index) */
  highlightedIndex: number | null;
  /** Callback to set or clear the hovered source index */
  setHighlightedIndex: (idx: number | null) => void;
}

/**
 * SourcesPanel component displays the list of supporting context sources.
 * Maps individual items to a SourceCard component and manages their hovered states.
 * 
 * @param {SourcesPanelProps} props The props for the component.
 * @returns {React.ReactElement} The rendered sources panel list.
 */
export const SourcesPanel: React.FC<SourcesPanelProps> = ({
  status,
  sources,
  highlightedIndex,
  setHighlightedIndex,
}) => {
  return (
    <div className="glass-panel sources-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
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
  );
};
