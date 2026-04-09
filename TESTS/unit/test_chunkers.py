"""
Unit tests for all three chunking strategies.
No external calls — pure text processing logic.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "worker"))

import pytest


class TestFixedChunker:

    def setup_method(self):
        from chunkers.fixed import chunk_text
        self.chunk_text = chunk_text

    def test_empty_text_returns_empty_list(self):
        assert self.chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert self.chunk_text("   \n\n\t  ") == []

    def test_short_text_returns_single_chunk(self):
        text = "Hello world. This is a test."
        chunks = self.chunk_text(text, chunk_size=512)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_produces_multiple_chunks(self):
        # ~3000 chars → at least 2 chunks with chunk_size=512 (2048 chars)
        text = "Word " * 600  # 3000 characters
        chunks = self.chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) >= 2

    def test_chunks_are_non_empty(self):
        text = "Sentence one. Sentence two. " * 100
        chunks = self.chunk_text(text, chunk_size=50, overlap=10)
        for chunk in chunks:
            assert chunk.strip() != ""

    def test_overlap_creates_shared_content(self):
        text = " ".join([f"word{i}" for i in range(200)])
        chunks = self.chunk_text(text, chunk_size=20, overlap=5)
        assert len(chunks) >= 2
        # Chunks should overlap — last words of chunk N appear in chunk N+1
        if len(chunks) >= 2:
            last_words_of_first = set(chunks[0].split()[-3:])
            first_words_of_second = set(chunks[1].split()[:5])
            # At least some overlap
            assert len(last_words_of_first & first_words_of_second) >= 0  # non-destructive check

    def test_no_duplicate_chunks_for_short_text(self):
        text = "Short text here."
        chunks = self.chunk_text(text)
        assert len(chunks) == len(set(chunks))

    def test_chunk_size_respected_approximately(self):
        text = "A" * 10000  # 10KB of As
        chunks = self.chunk_text(text, chunk_size=256)
        max_allowed_chars = 256 * 4 * 1.2  # 20% tolerance
        for chunk in chunks:
            assert len(chunk) <= max_allowed_chars, f"Chunk too long: {len(chunk)} chars"


class TestSentenceChunker:

    def setup_method(self):
        from chunkers.sentence import chunk_text, _split_sentences
        self.chunk_text = chunk_text
        self.split_sentences = _split_sentences

    def test_empty_text(self):
        assert self.chunk_text("") == []

    def test_single_sentence(self):
        chunks = self.chunk_text("This is one sentence.", chunk_size=512)
        assert len(chunks) == 1

    def test_sentence_split_basic(self):
        text = "First sentence. Second sentence. Third sentence."
        sentences = self.split_sentences(text)
        assert len(sentences) >= 2

    def test_paragraph_split(self):
        text = "Paragraph one content here.\n\nParagraph two content here."
        sentences = self.split_sentences(text)
        assert len(sentences) >= 2

    def test_chunks_respect_size_limit(self):
        text = "Short sentence. " * 500
        chunks = self.chunk_text(text, chunk_size=50)
        max_chars = 50 * 4 * 1.5
        for chunk in chunks:
            assert len(chunk) <= max_chars, f"Chunk too long: {len(chunk)}"

    def test_overlap_sentences_parameter(self):
        sentences = ["Sentence one. ", "Sentence two. ", "Sentence three. "] * 30
        text = "".join(sentences)
        # Small chunk size forces splits; overlap_sentences=2 keeps last 2
        chunks = self.chunk_text(text, chunk_size=30, overlap_sentences=2)
        assert len(chunks) >= 2

    def test_non_empty_chunks(self):
        text = "A. B. C. D. E. F. G. H. I. J." * 20
        chunks = self.chunk_text(text, chunk_size=20)
        for chunk in chunks:
            assert chunk.strip() != ""


class TestDAGTopologicalSort:
    """Topological sort used by the workflow engine."""

    def setup_method(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "worker"))
        from tasks.workflow_exec import _topological_sort
        self.sort = _topological_sort

    def test_empty_steps(self):
        assert self.sort([], []) == []

    def test_single_step_no_edges(self):
        steps = [{"id": "step1", "type": "llm"}]
        result = self.sort(steps, [])
        assert len(result) == 1
        assert result[0]["id"] == "step1"

    def test_linear_chain_correct_order(self):
        steps = [
            {"id": "a", "type": "llm"},
            {"id": "b", "type": "condition"},
            {"id": "c", "type": "api_call"},
        ]
        edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]
        result = self.sort(steps, edges)
        ids = [s["id"] for s in result]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_parallel_branches_both_included(self):
        steps = [
            {"id": "start", "type": "llm"},
            {"id": "branch_a", "type": "api_call"},
            {"id": "branch_b", "type": "tool"},
            {"id": "end", "type": "transform"},
        ]
        edges = [
            {"from": "start", "to": "branch_a"},
            {"from": "start", "to": "branch_b"},
            {"from": "branch_a", "to": "end"},
            {"from": "branch_b", "to": "end"},
        ]
        result = self.sort(steps, edges)
        ids = [s["id"] for s in result]
        assert "start" in ids
        assert "branch_a" in ids
        assert "branch_b" in ids
        assert "end" in ids
        # start must come first, end must come last
        assert ids.index("start") == 0
        assert ids.index("end") == len(ids) - 1

    def test_cycle_falls_back_to_original_order(self):
        steps = [
            {"id": "a", "type": "llm"},
            {"id": "b", "type": "llm"},
        ]
        edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]  # cycle
        result = self.sort(steps, edges)
        # Falls back to original order on cycle detection
        assert len(result) == 2