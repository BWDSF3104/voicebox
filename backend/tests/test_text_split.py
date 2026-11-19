"""Tests for story-level text splitting (utils/text_split.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.utils.text_split import split_for_story


def test_paragraph_drops_blank_lines():
    text = "一\n\n二\n\n\n三\n"
    assert split_for_story(text) == ["一", "二", "三"]


def test_empty_text_returns_empty():
    assert split_for_story("   \n\n  ") == []


def test_chapter_default_regex_splits_and_keeps_heading():
    text = "序文\n第一章 はじめ\n本文a\n第二章 つぎ\n本文b"
    segs = split_for_story(text, granularity="chapter")
    assert segs[0] == "序文"
    assert segs[1] == "第一章 はじめ\n本文a"
    assert segs[2] == "第二章 つぎ\n本文b"


def test_chapter_custom_regex():
    text = "== A\nx\n== B\ny"
    segs = split_for_story(
        text, granularity="chapter", chapter_regex=r"^== .*$"
    )
    assert segs == ["== A\nx", "== B\ny"]


def test_chapter_no_heading_falls_back_to_paragraph():
    text = "一\n二\n三"
    assert split_for_story(text, granularity="chapter") == ["一", "二", "三"]


def test_chapter_invalid_regex_falls_back():
    text = "一\n二"
    assert split_for_story(text, granularity="chapter", chapter_regex="(") == [
        "一",
        "二",
    ]


def test_chars_respects_max_and_keeps_all_text():
    text = "あ。" * 200  # 400 chars, sentences of 2
    segs = split_for_story(text, granularity="chars", max_chars=50)
    assert all(len(s) <= 50 for s in segs)
    assert "".join(segs) == text
