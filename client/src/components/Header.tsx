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
      <h1 style={{ fontSize: '2.5rem', fontWeight: 700, marginBottom: '8px' }}>
        Low-Latency <span className="gradient-text">Web RAG</span>
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: '600px', margin: '0 auto' }}>
        A low-latency Retrieval-Augmented Generation pipeline query-scoring Google/web documents with Cohere and streaming answers in real-time.
      </p>
    </header>
  );
};
