# 案D: 日本語長文チャンク分割の改善（端数結合・段落優先・UI設定露出）

**Status**: 完了
**Date**: 2026-11-15
**Next Action**: なし（クローズ。UI露出の natural_min_chars は longtext-streaming 側で 6cfde64 済み）

## 意図 / 背景

長文TTS（小説の朗読化）で `backend/utils/chunked_tts.py` の分割品質が全案（A/C/B）の基盤。2026-11-15 の実測（`docs/ai/tmp/probe_jp_split.py`、日本語2092字）で以下を観測済み（詳細は `2026-11-15-voicebox-longtext-streaming.md` の追加検討セクション）:
- 800字指定では文末「。」境界で正しく分割（日本語対応は健在）
- 2000字指定で末尾109字のミニチャンクが単独生成される（端数最適化なし）
- 改行（場面転換）優先分割がない

## 調査結果 / 変更内容

- `split_text_into_chunks` を書き換え（`backend/utils/chunked_tts.py`）:
  - `_paragraphs()`: 改行を最優先境界に段落へ分ける。段落が収まるうち Current chunk へ詰め込む（pack）。
  - `_split_sentences()`: 既存の文末境界ロジックを段落内に適用（改行なし長文の後方互換）。
  - `_fix_small_tail()` + `_rebalance_cut()`: 末尾が `max_chars` の `MIN_TAIL_RATIO=0.4` 未満なら前チャンクへ結合し、超过分を文境界で中央再配置（実測観測の末尾109字ミニチャンクを解消）。
  - `_join_sep()`: 結合時の区切りは ASCII 同士のみ空白、CJK は無区切り。
- フロント UI 露出は**既存**で追加不要と確認: `GenerationPage.tsx` に `maxChunkChars` スライダー（settings 永続化）、`useGenerationForm.ts` が generate へ `max_chunk_chars` を渡している。

## Verification

- `vbtest-venv` で `python -m pytest backend/tests/test_chunked_tts.py -v` → **10 passed**（新規6: 段落優先/詰め込み/日本語端数再配置/ASCII末尾/区切り文字/既存4。0.24s、2026-11-15）
- テスト実行 venv: `S:\Documents\Kilo_Commons\Common_Operations\docs\ai\tmp\vbtest-venv`（voicebox 側には無い）
- 実機（sidecar 生成品質）は cu128 ビルド（案D込み・2026-11-15 13:00Z デプロイ済み）でユーザー確認待ち

## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
