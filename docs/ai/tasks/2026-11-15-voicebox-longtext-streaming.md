# Voicebox 長文生成の進捗表示・段階再生（案A実装）

**Status**: 進行中（cu128 sidecar デプロイ済み・ユーザー実機確認待ち）
**Date**: 2026-11-15
**Next Action**: Voicebox 起動→ユーザーが長文生成で進捗表示(x/N・ETA)＋段階再生（LiveListen）を実機確認→OKなら end＋アーカイブ

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
- **未確認**: 進捗実表示・spool 段階再生の実動作 — ユーザー実機確認待ち（方針: 生成系検証は手動、`decisions/2026-11-15-manual-generation-verification.md`）

### cu128 sidecar 再ビルド（2026-11-15 完了）
- 根本原因: venv の torch が PyPI 既定の CPU 版 → `pip install torch torchaudio --index-url .../whl/cu128` で `2.11.0+cu128`・`cuda.is_available()=True`（RTX 3090）へ。`PYTHONUTF8=1` 必須（日本語ロケール cp932 エラー回避）
- `build_binary.py --cuda`: `--collect-all nvidia.*` 追加で CUDA DLL 収集。所要 **18.4分**、成果物 **5.0GB**（`dist\voicebox-server-cuda`、`_internal\torch\lib\cublas64_12.dll` 確認）
- デプロイ: 旧 `backends\cuda`（0.5.0）→ `cuda.bak-050` へリネーム保存、新ビルドを robocopy、`cuda-libs.json`（version cu128-v1）書き戻し
- 本ビルドには案Dの分割改善（段落優先・端数再配置）も含む（`chunked_tts.py` 更新後に assemble 実行済み）

## 設計上のトレードオフ（既知）

- 段階再生中はチャンク間 crossfade なし（ハードカット）／effects chain は適用されない（完了後再生へ自然フォールバック）
- spool wav は generations ディレクトリに残留（retry で上書き、増分は小さい。cleanup は未実装）
- chunk ファイルの配信に DB チェックなし（UUID書式検証のみ。一時ファイル）

## 追加検討（案D・案C・案B）2026-11-15 観測ベース

### 案D: 日本語分割の改善（費用小・全案の品質基盤）
実地テスト（`docs/ai/tmp/probe_jp_split.py`、日本語小説文2092字、vbtest-venvで実行）:
- 800字上限では **文末「。」境界で正しく分割**（784/785/523字。日本語文末対応は生きている）
- **末尾ミニチャンクの弱点**: 2000字指定で末尾 **109字の端数chunk** が単独生成される（文末境界優先のみでチャンク数最適化なし）
- 改行（段落/場面転換）優先分割は無い。引用符「」内も普通に切る（TTS上は支障なし）
改善案: ①末尾チャンクが小さい時（例250字未満）は前chunkと結合 or 平均再配置 ②改行優先の段落分割 ③`max_chunk_chars` は GenerationRequest に既存フィールド→フロントUI設定として露出可能（バックエンド改修なしで長文用2000字運用可）

### 案C: 長文読本パイプライン（物語→聴く）（費用中・B非依存）
観測: Stories は**実在する多トラック・クリップ編集機能**（`routes/stories.py`: timecode/reorder/trim/split/volume/**export mixed wav**、StoryItem.track あり、frontend `StoriesTab` + `useStoryPlayback` で連続再生も実装済み）。item=generation なので **itemごとに別profile（語り手/登場人物）の音声を当てられる**。
欠けているのは入口だけ: 「長文テキスト取り込み→章/段落に分割→itemごとに生成ジョブ投入→storyへ自動追加」。実装は既存 `/generate` キュー（案A進捗付き）+ 既存 stories API の再利用で、**新しい推論経路は不要**。生成済みitemから章順に聴く/章単位リトライも既存部品で成立。

### 案B: 真のストリーム出力（費用大・BはC/D後）
観測: 8エンジン全て `generate()` で**音声を一括返す**バッチIF。ストリームIFは無い（kokoro内含まれず）。ただし qwen 系は公式 `qwen_tts` ライブラリ（Qwen3-TTS-12Hz 系、ストリーム合成設計持ち）— 検証要。
実態: 案Aで「チャンク単位の疑似ストリーム（spool+順次再生）」は既にある。案Bの本体価値は**初回再生までの待ち時間をチャンク1個分(数十秒)→数秒**へ縮めること。
選択肢: ①（低コスト・エンジン非依存）長文の**最初のチャンクだけ小さく**分割（例: 先頭200字→以降800字）— `max_chunk_chars` 拡張と案A spoolで即実現 ②qwen エンジン限定のエンジン級真ストリーム（PCMフラグメントyield）— IF追加+エンジン分岐で高コスト、効果は②のみ数秒以内

### 実施順序案
D（小修正）→ C（読本パイプライン、Aの進捗/段階再生がそのまま効く）→ B①（先頭chunk縮小、ほぼおまけ）→ B②（qwenストリーム、必要性を実測してから）

## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
