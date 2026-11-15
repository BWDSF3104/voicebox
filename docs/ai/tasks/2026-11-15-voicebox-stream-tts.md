# 案B: 生成音声のストリーム化（B①先頭チャンク縮小→B②qwenエンジン級ストリーム評価）

**Status**: 未着手
**Date**: 2026-11-15
**Next Action**: B①: 先頭チャンクだけ小（例200字）の分割オプション実装→初回再生待ちを実測→B②の要否判断

## 意図 / 背景

長文生成で最初の再生まで全文（または800字チャンク）待ちとなる体感遅延の削減。観測で「完全な1音声ストリーム」はエンジン制約があることが判明（詳細: `2026-11-15-voicebox-longtext-streaming.md` 追加検討）:
- qwen3-tts は `generate_speech(..., streaming=False)` のみ。真の音声ストリームは `StreamingChatMLProcessor`（QwenTTS-Realtime 専用、モデル差し替え+WebSocket変換が必要で重い）
- kokml（TTSInferEngine実）は chunk-by-chunk yield 可能。voicebox の `generate_from_text` は `asyncio.run` で await → `yield` 不可
- engines/ の音声ストリーム経路は whisper 文字起こし専用（`/transcribe/stream`）で、`/generate/stream` は存在しない

## 調査結果 / 変更内容

（着手時に記入）
- **B①（安価・本命）**: `split_text_into_chunks` に先頭チャンクのみ小（例200字）のオプション追加。案A の chunk spool と段階再生がそのまま効くので、UIは初回再生待ちの短縮のみで新規コードほぼ不要
- **B②（重い・条件付き）**: qwen エンジンの `StreamingChatMLProcessor` 級ストリーム化。B① 実測の初回待ちが許容範囲なら不実施（要否判断を記録して終了）

## Verification

（未実施。予定: 先頭チャンク縮小の単体テスト＋初回再生待ちの実測値を本ファイルに記録。B②実施時は dev モードまたは sidecar 再ビルド版で実機確認）

## 依存 / 順序

- 案D（チャンク分割改善）→ 案C（読本パイプライン）→ 本案B の順で着手
- chunk spool・段階再生（案A）実装済み（commit ab3241f）が前提として効く

## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
