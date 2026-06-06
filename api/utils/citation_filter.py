"""
Citation deduplication filter for streamed LLM output.

Small/fast LLMs tend to produce noisy, repetitive inline citations
(e.g., "A [1, 2], B [1, 2], and C [1, 2]." instead of "A, B, and C [1][2].").
This module provides a sentence-level buffer that collects citations,
deduplicates them, and emits a single consolidated citation set at the
end of each sentence.
"""

import re
from typing import List, Tuple

# Matches citation groups like [1], [2, 3], [1, 2, 3]
_CITATION_RE = re.compile(r"\s*\[[\d\s,]+\]")


def deduplicate_sentence_citations(sentence: str) -> str:
    """
    Given a sentence string, strips all inline citations, collects the
    unique indices, and appends a single consolidated citation block at the end.

    Args:
        sentence: A single sentence possibly containing multiple inline citations.

    Returns:
        The sentence with citations consolidated at the end.
    """
    indices: list[int] = []

    for match in _CITATION_RE.finditer(sentence):
        bracket_text = match.group()
        nums = re.findall(r"\d+", bracket_text)
        for n in nums:
            idx = int(n)
            if idx not in indices:
                indices.append(idx)

    # Capture original leading and trailing whitespace (including newlines)
    leading_ws = sentence[:len(sentence) - len(sentence.lstrip())]
    trailing_ws = sentence[len(sentence.rstrip()):] if len(sentence.rstrip()) > 0 else ""
    # Remove all citation brackets from the text
    cleaned_body = _CITATION_RE.sub("", sentence).strip()
    if not cleaned_body:
        return sentence
    if not indices:
        return leading_ws + cleaned_body + trailing_ws
    # Build consolidated citation: [1][2][3]
    citation_str = "".join(f"[{i}]" for i in sorted(indices))
    # If sentence body ends with punctuation, insert citation before it
    if cleaned_body[-1] in ".!?":
        body_with_citation = cleaned_body[:-1] + " " + citation_str + cleaned_body[-1]
    else:
        body_with_citation = cleaned_body + " " + citation_str
    # Return with the original leading and trailing whitespace restored
    return leading_ws + body_with_citation + trailing_ws


def filter_citations(text: str) -> str:
    """
    Processes a full text block by splitting it into sentences,
    deduplicating citations within each sentence, and reassembling.

    Args:
        text: The full LLM-generated answer text.

    Returns:
        The text with per-sentence citation deduplication applied.
    """
    if not text:
        return text

    # Split on sentence-ending punctuation while keeping the delimiter
    # This handles ". ", "! ", "? ", and end-of-string
    parts = re.split(r"((?<=[.!?])\s+)", text)

    result_parts: List[str] = []
    for part in parts:
        if not part.strip():
            result_parts.append(part)
            continue

        # Only process parts that actually contain citations
        if _CITATION_RE.search(part):
            result_parts.append(deduplicate_sentence_citations(part))
        else:
            result_parts.append(part)

    return " ".join(result_parts)
