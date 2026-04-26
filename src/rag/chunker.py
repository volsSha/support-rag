from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    content: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


_HEADING_RE = re.compile(r"^(#{1,6}\s.*)$", re.MULTILINE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _extract_headers(text: str) -> list[str]:
    return _HEADING_RE.findall(text)


def _current_header(lines: list[str]) -> str:
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped
    return ""


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paragraphs


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text)
    return [s.strip() for s in parts if s.strip()]


def chunk_document(text: str, chunk_size: int = 400, overlap: int = 80) -> list[Chunk]:
    if not text.strip():
        return []

    char_target = chunk_size * 4
    char_overlap = overlap * 4

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    lines = text.split("\n")

    def find_header_for(para_text: str) -> str:
        for i, line in enumerate(lines):
            if para_text[:50] in line or line.strip() == para_text[: len(line.strip())]:
                return _current_header(lines[: i + 1])
        for i, line in enumerate(lines):
            if para_text.split(".")[0].strip() in line:
                return _current_header(lines[: i + 1])
        return ""

    segments: list[str] = []
    for para in paragraphs:
        header = find_header_for(para)
        if len(para) <= char_target:
            prefix = f"{header}\n" if header else ""
            segments.append(f"{prefix}{para}")
        else:
            sentences = _split_sentences(para)
            buffer = ""
            prefix = f"{header}\n" if header else ""
            for sentence in sentences:
                if buffer and len(buffer) + len(sentence) > char_target:
                    segments.append(f"{prefix}{buffer.strip()}")
                    prefix = ""
                    buffer = sentence[char_overlap:] if len(sentence) > char_overlap else sentence
                else:
                    buffer += (" " if buffer else "") + sentence
            if buffer.strip():
                segments.append(f"{prefix}{buffer.strip()}")

    if not segments:
        return [Chunk(content=text.strip(), chunk_index=0, metadata={})]

    if len(segments) == 1 and len(segments[0]) <= char_target:
        return [Chunk(content=segments[0].strip(), chunk_index=0, metadata={})]

    merged: list[str] = []
    current = ""
    for seg in segments:
        if current and len(current) + len(seg) > char_target:
            merged.append(current.strip())
            if len(current) > char_overlap:
                current = current[-char_overlap:] + "\n" + seg
            else:
                current = seg
        else:
            current = f"{current}\n{seg}" if current else seg
    if current.strip():
        merged.append(current.strip())

    return [Chunk(content=content, chunk_index=i, metadata={}) for i, content in enumerate(merged)]
