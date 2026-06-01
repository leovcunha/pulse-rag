import React from 'react';
import { LatencyMetrics, QueryStatus } from '../hooks/useRagQuery';

interface LatencyDashboardProps {
  status: QueryStatus;
  metrics: LatencyMetrics | null;
  provider: string;
  ttft: number | null;
  fallbackAlert: string | null;
}

interface LatencyStep {
  name: string;
  key: keyof LatencyMetrics | 'llm_ttft_ms';
  target: number;
  description: string;
}

export const LatencyDashboard: React.FC<LatencyDashboardProps> = ({
  status,
  metrics,
  provider,
  ttft,
  fallbackAlert,
}) => {
  const actualTotal = metrics?.total_ms || 0;

  const steps: LatencyStep[] = [
    { name: 'Web Search (Tavily)', key: 'search_ms', target: 350, description: 'Querying and cleaning web results' },
    { name: 'Reranking (Cohere)', key: 'rerank_ms', target: 150, description: 'Filtering for top 5 relevant cards' },
    { name: 'Prompt Prep', key: 'prompt_ms', target: 5, description: 'In-memory template structuring' },
    { name: 'LLM Time-to-First-Token', key: 'llm_ttft_ms', target: 200, description: 'Provider start to initial token return' },
  ];

  // Helper to determine status color relative to target
  const getMetricColorClass = (actual: number, target: number) => {
    if (actual <= 0) return 'text-muted';
    if (actual <= target) return 'text-accent-success';
    if (actual <= target * 1.5) return 'text-accent-warning';
    return 'text-accent-error';
  };

  const getMetricStyle = (actual: number, target: number) => {
    const ratio = Math.min((actual / target) * 100, 100);
    if (actual <= target) return { width: `${ratio}%`, backgroundColor: '#10b981' };
    if (actual <= target * 1.5) return { width: `${ratio}%`, backgroundColor: '#f59e0b' };
    return { width: `${ratio}%`, backgroundColor: '#ef4444' };
  };

  const getStepProgressState = (stepName: string): 'idle' | 'running' | 'done' => {
    if (status === 'idle') return 'idle';
    if (status === 'error') return 'idle';
    
    if (stepName.includes('Search')) {
      if (status === 'searching') return 'running';
      if (['reranking', 'generating', 'completed'].includes(status)) return 'done';
    }
    if (stepName.includes('Reranking')) {
      if (status === 'reranking') return 'running';
      if (['generating', 'completed'].includes(status)) return 'done';
    }
    if (stepName.includes('Prompt')) {
      if (status === 'generating' && !ttft) return 'running';
      if (['generating', 'completed'].includes(status) && (metrics || ttft)) return 'done';
    }
    if (stepName.includes('First-Token')) {
      if (status === 'generating' && !ttft) return 'running';
      if (status === 'completed' || ttft) return 'done';
    }
    return 'idle';
  };

  const targetTotal = 1800; // 1.8 seconds SLA target (perceived latency to first token)

  return (
    <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Latency Diagnostics</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className={`status-dot ${status === 'completed' ? 'completed' : status === 'error' ? 'error' : status === 'idle' ? 'idle' : 'active'}`} />
          <span style={{ fontSize: '0.85rem', textTransform: 'capitalize', color: 'var(--text-secondary)' }}>{status}</span>
        </div>
      </div>

      {provider && (
        <div 
          className="glass-panel" 
          style={{ 
            padding: '12px 16px', 
            background: provider === 'groq' ? 'rgba(16, 185, 129, 0.05)' : 'rgba(168, 85, 247, 0.05)',
            borderColor: provider === 'groq' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(168, 85, 247, 0.2)',
            borderRadius: '10px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>LLM Provider:</span>
            <span 
              style={{ 
                fontSize: '0.9rem', 
                fontWeight: 600, 
                color: provider === 'groq' ? 'var(--accent-success)' : 'var(--accent-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}
            >
              {provider}
            </span>
          </div>
          {fallbackAlert && (
            <div style={{ fontSize: '0.75rem', color: 'var(--accent-warning)', marginTop: '6px', fontStyle: 'italic' }}>
              ⚠️ {fallbackAlert}
            </div>
          )}
        </div>
      )}

      {/* Latency Stages */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {steps.map((step) => {
          // Get actual value
          let actualVal = 0;
          if (metrics) {
            actualVal = metrics[step.key as keyof LatencyMetrics] || 0;
          } else if (step.key === 'llm_ttft_ms' && ttft) {
            actualVal = ttft;
          }
          
          const progressState = getStepProgressState(step.name);
          const colorClass = getMetricColorClass(actualVal, step.target);

          return (
            <div key={step.name} style={{ display: 'flex', flexDirection: 'column', gap: '6px', opacity: progressState === 'idle' && actualVal === 0 ? 0.4 : 1, transition: 'opacity 0.25s' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {progressState === 'running' && <span className="status-dot active" style={{ width: '6px', height: '6px' }} />}
                  <span style={{ fontWeight: 500, color: progressState === 'running' ? 'var(--accent-primary)' : 'var(--text-primary)' }}>{step.name}</span>
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                  {actualVal > 0 ? (
                    <span className={colorClass}>{actualVal.toFixed(0)}ms</span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)' }}>--</span>
                  )}
                  <span style={{ color: 'var(--text-muted)' }}> / {step.target}ms</span>
                </div>
              </div>

              {/* Progress bar container */}
              <div style={{ height: '4px', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '2px', overflow: 'hidden', position: 'relative' }}>
                {progressState === 'running' && (
                  <div className="shimmer-bg" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
                )}
                {actualVal > 0 && (
                  <div style={{ height: '100%', borderRadius: '2px', transition: 'width 0.4s ease-out', ...getMetricStyle(actualVal, step.target) }} />
                )}
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{step.description}</span>
            </div>
          );
        })}
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }} />

      {/* Total Latency Meter */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>Time-to-First-Token SLA</span>
          <div style={{ fontFamily: 'var(--font-mono)' }}>
            {actualTotal > 0 ? (
              <span 
                style={{ 
                  fontSize: '1.2rem', 
                  fontWeight: 700, 
                  color: actualTotal <= targetTotal ? 'var(--accent-success)' : actualTotal <= targetTotal * 1.3 ? 'var(--accent-warning)' : 'var(--accent-error)' 
                }}
              >
                {(actualTotal / 1000).toFixed(2)}s
              </span>
            ) : (
              <span style={{ color: 'var(--text-muted)', fontSize: '1rem' }}>--</span>
            )}
            <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}> / {(targetTotal / 1000).toFixed(1)}s</span>
          </div>
        </div>

        <div style={{ height: '6px', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '3px', overflow: 'hidden' }}>
          {actualTotal > 0 && (
            <div 
              style={{ 
                height: '100%', 
                borderRadius: '3px', 
                transition: 'width 0.5s cubic-bezier(0.1, 0.8, 0.2, 1)', 
                ...getMetricStyle(actualTotal, targetTotal) 
              }} 
            />
          )}
        </div>
        
        {actualTotal > 0 && (
          <span 
            style={{ 
              fontSize: '0.75rem', 
              textAlign: 'center', 
              color: actualTotal <= targetTotal ? 'var(--accent-success)' : 'var(--accent-warning)',
              marginTop: '4px'
            }}
          >
            {actualTotal <= targetTotal 
              ? '⚡ SLA Target met! Answer started streaming in under 1.8s.' 
              : '⚠️ SLA Target exceeded (likely due to search API or network load).'}
          </span>
        )}
      </div>
    </div>
  );
};
