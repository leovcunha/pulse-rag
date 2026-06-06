"""Tests for the citation deduplication filter."""

import pytest
from api.utils.citation_filter import deduplicate_sentence_citations, filter_citations


class TestDeduplicateSentenceCitations:
    """Tests for single-sentence citation deduplication."""

    def test_no_citations_returns_unchanged(self):
        text = "This is a plain sentence without citations."
        assert deduplicate_sentence_citations(text) == text

    def test_single_citation_preserved(self):
        result = deduplicate_sentence_citations("Machine learning improves grid efficiency [1].")
        assert result == "Machine learning improves grid efficiency [1]."

    def test_duplicate_citations_consolidated(self):
        text = "Grid Optimization [1, 2, 3], Predictive Maintenance [1, 2, 3], and Energy Efficiency [1, 2, 3]."
        result = deduplicate_sentence_citations(text)
        assert result == "Grid Optimization, Predictive Maintenance, and Energy Efficiency [1][2][3]."

    def test_partial_overlap_citations_merged(self):
        text = "Machine Learning [1, 2] and Deep Learning [2, 3] are used."
        result = deduplicate_sentence_citations(text)
        assert result == "Machine Learning and Deep Learning are used [1][2][3]."

    def test_already_clean_sentence_unchanged(self):
        text = "AI improves grids through optimization and predictive maintenance [1][2]."
        result = deduplicate_sentence_citations(text)
        assert result == "AI improves grids through optimization and predictive maintenance [1][2]."

    def test_empty_string_returns_empty(self):
        assert deduplicate_sentence_citations("") == ""

    def test_no_punctuation_at_end(self):
        text = "Smart Grids [1, 2] are a key area [2, 3]"
        result = deduplicate_sentence_citations(text)
        assert result == "Smart Grids are a key area [1][2][3]"


class TestFilterCitations:
    """Tests for multi-sentence full-text citation filtering."""

    def test_empty_text(self):
        assert filter_citations("") == ""
        assert filter_citations(None) is None

    def test_single_sentence_dedup(self):
        text = "A [1] and B [1] are used."
        result = filter_citations(text)
        assert result == "A and B are used [1]."

    def test_multi_sentence_dedup(self):
        text = "First topic [1, 2] is important [1]. Second topic [2, 3] is also relevant [3]."
        result = filter_citations(text)
        # Each sentence should be independently deduped
        assert "[1][2]" in result
        assert "[2][3]" in result

    def test_preserves_text_without_citations(self):
        text = "No citations here. Just plain text."
        assert filter_citations(text) == text

    def test_realistic_noisy_llm_output(self):
        text = (
            "Artificial Intelligence Applications [1, 2, 3] include Grid Optimization [1, 2, 3], "
            "Predictive Maintenance [1, 2, 3], and Energy Efficiency [1, 2, 3]. "
            "Smart Grids [1, 2, 3] benefit from Machine Learning [1, 2] and Deep Learning [1, 2]."
        )
        result = filter_citations(text)
        # Should not have inline citations on every noun
        assert "[1, 2, 3]" not in result
        # Should have consolidated citations
        assert "[1][2][3]" in result
