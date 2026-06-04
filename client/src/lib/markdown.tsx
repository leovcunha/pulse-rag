import React from 'react';

/**
 * Parses and transforms raw citations in brackets (e.g. "[1]") into interactive, hoverable badges.
 *
 * @param text - The raw text segment containing potential citations.
 * @param baseKey - The base key to use for JSX elements key attributes.
 * @param highlightedIndex - The index of the currently highlighted citation source (1-based), or null.
 * @param setHighlightedIndex - Callback function to update the highlighted index state.
 * @returns An array of React nodes (text fragments and formatted badge spans).
 */
export const renderInlineCitations = (
  text: string,
  baseKey: string,
  highlightedIndex: number | null,
  setHighlightedIndex: (idx: number | null) => void
): React.ReactNode[] => {
  const regex = /\[([\d\s,]+)\]/g;
  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    const matchIndex = match.index;

    // Add normal text part preceding the citation
    if (matchIndex > lastIndex) {
      elements.push(text.substring(lastIndex, matchIndex));
    }

    const citationContent = match[1];
    const parts = citationContent.split(',').map(p => p.trim()).filter(Boolean);

    // Render group citation as [1, 2, 3] with individual interactive numbers
    elements.push(<span key={`cite-group-open-${baseKey}-${matchIndex}`}>[</span>);
    parts.forEach((part, partIdx) => {
      const indexNum = parseInt(part, 10);
      if (!isNaN(indexNum)) {
        elements.push(
          <span
            key={`cite-num-${baseKey}-${matchIndex}-${partIdx}`}
            className={`citation-link ${highlightedIndex === indexNum ? 'highlighted' : ''}`}
            onMouseEnter={() => setHighlightedIndex(indexNum)}
            onMouseLeave={() => setHighlightedIndex(null)}
            style={{ cursor: 'pointer' }}
          >
            {indexNum}
          </span>
        );
        if (partIdx < parts.length - 1) {
          elements.push(<span key={`cite-sep-${baseKey}-${matchIndex}-${partIdx}`}>, </span>);
        }
      } else {
        elements.push(<span key={`cite-non-num-${baseKey}-${matchIndex}-${partIdx}`}>{part}</span>);
      }
    });
    elements.push(<span key={`cite-group-close-${baseKey}-${matchIndex}`}>]</span>);

    lastIndex = regex.lastIndex;
  }

  // Add remaining trailing text
  if (lastIndex < text.length) {
    elements.push(text.substring(lastIndex));
  }

  return elements.length > 0 ? elements : [text];
};

/**
 * Parses and transforms double asterisks (e.g. "**bold**") inside a text segment into rich text.
 *
 * @param text - The raw text content.
 * @param baseKey - The base key to use for JSX elements key attributes.
 * @param highlightedIndex - The index of the currently highlighted citation source, or null.
 * @param setHighlightedIndex - Callback function to update the highlighted index state.
 * @returns An array of React nodes (text, citations, and bold elements).
 */
export const renderInlineRichText = (
  text: string,
  baseKey: string,
  highlightedIndex: number | null,
  setHighlightedIndex: (idx: number | null) => void
): React.ReactNode[] => {
  const boldParts = text.split('**');

  return boldParts.map((part, index) => {
    const isBold = index % 2 === 1;
    const partKey = `${baseKey}-bold-${index}`;

    const citationContent = renderInlineCitations(part, partKey, highlightedIndex, setHighlightedIndex);

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

/**
 * Renders streamed text and transforms markdown lists, headers, rules, and citations.
 *
 * @param text - The complete raw markdown text content.
 * @param highlightedIndex - The index of the currently highlighted citation source, or null.
 * @param setHighlightedIndex - Callback function to update the highlighted index state.
 * @returns An array of React nodes formatted with appropriate paragraph, list, and heading tags.
 */
export const renderTextWithCitations = (
  text: string,
  highlightedIndex: number | null,
  setHighlightedIndex: (idx: number | null) => void
): React.ReactNode[] | null => {
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
        {renderInlineRichText(content, key, highlightedIndex, setHighlightedIndex)}
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
          {renderInlineRichText(headerContent, `header-content-${i}`, highlightedIndex, setHighlightedIndex)}
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
            {renderInlineRichText(listContent, `list-content-${i}`, highlightedIndex, setHighlightedIndex)}
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
