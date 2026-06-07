import React, { useState } from 'react';
import { useRagQuery } from './hooks/useRagQuery';
import { Header } from './components/Header';
import { QueryForm } from './components/QueryForm';
import { AnswerPanel } from './components/AnswerPanel';
import { SourcesPanel } from './components/SourcesPanel';
import { LatencyDashboard } from './components/LatencyDashboard';
import './App.css';

/**
 * Main application entry point page-level component.
 * Orchestrates custom hook useRagQuery data-fetching flows and
 * layouts of the modular presentational sub-components.
 * 
 * @returns {React.ReactElement} The main layout of the application.
 */
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
    transformedQuery,
    runQuery,
  } = useRagQuery();

  // Highlight index tracks which citation source is hovered (1-based index)
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);

  return (
    <div className="app-container">
      {/* Header section */}
      <Header />

      {/* Input submission query form */}
      <QueryForm
        query={query}
        setQuery={setQuery}
        status={status}
        onSubmit={runQuery}
      />

      {/* Main Content Layout Grid */}
      {status !== 'idle' && (
        <div className="content-grid">
          {/* Main Column - Answer Stream */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <AnswerPanel
              status={status}
              answer={answer}
              error={error}
              highlightedIndex={highlightedIndex}
              setHighlightedIndex={setHighlightedIndex}
              transformedQuery={transformedQuery}
            />
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
            <SourcesPanel
              status={status}
              sources={sources}
              highlightedIndex={highlightedIndex}
              setHighlightedIndex={setHighlightedIndex}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
