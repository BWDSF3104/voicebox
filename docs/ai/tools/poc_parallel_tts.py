r"""PoC: chunk parallel TTS generation (GPU throughput + output-identity probe).

Question answered here (analysis found no library-level reentrancy blocker;
the real unknown is whether two concurrent generate() calls actually overlap
on the single default CUDA stream, or merely interleave Python-side).

Phases, same two texts + same seed:
  A  baseline      - sequential, exactly the production path
  B  concurrent    - both via asyncio.gather (two to_thread workers, default stream)
  C  concurrent+   - B but each worker pins its own torch.cuda.Stream

Metrics per phase: wall time, sec/char, audio seconds, sha256 of first output
(identity check vs A; a hash mismatch in B/C most likely means the global RNG
is shared across the two threads, not a race in the model itself).

Run (user):  docs\ai\tools\poc_parallel_tts.cmd
Logs:        docs\ai\tmp\poc-parallel-tts-<timestamp>.log  (stdout+stderr mirror)
             docs\ai\tmp\poc-parallel-tts-results.json     (append, one record per run)
No files are written outside docs/ai/tmp and the voice prompt disk cache.
"""
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # docs/ai/tools/<file> -> project root
sys.path.insert(0, str(ROOT))

import numpy as np
import torch

TMP = ROOT / "docs" / "ai" / "tmp"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
LOG_PATH = TMP / f"poc-parallel-tts-{STAMP}.log"
JSON_PATH = TMP / "poc-parallel-tts-results.json"

MODEL_SIZE = "1.7B"
SEED = 42
LANGUAGE = "ja"
# Two ~100-char excerpts of Natsume Soseki's Kokoro (public domain).
TEXTS = [
    "先生は最初からたいへんわたしを可愛がってくれた。だが正直なところ、その愛情は"
    "父に対するそれとは別種のものらしい。先生に子どもがないためだろう、とわたしは解釈していた。",
    "大学の空気のようには、化学的数学的分析のできない種類のものがあった。それを構成する"
    "人間をいくら精しく調べて見ても、その総和を積み立てた位では全体の化合物が得られない。",
]

_log = open(LOG_PATH, "w", encoding="utf-8", buffering=1)


def log(msg: str = "") -> None:
    print(msg)  # stdout is teed to LOG_PATH below


_original_stdout = sys.stdout


class Tee:
    def __init__(self):
        self.out = _original_stdout

    def write(self, s):
        try:
            self.out.write(s)
            self.out.flush()
        except Exception:
            pass
        _log.write(s)
        return len(s)

    def flush(self):
        _log.flush()


sys.stdout = Tee()  # capture library prints (torch warnings) into the log too


def nvidia_smi() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or out.stderr.strip()
    except Exception as exc:
        return f"nvidia-smi failed: {exc}"


def wav_hash(audio: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(audio, dtype=np.float32).tobytes()).hexdigest()[:16]


def describe(name: str, results, wall: float) -> dict:
    total_chars = sum(r["chars"] for r in results)
    audio_secs = sum(r["audio_secs"] for r in results)
    rec = {
        "phase": name,
        "wall_secs": round(wall, 2),
        "sec_per_char": round(wall / total_chars, 3),
        "audio_secs": round(audio_secs, 1),
        "rtf": round(wall / audio_secs, 3),  # real-time factor; <1 means faster than realtime
        "hashes": [r["hash"] for r in results],
        "lengths_secs": [r["audio_secs"] for r in results],
    }
    log(f"[{name}] wall={rec['wall_secs']}s  sec/char={rec['sec_per_char']}s"
        f"  audio={rec['audio_secs']}s  RTF={rec['rtf']}")
    log(f"       hashes={rec['hashes']} lengths={rec['lengths_secs']}")
    return rec


async def run_seq(backend, vp) -> tuple[list, float]:
    t0 = time.perf_counter()
    results = []
    for text in TEXTS:
        audio, sr = await backend.generate(text, vp, LANGUAGE, seed=SEED)
        results.append({"chars": len(text), "hash": wav_hash(audio),
                        "audio_secs": round(len(audio) / sr, 2)})
    return results, time.perf_counter() - t0


async def run_parallel(backend, vp) -> tuple[list, float]:
    t0 = time.perf_counter()

    async def one(text):
        audio, sr = await backend.generate(text, vp, LANGUAGE, seed=SEED)
        return {"chars": len(text), "hash": wav_hash(audio),
                "audio_secs": round(len(audio) / sr, 2)}

    results = await asyncio.gather(*(one(t) for t in TEXTS))
    return results, time.perf_counter() - t0


