# 案D: 日本語長文チャンク分割の改善（端数結合・段落優先・UI設定露出）

**Status**: 未着手
**Date**: 2026-11-15
**Next Action**: backend/tests に端数結合のテスト追加→split_text_into_chunks 改善→フロントUIでmax_chunk_chars設定露出

## 意図 / 背景

長文TTS（小説の朗読化）で `backend/utils/chunked_tts.py` の分割品質が全案（A/C/B）の基盤。2026-11-15 の実測（`docs/ai/tmp/probe_jp_split.py`、日本語2092字）で以下を観測済み（詳細は `2026-11-15-voicebox-longtext-streaming.md` の追加検討セクション）:
- 800字指定では文末「。」境界で正しく分割（日本語対応は健在）
- 2000字指定で末尾109字のミニチャンクが単独生成される（端数最適化なし）
- 改行（場面転換）優先分割がない

## 調査結果 / 変更内容

（着手時に記入。実装方針: 末尾チャンクがしきい値未満なら前チャンクと結合 or 平均再配置／改行を最優先境界に／長文用に `max_chunk_chars` をフロント設定として露出 — APIは GenerationRequest に既存フィールドのためバックエンド改修ほぼ不要）

## Verification

（未実施。予定: split_text_into_chunks のテストを backend/tests に追加（端数結合・段落優先・日本語/英語混在）、`vbtest-venv` で pytest）

## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
