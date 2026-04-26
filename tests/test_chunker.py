from __future__ import annotations

from src.rag.chunker import Chunk, chunk_document


def test_empty_string():
    assert chunk_document("") == []
    assert chunk_document("   \n\n  ") == []


def test_short_text_single_chunk():
    result = chunk_document("Hello world.")
    assert len(result) == 1
    assert result[0].content == "Hello world."
    assert result[0].chunk_index == 0


def test_long_text_multiple_chunks():
    paragraphs = [
        "This is paragraph one. " * 60,
        "This is paragraph two. " * 60,
        "This is paragraph three. " * 60,
    ]
    text = "\n\n".join(paragraphs)
    result = chunk_document(text)
    assert len(result) > 1
    for i, chunk in enumerate(result):
        assert isinstance(chunk, Chunk)
        assert chunk.chunk_index == i
        assert len(chunk.content) > 0


def test_chunk_indices_sequential():
    text = "First paragraph. " * 200 + "\n\n" + "Second paragraph. " * 200
    result = chunk_document(text)
    indices = [c.chunk_index for c in result]
    assert indices == list(range(len(result)))


def test_markdown_headers_preserved():
    text = "# Getting Started\n\nWelcome to the app. This is the introduction. " * 50
    result = chunk_document(text)
    assert len(result) >= 1
    found_header = any("# Getting Started" in c.content for c in result)
    assert found_header, "Markdown header should be preserved in chunk content"


def test_multiple_headers():
    text = "# Section One\n\nContent for section one. " * 60 + "\n\n## Subsection\n\nSubsection content. " * 60
    result = chunk_document(text)
    assert len(result) > 1
    has_section_one = any("# Section One" in c.content for c in result)
    assert has_section_one


def test_metadata_default():
    result = chunk_document("Some text here.")
    assert result[0].metadata == {}


def test_overlap_between_chunks():
    text = "This is a sentence. " * 200
    result = chunk_document(text)
    if len(result) > 1:
        end_of_first = result[0].content[-100:]
        start_of_second = result[1].content[:100:]
        has_overlap = end_of_first.rstrip() in start_of_second or start_of_second.lstrip() in end_of_first
        assert has_overlap, "Consecutive chunks should have overlap"
