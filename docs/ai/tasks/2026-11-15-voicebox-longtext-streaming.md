# Voicebox 長文生成の進捗表示・段階再生（案A実装）

**Status**: 進行中（CUDA sidecar再ビルド着手）
**Date**: 2026-11-15
**Next Action**: venv(py3.12)+pip install 実行中→完了後 build_binary.py --cuda→backends\cuda 差し替え→インストール版で進捗表示・段階再生を実機確認

> **このファイルが正典**（2026-11-15 移管、`decisions/2026-11-15-docs-relocation-to-voicebox.md` 参照）。Common_Operations 側に同名コピーが残っている場合、そちらは凍結なので更新内容は本ファイルへ反映すること。

## 意図 / 背景

長文（小説等の日本語音声化）を TTS 生成する際、v0.5.0 は「全チャンク生成完了まで待ってから再生可能」で、生成中の進捗も分からない。ユーザー要望で案A（段階再生＋低コスト進捗表示）を実施。進捗は生成速度に実質影響なし（メモリ記録＋既存SSE相乗り）が条件。調査は親タスク `2026-11-15-voicebox-windows-quit-fix.md` の検討セクション参照。

## 調査結果 / 変更内容

既存資産: `utils/chunked_tts.py`（800字/チャンク文末分割+crossfade、逐次ループ）、`/generate/{id}/status` は SSE（frontend `useGenerationProgress.ts` が購読済み、サーバー側は1秒DBポーリング）、pub/sub `mcp_server/events.py`。

変更はブランチ `fix/windows-quit` の追加2コミット（fork `BWDSF3104/voicebox` へ push 済み）:

### bc2cb4a 進捗表示
- `utils/chunked_tts.py`: `generate_chunked` に `on_chunk(index,total,audio,sr)` 追加（未指定なら従来同挙動、fast path でも呼ぶ）
- `utils/tasks.py`: `GenerationTask` に completed/total、`update_generation_progress`/`get_generation_progress`（メモリのみ、DB書込みなし）
- `services/generation.py`: `_on_chunk` で進捗更新＋**effects_chain 未使用時**のみチャンク音声 wav を generations ディレクトリへ spool（`{genid}_chunk_{i}.wav`、失敗しても生成は継続）
- `routes/generations.py`: status SSE payload に `progress:{completed,total}`（task_manager メモリ参照のみ）
- `routes/audio.py`: `GET /audio/{id}/chunk/{i}`（UUID検証、404安全）
- frontend: `generationStore` に progress（startedAt 付き）、`useGenerationProgress` で受信、`HistoryTable` の Generating... に `(x/N) ~ETA left`（ETA はフロント側経過ベース）

### ab3241f 段階再生
- 新規 `LiveListenButton.tsx`: 履歴行（チャンク1件以上完了で表示）から spool を HTMLAudio で順再生→生成完了後は最終ファイルへ継続。spool 未達は6回リトライ後静かに停止（旧サーバー・effects プロファイルで安全）
- `client.ts` に `getGenerationChunkUrl`、`generationStore.livePlaybackIds` で完了時メインプレイヤー自動再生と二重再生を抑止

## Verification

- backend pytest: `backend/tests/test_chunked_tts.py` 5件 pass（コールバック順序/回数、fast path、None後方互換、trim→callback順、TaskManager progress 往復）。実行: `docs\ai\tmp\vbtest-venv`（numpy+pytest のみ）で `python -m pytest backend/tests/test_chunked_tts.py`
- backend 変更5ファイル `py_compile` pass
- frontend `tsc -p app/tsconfig.json --noEmit` clean、biome 新規指摘なし（既存6件は baseline）
- 互換性（実機）: 変更フロント埋め込みの release exe をインストール版バックエンド（旧・progress非送信）で起動 → UI正常表示、クローズで全終了 PASS・WEBVIEW2_CLEAN。**progress 未送信時は無表示で安全**（想定後方互換）
- **未確認**: 進捗実表示・spool 段階再生の実動作 — voicebox-server.exe（PyInstaller 513MB）が旧 backend のため。新 backend の効果確認には sidecar 再ビルド（torch環境必要）または dev モード（uvicorn backend + tauri dev）が必要

## 設計上のトレードオフ（既知）

- 段階再生中はチャンク間 crossfade なし（ハードカット）／effects chain は適用されない（完了後再生へ自然フォールバック）
- spool wav は generations ディレクトリに残留（retry で上書き、増分は小さい。cleanup は未実装）
- chunk ファイルの配信に DB チェックなし（UUID書式検証のみ。一時ファイル）

## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
