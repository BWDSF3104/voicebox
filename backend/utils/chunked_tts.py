"""
Chunked TTS generation utilities.

Splits long text into sentence-boundary chunks, generates audio per-chunk
via any TTSBackend, and concatenates with crossfade.  All logic is
engine-agnostic — it wraps the standard ``TTSBackend.generate()`` interface.

Short text (≤ max_chunk_chars) uses the single-shot fast path with zero
overhead.
"""

import logging
import re
from typing import List, Tuple

import numpy as np

logger = logging.getLogger("voicebox.chunked-tts")

# Default chunk size in characters.  Can be overridden per-request via
# the ``max_chunk_chars`` field on GenerationRequest.
DEFAULT_MAX_CHUNK_CHARS = 800

# Common abbreviations that should NOT be treated as sentence endings.
# Lowercase for case-insensitive matching.
_ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "st",
        "ave",
        "blvd",
        "inc",
        "ltd",
        "corp",
        "dept",
        "est",
        "approx",
        "vs",
        "etc",
        "e.g",
        "i.e",
        "a.m",
        "p.m",
        "u.s",
        "u.s.a",
        "u.k",
    }
)

# Paralinguistic tags used by Chatterbox Turbo.  The splitter must never
# cut inside one of these.
_PARA_TAG_RE = re.compile(r"\[[^\]]*\]")


# A trailing chunk shorter than this fraction of *max_chars* is rebalanced
# with the previous chunk instead of becoming a standalone mini-generation.
MIN_TAIL_RATIO = 0.4


