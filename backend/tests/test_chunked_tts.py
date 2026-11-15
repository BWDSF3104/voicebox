"""Tests for chunked TTS generation callbacks and progress tracking."""

import asyncio

import numpy as np

from backend.utils.chunked_tts import generate_chunked
from backend.utils.tasks import TaskManager


class MockBackend:
    def __init__(self, duration_ms: int = 20, sample_rate: int = 24000):
        self.duration_ms = duration_ms
        self.sample_rate = sample_rate
        self.calls = 0

    async def generate(self, text, voice_prompt, language, seed, instruct):
        self.calls += 1
        n = int(self.sample_rate * self.duration_ms / 1000)
        return np.sin(np.linspace(0, 100, n, dtype=np.float32)), self.sample_rate


def test_on_chunk_called_per_chunk_in_order():
    long_text = ("This is a test sentence. " * 40) + "End."
    backend = MockBackend()
    seen = []

    def on_chunk(index, total, audio, sample_rate):
        seen.append((index, total, len(audio), sample_rate))

    audio, sr = asyncio.run(
        generate_chunked(backend, long_text, {}, max_chunk_chars=800, on_chunk=on_chunk)
    )
    assert backend.calls == len(seen) > 1, "should have produced multiple chunks"
    assert [idx for idx, _, _, _ in seen] == list(range(len(seen)))
    assert {total for _, total, _, _ in seen} == {len(seen)}
    assert audio.ndim == 1 and sr == backend.sample_rate


def test_on_chunk_fast_path_single_chunk():
    backend = MockBackend()
    seen = []
    asyncio.run(generate_chunked(backend, "Short text.", {}, on_chunk=lambda i, t, a, sr: seen.append((i, t))))
    assert seen == [(0, 1)]


def test_no_callback_keeps_existing_behavior():
    backend = MockBackend()
    audio, sr = asyncio.run(generate_chunked(backend, "Short text.", {}))
    assert audio.ndim == 1


def test_trim_fn_applied_before_callback():
    backend = MockBackend(duration_ms=100)

    def trim(audio, sr):
        return audio[: int(sr * 0.01)]

    seen = []
    asyncio.run(
        generate_chunked(backend, "Short text.", {}, trim_fn=trim, on_chunk=lambda i, t, a, sr: seen.append(len(a)))
    )
    assert seen == [240]


def test_task_manager_progress_roundtrip():
    tm = TaskManager()
    tm.start_generation("g1", "p1", "text")
    assert tm.get_generation_progress("g1") is None  # total unknown yet
    tm.update_generation_progress("g1", 2, 5)
    assert tm.get_generation_progress("g1") == {"completed": 2, "total": 5}
    tm.update_generation_progress("g1", 5, 5)
    assert tm.get_generation_progress("g1") == {"completed": 5, "total": 5}
    tm.complete_generation("g1")
    assert tm.get_generation_progress("g1") is None
    # Updates for unknown tasks are ignored.
    tm.update_generation_progress("missing", 1, 1)
