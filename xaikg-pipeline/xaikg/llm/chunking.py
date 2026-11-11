"""Document chunking driven by the ChunkingStrategy of the extraction task (read from the T4 side-car).
Every chunk records its character offsets in the document so that spans reported by the LLM
(relative to the chunk) can be mapped back to document offsets for provenance and grounding."""
from __future__ import annotations

import re
from dataclasses import dataclass

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
_PARAGRAPH = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class Chunk:
    index: int
    start: int
    end: int
    text: str


def _units(text: str, splitter: str) -> list[tuple[int, int]]:
    """(start, end) of the atomic units the splitter never cuts through."""
    if splitter == "PARAGRAPH":
        spans, pos = [], 0
        for m in _PARAGRAPH.finditer(text):
            if m.start() > pos:
                spans.append((pos, m.start()))
            pos = m.end()
        if pos < len(text):
            spans.append((pos, len(text)))
        return spans or [(0, len(text))]
    if splitter == "SENTENCE":
        spans, pos = [], 0
        for m in _SENTENCE_END.finditer(text):
            spans.append((pos, m.start()))
            pos = m.end()
        if pos < len(text):
            spans.append((pos, len(text)))
        return spans or [(0, len(text))]
    if splitter == "TOKEN":
        return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)] or [(0, len(text))]
    return []  # FIXED_SIZE: sliding window, no units


def chunk_document(text: str, chunk_size: int, overlap: int, splitter: str = "PARAGRAPH") -> list[Chunk]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("invalid chunking parameters (C3 guarantees this never happens for checked models)")
    if not text.strip():
        return []
    chunks: list[Chunk] = []
    if splitter == "FIXED_SIZE":
        step, pos = chunk_size - overlap, 0
        while pos < len(text):
            end = min(pos + chunk_size, len(text))
            chunks.append(Chunk(len(chunks), pos, end, text[pos:end]))
            if end == len(text):
                break
            pos += step
        return chunks

    units = _units(text, splitter)
    i = 0
    while i < len(units):
        start = units[i][0]
        j = i
        # pack units until the chunk would exceed chunk_size (always take at least one unit)
        while j + 1 < len(units) and units[j + 1][1] - start <= chunk_size:
            j += 1
        end = units[j][1]
        # a single unit longer than chunk_size is hard-split
        if end - start > chunk_size:
            pos = start
            while pos < end:
                e = min(pos + chunk_size, end)
                chunks.append(Chunk(len(chunks), pos, e, text[pos:e]))
                pos = e if e == end else e - overlap
            i = j + 1
            continue
        chunks.append(Chunk(len(chunks), start, end, text[start:end]))
        if j + 1 >= len(units):
            break
        # overlap: step back over trailing units whose total length is <= overlap
        k = j + 1
        while k > i + 1 and end - units[k - 1][0] <= overlap:
            k -= 1
        i = k
    return chunks
