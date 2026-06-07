import React from 'react';

/**
 * Header component that displays the application title, styled main heading,
 * and a description of the Sub-2-Second Web RAG pipeline.
 * 
 * @returns {React.ReactElement} The rendered header component.
 */
export const Header: React.FC = () => {
  return (
    <header style={{ textAlign: 'center', marginBottom: '10px' }}>
      <h1 className="header-title">
        Low-Latency <span className="gradient-text">Web RAG</span>
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', maxWidth: '600px', margin: '0 auto', lineHeight: '1.5' }}>
        Search the live web and get real-time, AI-synthesized answers with cited sources.
      </p>
    </header>
  );
};
