"""
Story-level text splitting for the audiobook import pipeline (Plan C).

Splits a long text into *segments* (= one story item = one generation job).
This layer is distinct from ``chunked_tts.split_text_into_chunks``: segment
size here decides editing granularity; chunks inside each segment stay
handled by the existing per-generation TTS splitter.

Granularities:
- ``paragraph``: one line = one paragraph (Japanese-novel convention).
- ``chapter``: split before chapter headings (default regex matches
  ``第一章`` etc.). Falls back to ``paragraph`` when no heading is found.
- ``chars``: delegate to ``chunked_tts.split_text_into_chunks`` (sentence-
  first packing with tail rebalance).
"""

import re
from typing import List, Optional

CHAPTER_REGEX_DEFAULT = r"^\s*第[0-9〇一二三四五六七八九十百千万]+章.*$"


def split_for_story(
    text: str,
    granularity: str = "paragraph",
    chapter_regex: Optional[str] = None,
    max_chars: int = 2000,
) -> List[str]:
    """Split *text* into story segments. Never returns empty segments."""
    text = text.strip()
    if not text:
        return []
    if granularity == "chapter":
        segs = _split_chapters(text, chapter_regex or CHAPTER_REGEX_DEFAULT)
        if segs is None:  # no heading matched -> fall back
            return split_for_story(text, "paragraph")
        return segs
    if granularity == "chars":
        from .chunked_tts import split_text_into_chunks

        return split_text_into_chunks(text, max_chars=max_chars)
    # paragraph: single newline = boundary (Japanese novels are 1行=1段落)
    return [p.strip() for p in text.splitlines() if p.strip()]


def _split_chapters(text: str, chapter_regex: str) -> Optional[List[str]]:
    try:
        pattern = re.compile(chapter_regex, re.MULTILINE)
    except re.error:
        return None
    hits = list(pattern.finditer(text))
    if not hits:
        return None
    segments: List[str] = []
    head = text[: hits[0].start()].strip()
    if head:
        segments.append(head)
    positions = [h.start() for h in hits] + [len(text)]
    for i in range(len(hits)):
        seg = text[positions[i] : positions[i + 1]].strip()
        if seg:
            segments.append(seg)
    return segments
