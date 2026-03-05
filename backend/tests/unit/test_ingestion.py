"""Unit tests for the document ingestion pipeline (PyMuPDF-based)."""

from __future__ import annotations

from app.services.rag.ingestion import (
    _find_page_at_position,
    _make_chunk,
    _markdown_section_chunks,
    _sliding_window_chunks,
)

# ── _sliding_window_chunks ──────────────────────────────────────────────────


class TestSlidingWindowChunks:
    def test_basic_split(self) -> None:
        text = "a" * 2000
        chunks = _sliding_window_chunks(text, size=1000, overlap=200)
        # start=0 [0:1000], start=800 [800:1800], start=1600 [1600:2000]
        assert len(chunks) == 3
        assert len(chunks[0]) == 1000
        assert len(chunks[1]) == 1000
        assert len(chunks[2]) == 400

    def test_short_text(self) -> None:
        chunks = _sliding_window_chunks("hello world", size=1000, overlap=200)
        assert len(chunks) == 1
        assert chunks[0] == "hello world"

    def test_empty_text(self) -> None:
        assert _sliding_window_chunks("") == []
        assert _sliding_window_chunks("   ") == []

    def test_exact_size(self) -> None:
        text = "x" * 1000
        chunks = _sliding_window_chunks(text, size=1000, overlap=200)
        # start=0 [0:1000], start=800 [800:1000] → 200 chars
        assert len(chunks) == 2
        assert len(chunks[0]) == 1000
        assert len(chunks[1]) == 200

    def test_overlap_content(self) -> None:
        text = "AAAA" + "BBBB" + "CCCC"  # 12 chars
        chunks = _sliding_window_chunks(text, size=8, overlap=4)
        # chunk 0: start=0, end=8 → "AAAABBBB"
        # chunk 1: start=4, end=12 → "BBBBCCCC"
        assert chunks[0] == "AAAABBBB"
        assert chunks[1] == "BBBBCCCC"


# ── _markdown_section_chunks ────────────────────────────────────────────────


class TestMarkdownSectionChunks:
    def test_splits_on_headers(self) -> None:
        pages = [
            (1, "## Introduction\nThis is the intro."),
            (2, "## Methods\nWe did stuff.\n## Results\nThings happened."),
        ]
        chunks = _markdown_section_chunks(pages, doc_id="test-doc")
        sections = [c["section"] for c in chunks]
        assert "Introduction" in sections
        assert "Methods" in sections
        assert "Results" in sections

    def test_page_numbers_tracked(self) -> None:
        pages = [
            (1, "## Chapter 1\nPage one content."),
            (5, "## Chapter 2\nPage five content."),
        ]
        chunks = _markdown_section_chunks(pages, doc_id="test-doc")
        page_map = {str(c["section"]): c["page"] for c in chunks}
        assert page_map["Chapter 1"] == 1
        assert page_map["Chapter 2"] == 5

    def test_no_headers_falls_back(self) -> None:
        pages = [(1, "Just some plain text without any headers.")]
        chunks = _markdown_section_chunks(pages, doc_id="test-doc")
        assert len(chunks) >= 1
        assert chunks[0]["section"] == ""
        assert chunks[0]["page"] == 1

    def test_oversized_section_subsplit(self) -> None:
        long_text = "## Big Section\n" + "word " * 500  # ~2500 chars
        pages = [(3, long_text)]
        chunks = _markdown_section_chunks(pages, doc_id="test-doc", max_chunk_size=500)
        assert len(chunks) > 1
        for c in chunks:
            assert c["section"] == "Big Section"
            assert c["page"] == 3

    def test_preamble_before_first_header(self) -> None:
        pages = [(1, "Some preamble text.\n\n## First Section\nContent here.")]
        chunks = _markdown_section_chunks(pages, doc_id="test-doc")
        assert chunks[0]["section"] == ""
        assert "preamble" in str(chunks[0]["text"])
        assert chunks[1]["section"] == "First Section"

    def test_empty_pages_skipped(self) -> None:
        pages = [(1, "   "), (2, "## Real\nContent")]
        chunks = _markdown_section_chunks(pages, doc_id="test-doc")
        assert len(chunks) == 1
        assert chunks[0]["section"] == "Real"


# ── _make_chunk ─────────────────────────────────────────────────────────────


class TestMakeChunk:
    def test_schema_keys(self) -> None:
        chunk = _make_chunk("doc-1", "hello", 1, "Intro")
        assert set(chunk.keys()) == {
            "id",
            "doc_id",
            "text",
            "vector",
            "page",
            "section",
            "content_type",
            "has_equations",
        }
        assert chunk["doc_id"] == "doc-1"
        assert chunk["text"] == "hello"
        assert chunk["page"] == 1
        assert chunk["section"] == "Intro"
        assert chunk["vector"] == []
        assert chunk["content_type"] == "text"

    def test_has_equations_dollar(self) -> None:
        chunk = _make_chunk("d", "E = mc$^2$", 1, "")
        assert chunk["has_equations"] is True

    def test_has_equations_backslash(self) -> None:
        chunk = _make_chunk("d", "\\frac{1}{2}", 1, "")
        assert chunk["has_equations"] is True

    def test_no_equations(self) -> None:
        chunk = _make_chunk("d", "plain text here", 1, "")
        assert chunk["has_equations"] is False


# ── _find_page_at_position ──────────────────────────────────────────────────


class TestFindPageAtPosition:
    def test_finds_marker_before_position(self) -> None:
        full = "<!-- PAGE:3 -->\nsome text\n<!-- PAGE:7 -->\nmore"
        # Position after first marker → page 3
        assert _find_page_at_position(full, 16, []) == 3

    def test_finds_nearest_marker(self) -> None:
        full = "<!-- PAGE:1 -->\nstuff\n<!-- PAGE:5 -->\nmore"
        # Position after second marker → page 5
        assert _find_page_at_position(full, 30, [(1, ""), (5, "")]) == 5

    def test_no_marker_falls_back(self) -> None:
        assert _find_page_at_position("no markers", 0, [(10, "text")]) == 10

    def test_no_marker_no_pages(self) -> None:
        assert _find_page_at_position("no markers", 0, []) == 0