def split_text_into_chunks(text: str, max_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> List[str]:
    """Split *text* at natural boundaries into chunks of at most *max_chars*.

    Priority: paragraph (newline) boundary → sentence-end (``.!?`` not
    preceded by an abbreviation and not inside brackets) → clause boundary
    (``;:,—``) → whitespace → hard cut.  Small paragraphs are packed into
    the current chunk; a trailing chunk below ``MIN_TAIL_RATIO`` of
    *max_chars* is merged with the previous one (or split in two near the
    centre when the merge would overflow).

    Paralinguistic tags like ``[laugh]`` are treated as atomic and will not
    be split across chunks.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    for para in _paragraphs(text):
        if len(para) > max_chars:
            chunks.extend(_split_sentences(para, max_chars))
        elif chunks and len(chunks[-1]) + 1 + len(para) <= max_chars:
            chunks[-1] = chunks[-1] + "\n" + para
        else:
            chunks.append(para)

    return _fix_small_tail(chunks, max_chars)


def _paragraphs(text: str) -> List[str]:
    """Split on newlines, dropping blank lines."""
    return [p.strip() for p in text.splitlines() if p.strip()]


def _split_sentences(remaining: str, max_chars: int) -> List[str]:
    """Split one oversized paragraph at sentence/clause boundaries."""
    chunks: List[str] = []

    while remaining:
        remaining = remaining.lstrip()
        if not remaining:
            break
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        segment = remaining[:max_chars]

        # Try to split at the last real sentence ending
        split_pos = _find_last_sentence_end(segment)
        if split_pos == -1:
            split_pos = _find_last_clause_boundary(segment)
        if split_pos == -1:
            split_pos = segment.rfind(" ")
        if split_pos == -1:
            # Absolute fallback: hard cut but avoid splitting inside a tag
            split_pos = _safe_hard_cut(segment, max_chars)

        chunk = remaining[: split_pos + 1].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos + 1 :]

    return chunks


def _fix_small_tail(chunks: List[str], max_chars: int) -> List[str]:
    """Merge/rebalance a trailing chunk that is too small to be worth
    a standalone generation call."""
    if len(chunks) < 2:
        return chunks
    min_tail = max(int(max_chars * MIN_TAIL_RATIO), 1)
    last, prev = chunks.pop(), chunks.pop()
    if len(last) >= min_tail:
        chunks.extend([prev, last])
        return chunks

    merged = prev + _join_sep(prev, last) + last
    if len(merged) <= max_chars:
        chunks.append(merged)
        return chunks

    # Rebalance: one split near the centre at the nearest sentence end
    cut = _rebalance_cut(merged, max_chars, min_tail)
    first, second = merged[:cut].strip(), merged[cut:].strip()
    if first and second:
        chunks.extend([first, second])
    else:
        chunks.append(merged)
    return chunks


def _join_sep(prev: str, last: str) -> str:
    """Separator when re-joining two chunks: a space when both sides are
    ASCII (Latin text spaces around punctuation), nothing for CJK."""
    a, b = prev[-1] if prev else "", last[0] if last else ""
    if a.isascii() and b.isascii():
        return " "
    return ""


def _rebalance_cut(text: str, max_chars: int, min_tail: int) -> int:
    """Index to split *text* into two roughly equal parts, preferring
    sentence-ending punctuation near the midpoint."""
    target = len(text) // 2
    best = -1
    best_dist = None
    for m in re.finditer(r"[.!?](?:\s|$)|[\u3002\uff01\uff1f]", text[:max_chars]):
        pos = m.end()
        if pos < min_tail:
            continue
        dist = abs(pos - target)
        if best == -1 or dist < best_dist:
            best, best_dist = pos, dist
    if best == -1:
        pos = text.rfind(" ", 0, max_chars)
        if pos > 0:
            return pos
        return target
    return best


def _find_last_sentence_end(text: str) -> int:
    """Return the index of the last sentence-ending punctuation in *text*.

    Skips periods that follow common abbreviations (``Dr.``, ``Mr.``, etc.)
    and periods inside bracket tags (``[laugh]``).  Also handles CJK
    sentence-ending punctuation (``。！？``).
    """
    best = -1
    # ASCII sentence ends
    for m in re.finditer(r"[.!?](?:\s|$)", text):
        pos = m.start()
        char = text[pos]
        # Skip periods after abbreviations
        if char == ".":
            # Walk backwards to find the preceding word
            word_start = pos - 1
            while word_start >= 0 and text[word_start].isalpha():
                word_start -= 1
            word = text[word_start + 1 : pos].lower()
            if word in _ABBREVIATIONS:
                continue
            # Skip decimal numbers (digit immediately before the period)
            if word_start >= 0 and text[word_start].isdigit():
                continue
        # Skip if we're inside a bracket tag
        if _inside_bracket_tag(text, pos):
            continue
        best = pos
    # CJK sentence-ending punctuation
    for m in re.finditer(r"[\u3002\uff01\uff1f]", text):
        if m.start() > best:
            best = m.start()
    return best


def _find_last_clause_boundary(text: str) -> int:
    """Return the index of the last clause-boundary punctuation."""
    best = -1
    for m in re.finditer(r"[;:,\u2014](?:\s|$)", text):
        pos = m.start()
        # Skip if inside a bracket tag
        if _inside_bracket_tag(text, pos):
            continue
        best = pos
    return best


def _inside_bracket_tag(text: str, pos: int) -> bool:
    """Return True if *pos* falls inside a ``[...]`` tag."""
    for m in _PARA_TAG_RE.finditer(text):
        if m.start() < pos < m.end():
            return True
    return False


def _safe_hard_cut(segment: str, max_chars: int) -> int:
    """Find a hard-cut position that doesn't split a ``[tag]``."""
    cut = max_chars - 1
    # Check if the cut falls inside a bracket tag; if so, move before it
    for m in _PARA_TAG_RE.finditer(segment):
        if m.start() < cut < m.end():
            return m.start() - 1 if m.start() > 0 else cut
    return cut


def concatenate_audio_chunks(
    chunks: List[np.ndarray],
    sample_rate: int,
    crossfade_ms: int = 50,
) -> np.ndarray:
    """Concatenate audio arrays with a short crossfade to eliminate clicks.

    Each chunk is expected to be a 1-D float32 ndarray at *sample_rate* Hz.
    """
    if not chunks:
        return np.array([], dtype=np.float32)
    if len(chunks) == 1:
        return chunks[0]

    crossfade_samples = int(sample_rate * crossfade_ms / 1000)
    result = np.array(chunks[0], dtype=np.float32, copy=True)

    for chunk in chunks[1:]:
        if len(chunk) == 0:
            continue
        overlap = min(crossfade_samples, len(result), len(chunk))
        if overlap > 0:
            fade_out = np.linspace(1.0, 0.0, overlap, dtype=np.float32)
            fade_in = np.linspace(0.0, 1.0, overlap, dtype=np.float32)
            result[-overlap:] = result[-overlap:] * fade_out + chunk[:overlap] * fade_in
            result = np.concatenate([result, chunk[overlap:]])
        else:
            result = np.concatenate([result, chunk])

    return result


async def generate_chunked(
    backend,
    text: str,
    voice_prompt: dict,
    language: str = "en",
    seed: int | None = None,
    instruct: str | None = None,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    crossfade_ms: int = 50,
    trim_fn=None,
    on_chunk=None,
    on_chunk_start=None,
) -> Tuple[np.ndarray, int]:
    """Generate audio with automatic chunking for long text.

    For text shorter than *max_chunk_chars* this is a thin wrapper around
    ``backend.generate()`` with zero overhead.

    For longer text the input is split at natural sentence boundaries,
    each chunk is generated independently, optionally trimmed (useful for
    Chatterbox engines that hallucinate trailing noise), and the results
    are concatenated with a crossfade (or hard cut if *crossfade_ms* is 0).

    Parameters
    ----------
    backend : TTSBackend
        Any backend implementing the ``generate()`` protocol.
    text : str
        Input text (may be arbitrarily long).
    voice_prompt, language, seed, instruct
        Forwarded to ``backend.generate()`` verbatim.
    max_chunk_chars : int
        Maximum characters per chunk (default 800).
    crossfade_ms : int
        Crossfade duration in milliseconds between chunks.  0 for a hard
        cut with no overlap (default 50).
    trim_fn : callable | None
        Optional ``(audio, sample_rate) -> audio`` post-processing
        function applied to each chunk before concatenation (e.g.
        ``trim_tts_output`` for Chatterbox engines).
    on_chunk : callable | None
        Optional synchronous ``(index, total, audio, sample_rate)`` callback
        invoked right after each chunk (including the single-chunk fast path)
        is generated and trimmed. Used to surface long-text progress; raising
        propagates to the caller — wrap in your own try/except if it must not
        abort generation.
    on_chunk_start : callable | None
        Optional synchronous ``(index, total)`` callback invoked right before
        each chunk starts generating.  Reports progress while a chunk is still
        in flight — the UI would otherwise show nothing for minutes.

    Returns
    -------
    (audio, sample_rate) : Tuple[np.ndarray, int]
    """
    chunks = split_text_into_chunks(text, max_chunk_chars)

    if len(chunks) <= 1:
        # Short text — single-shot fast path
        audio, sample_rate = await backend.generate(
            text,
            voice_prompt,
            language,
            seed,
            instruct,
        )
        if trim_fn is not None:
            audio = trim_fn(audio, sample_rate)
        if on_chunk is not None:
            on_chunk(0, 1, audio, sample_rate)
        return audio, sample_rate

    # Long text — chunked generation
    logger.info(
        "Splitting %d chars into %d chunks (max %d chars each)",
        len(text),
        len(chunks),
        max_chunk_chars,
    )
    audio_chunks: List[np.ndarray] = []
    sample_rate: int | None = None

    for i, chunk_text in enumerate(chunks):
        logger.info(
            "Generating chunk %d/%d (%d chars)",
            i + 1,
            len(chunks),
            len(chunk_text),
        )
        if on_chunk_start is not None:
            on_chunk_start(i, len(chunks))
        # Vary the seed per chunk to avoid correlated RNG artefacts,
        # but keep it deterministic so the same (text, seed) pair
        # always produces the same output.
        chunk_seed = (seed + i) if seed is not None else None

        chunk_audio, chunk_sr = await backend.generate(
            chunk_text,
            voice_prompt,
            language,
            chunk_seed,
            instruct,
        )
        if trim_fn is not None:
            chunk_audio = trim_fn(chunk_audio, chunk_sr)

        audio_chunks.append(np.asarray(chunk_audio, dtype=np.float32))
        if sample_rate is None:
            sample_rate = chunk_sr

        if on_chunk is not None:
            on_chunk(i, len(chunks), chunk_audio, chunk_sr)

    audio = concatenate_audio_chunks(audio_chunks, sample_rate, crossfade_ms=crossfade_ms)
    return audio, sample_rate