def _gen_sync_pinned_stream(backend, text, vp, stream):
    # Copy of PyTorchTTSBackend._generate_sync, pinned to a non-default stream.
    with torch.cuda.stream(stream):
        if SEED is not None:
            torch.manual_seed(SEED)
            if backend.device is not None:
                torch.cuda.manual_seed_all(SEED)
        wavs, sr = backend.model.generate_voice_clone(
            text=text,
            voice_clone_prompt=vp,
            language="Japanese",
            instruct=None,
            max_new_tokens=min(2048, 200 + int(len(text) * 4)),
            repetition_penalty=1.15,
        )
        torch.cuda.synchronize(stream)
        return wavs[0], sr


async def run_streams(backend, vp) -> tuple[list, float]:
    t0 = time.perf_counter()
    streams = [torch.cuda.Stream(), torch.cuda.Stream()]

    async def one(text, stream):
        audio, sr = await asyncio.to_thread(
            _gen_sync_pinned_stream, backend, text, vp, stream)
        return {"chars": len(text), "hash": wav_hash(audio),
                "audio_secs": round(len(audio) / sr, 2)}

    results = await asyncio.gather(*(one(t, s) for t, s in zip(TEXTS, streams)))
    return results, time.perf_counter() - t0


async def main() -> int:
    from backend import config

    app_data = Path(os.environ["APPDATA"]) / "sh.voicebox.app"
    config.set_data_dir(app_data)  # same dir the GUI sidecar uses → real profiles + caches
    log(f"data dir: {config.get_data_dir()}")

    from backend.backends import get_tts_backend_for_engine
    # Use the session module directly: init_db() only rebinds globals there,
    # not the package-level re-exports.
    from backend.database import session as _session
    from backend.services import profiles as profiles_service

    _session.init_db()
    db = _session.SessionLocal()
    plist = await profiles_service.list_profiles(db)
    if not plist:
        log("ABORT: no voice profiles found in the production data dir.")
        return 1
    profile = plist[0]
    log(f"profile: {profile.id} ({getattr(profile, 'name', '?')})")

    backend = get_tts_backend_for_engine("qwen")
    if os.environ.get("POC_CHECK"):
        log(f"CHECK OK: profile={profile.id} backend={type(backend).__name__} "
            f"device_attr={getattr(backend, 'device', None)} (no model loaded)")
        return 0
    log(f"GPU before load: {nvidia_smi()}")

    t0 = time.perf_counter()
    await backend.load_model_async(MODEL_SIZE)
    log(f"model load: {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    vp = await profiles_service.create_voice_prompt_for_profile(
        profile.id, db, use_cache=True, engine="qwen")
    log(f"voice prompt: {time.perf_counter() - t0:.1f}s")

    record = {"run": STAMP, "profile": str(profile.id), "seed": SEED,
              "chars_per_text": [len(t) for t in TEXTS], "phases": []}

    for name, fn in (("A-seq", run_seq), ("B-parallel", run_parallel),
                     ("C-streams", run_streams)):
        log()
        log(f"=== phase {name} ===  GPU: {nvidia_smi()}")
        try:
            t0 = time.perf_counter()
            results, wall = await fn(backend, vp)
            record["phases"].append(describe(name, results, wall))
        except torch.cuda.OutOfMemoryError:
            log(f"[{name}] CUDA OOM — record this as max-concurrency limit")
            record["phases"].append({"phase": name, "error": "CUDA OOM"})
        except Exception as exc:
            log(f"[{name}] FAILED: {type(exc).__name__}: {exc}")
            record["phases"].append({"phase": name, "error": str(exc)})

    log()
    log(f"GPU after: {nvidia_smi()}")
    a = next((p for p in record["phases"] if p.get("phase") == "A-seq"), None)
    if a and "hashes" in a:
        for p in record["phases"]:
            if "hashes" in p and p["phase"] != "A-seq":
                same = p["hashes"] == a["hashes"]
                log(f"identity {p['phase']} vs A-seq: {'IDENTICAL' if same else 'DIFFERENT'}"
                    f"{' (global RNG is shared between threads; expected)' if not same else ''}")

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = json.loads(JSON_PATH.read_text(encoding="utf-8")) if JSON_PATH.exists() else []
    history.append(record)
    JSON_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"results appended: {JSON_PATH}")
    log(f"log saved: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
