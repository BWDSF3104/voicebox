# Voicebox 長文生成の進捗表示・段階再生（案A実装）

**Status**: 完了
**Date**: 2026-11-15
**Next Action**: なし（クローズ。後続は案C `2026-11-15-voicebox-audiobook-pipeline.md` へ）

> **このファイルが正典**（2026-11-15 移管、`decisions/2026-11-15-docs-relocation-to-voicebox.md` 参照）。Common_Operations 側に同名コピーが残っている場合、そちらは凍結なので更新内容は本ファイルへ反映すること。

## 引き継ぎサマリ（2026-11-19 時点）

**稼働中の現物**（全て fork `BWDSF3104/voicebox` ブランチ `fix/windows-quit`）:
- `C:\Program Files\Voicebox\voicebox.exe` = 11/18 0:48 ビルド（= 最終コミット `fe43727` 相当のフロント、custom-protocol 付き）。バックアップ: `voicebox.exe.bak-0851`（split_natural まで・スライダー無し）、`voicebox.exe.bak-1115`（案A前）、`voicebox.exe.bak`（4/25 原版）
- sidecar `%APPDATA%\sh.voicebox.app\backends\cuda` = cuda8（11/17 9:53、natural_min_chars + スプール込み）。バックアップ: `cuda.bak-0851`（split_natural まで）、`cuda.bak-0517`、他 3 種
- ユーザー実データ: `%APPDATA%\sh.voicebox.app\voicebox.db`（profile 2・generation 24・story 1）— **正典パスは known-issues/verify-backend-port-conflict-empties-gui.md**

**このブランチのコミット順**: `867fb43`(進捗開始時公開) → `bc2cb4a`/`ab3241f`(案A) → `85ed006`(F1+F2暴走ガード) → `132a8ab`(split_natural) → `6cfde64`(natural_minスライダー) → `205102b`(段階再生の自動開始) → `b98f299`(二重再生防止) → docs系。**全項目実機PASS済み**（二重再生防止も 2026-11-19 ユーザー確認で解消）。

**ビルド→デプロイ手順（実測済み・この順）**:
1. `& "..\app\node_modules\.bin\vite.cmd" build`（cwd=`tauri\`、bun 無し、約20秒）
2. `cargo build --release --features tauri/custom-protocol`（cwd=`tauri\src-tauri`、約2〜3分。**この feature 必須**、無いと devUrl 起動で接続拒否）
3. exe 交換: GUI 終了確認後 `Copy-Item target\release\voicebox.exe "C:\Program Files\Voicebox\voicebox.exe" -Force`
4. sidecar 変更時のみ: `& ".\venv\Scripts\python.exe" build_binary.py --cuda`（cwd=`backend\`、約16〜19分、ログは `docs\ai\tmp\`）→ GUI 終了確認後 `robocopy dist\voicebox-server-cuda "$env:APPDATA\sh.voicebox.app\backends\cuda" /MIR`
5. 検証: pytest（下記）+ 編集した全 py の `python -m py_compile` + backend 起動確認（**教訓: pytest では services/generation.py の構文エラーは検出不能**）

**テスト実行**: `& "S:\Documents\Kilo_Commons\Common_Operations\docs\ai\tmp\vbtest-venv\Scripts\python.exe" -m pytest backend/tests/test_chunked_tts.py -q`（cwd=voicebox、16件）。フロント型: `.\app\node_modules\.bin\tsc.cmd -p app/tsconfig.json --noEmit`。

**検証方針**: 生成・モデルロード系の動作確認はユーザー実機のみ（GPU 使用、`decisions/2026-11-15-manual-generation-verification.md`）。画面確認・API 確認はヘッドレスブラウザ + raw backend で agent 側で可能（モデル非ロード、`known-issues/verify-backend-port-conflict-empties-gui.md` のポート/data-dir 制約を必ず守る）。

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

### 進捗UIが沈黙する根本原因と修正（2026-11-16）
- 診断（ファイルログ＋`docs\ai\tools\vb-sse-repro.py`、REST側からSSE購読）: chunk 1/2 生成中の約5分間、SSEイベントが**全て `progress=None`**（480個）。`update_generation_progress` はチャンク**完了時**（`_on_chunk`）しか呼ばれず、生成中のフロントに `total` すら届かなかったのが原因。SSE接続・`start_generation` 登録・受信チェーンは全て正常と確認済み。ログに `status=... but no progress in task_manager for 30s` 警告も同一兆候。
- 修正: `chunked_tts.generate_chunked` に `on_chunk_start(i,total)` 追加（各チャンク生成**開始直前**に発火）、`services/generation.py` が `update_generation_progress(id, i, total)` を登録し**1個目の生成開始前に total を公開**。`completed` は正直な完了数維持 → フロント無変更で 1個目生成中 `(0/2)` 表示、2個目以降に ETA 表示。
- 検証: pytest **11/11**（新規 `test_on_chunk_start_fires_before_each_chunk`: 開始コールが当該チャンクの `backend.generate()` 前に発火すること）。変更2ファイル py_compile OK。生成実測はユーザー手動方針により未実施。
- ビルド・デプロイ: cuda5 sidecar（所要16.8分、ログ永続化＋progress修正込み）を `backends\cuda` へデプロイ、直前版は `cuda.bak-logs-cu130` へ保存。素exe起動健全（既定 port 8000 で起動完了ログ確認。17999 は GUI 引数指定）。
- commit `867fb43` fix: チャンク開始時にprogressを公開＋サーバーログファイル永続化（fork `fix/windows-quit`）。
- 別記録: HF Hub オンライン確認リトライでモデルロードに約100秒浪費 → `known-issues/hf-hub-online-retries-slow-model-load.md`

### 実機第2回テスト（2026-11-16 24:03〜24:51）と追加修正
- サーバー側は全機能稼働をログで確認: ロード14秒、`progress=0/2→1/2` 配信、spool chunk_0/1.wav 書出し、SSE切断なし
- **画面に何も出ない原因はインストール版 exe（11/15 11:15 ビルド）が案A実装前**（bc2cb4a 19:56・ab3241f 19:59 生成）だったため。Tauri のフロントは `tauri/vite.config.ts` の alias 経由で `app/src` を埋め込む構造
- 追加修正 commit `85ed006`:
  - F1 `useGenerationProgress.ts`: loading_model/generating 状態変化時に history を refetch（従来「Loading Model」ラベルが張り付く）
  - F2 `pytorch_backend.py`: 暴走生成ガード。実測で chunk1（410字）が既定 max_new_tokens=2048 まで繰り返しループし **43分**（同尺寸正常≈4分）→ `max_new_tokens=min(2048, 200+4×文字数)`・`repetition_penalty 1.05→1.15`
- デプロイ済み: exe（cargo再ビルド、F1込み、旧→`voicebox.exe.bak-1115`）、cuda6 sidecar（F2込み、旧→`cuda.bak-cu130b`）。検証: tsc clean・pytest 11/11・py_compile OK
- 環境変更: HFキャッシュを `J:\modelData\huggingface` へ移設（S:\側はジャンクション、`C:\Users\fujim\.cache\huggingface` 既定パス解決チェーン維持）。効果: ロード154秒→14秒、HFリトライ騒音消滅。コピー元100GBはゴミ箱へ
- ビルド手順の陷阱（2026-11-17 実測）: `cargo build --release` だけでは `tauri/custom-protocol` が無く、起動時に devUrl（`http://localhost:5173`）を開いて接続拒否。正しくは `cargo build --release --features tauri/custom-protocol`。再ビルド・再インストール済みで解消見込み（実機起動確認待ち）

### 自然境界優先分割オプション split_natural（2026-11-17 commit 132a8ab）
- ユーザー発案「上限まで詰め込むのではなく、自然に切れるならどんどん切る」。UI 既定 OFF（従来挙動）
- `chunked_tts.split_text_into_chunks(..., natural=True)`: 段落→文末の全境界で分割。120字未満の断片は直前（先頭なら次）と結合。`max_chunk_chars` は上限として尊重（超える chunks は出ない）
- 配線: GenerationRequest.split_natural → run_generation / inline生成 → GenerationSettings（DB列 + migrations で自動追加）→ 設定UI Toggle（チャンク上限の下）→ 生成formで送信。i18n 4ロケール対応
- テスト5件追加（文末毎分割/短断片結合/上限遵守/短文単chunk/既定OFF不変）、pytest 15/15。tsc clean、i18n JSON妥当性確認
- デプロイ済み: exe 8:51（custom-protocol付き）+ cuda7 sidecar。旧sidecarは `cuda.bak-0517`、cuda5系バックアップ（cuda.bak-cu130b）は容量確保のため削除

### 最小分割長スライダー natural_min_chars（2026-11-17 commit 6cfde64）
- ユーザー要望「もっと細かく切れる選択肢が欲しい、数値で調整したい」→ 自然分割ON時のみ出るスライダー（0〜500字・step10・既定120）。0で全文末分割
- 配線: split_text_into_chunks(..., natural_min) → generate_chunked(natural_min_chars) → run_generation/inline → GenerationRequest/SettingsResponse/Update → DB列 `natural_min_chars`（migration自動追加）→ UI Slider（crossfadeと同様の commit-on-release 保存）→ i18n 4ロケール
- 画面確認（モデル非ロード・ヘッドレスブラウザ、vite dev + raw backend 17493）: Toggle ON→スライダー出現→ドラッグ→`PUT /settings/generation` 250字永続→**リロード後もON+250字**（スクショ `docs/ai/tools/natural-min-slider.png`）。`/health` model_loaded:false・vram_used_mb:0.0（画面を開くだけでロードしないことを grep + 実測で確認: ロードは生成系3経路と `/models/load` ボタン経由のみ）
- **教訓**: pytest 16/16 でも `generation.py:91` のインデント崩れ（SyntaxError）は検出されなかった（テストが services/generation.py を import しないため）。バックエンド編集後は `python -m py_compile` と実起動確認を必須とすること。修正後 py_compile 全通過・backend/cuda8 起動 OK
- デプロイ済み: exe 9:34（`voicebox.exe.bak-0851` 退避）+ cuda8 sidecar 9:53（`cuda.bak-0851` 退避、ビルドログ `docs/ai/tmp/vb-build-cuda8.log`）。cuda8 起動時 settings API に `natural_min_chars:120` 乗ることを確認済み

### 実機第4回テスト: 段階再生は成功・最終チャンクで二重再生（2026-11-17 commit b98f299）
- 実機結果: 段階再生の自動開始 **成功**（完成チャンクから順次再生）。ただし最終チャンクの完成時点で「chunk_N 再生中 + 本編final自動再生」が二重なり
- 原因: 完了SSE時の抑止チェックが `livePlaybackIds.has(id)` ののみで、リトライ間隙（次chunk未spool）等で list から外れたタイミングだと本編 autoplay が走る。加えてリトライ上限が6回(15s)で、次chunkの生成待ちに不足するケースがある
- 修正: store に `livePlaybackEndedAt` を追加し、live停止後**30秒間は本編autoplayを抑止**（二重なりを timing によらず防止）。リトライ上限 6→24回（60s）で最終チャンク前のギャップを吸収。tsc clean・vite build・exe 00:48 インストール済み

### 実機第3回テスト結果 + 段階再生の自動開始（2026-11-17 commit 205102b）
- 実機結果（自然分割スライダー・進捗）: 825字→**14 chunks**、spool=on で chunk_0..13.wav が順次生成（`backend.log`・`generations/` 実測）、生成速度OK、`progress=n/14` がリアルタイム更新OK。**ただし段階再生（完成chunk順次再生）が開始しなかった**
- 原因: `LiveListenButton`（履歴行のスピーカーicon）は**従来手動ボタン**で、押すまで chunk_0 から再生を開始しない設計。UI的に気づきにくく「順次再生されない」に見えた。スプールも `/audio/{id}/chunk/{i}` endpoint も frontend URL も全て正常（欠陥は自動開始が無いことのみ）
- 修正: `autoplay_on_generate`（既定ON）がONのとき、**最初のチャンク完成（completed>=1）・total>1 で自動開始**。完成時は既存の `livePlaybackIds` 抑制でメインplayer autoplay と二重再生しない。手動トグルも従来どおり有効。tsc clean・vite build・exe 00:08 インストール済み
- 教訓: spool生成・配信は backend 側が完全動作していたため、段階再生の不具合は**必ず frontend 再生トリガ側**を疑うこと

## chunk 並行生成（生成速度向上）の調査と PoC（2026-11-17）

ユーザー要望「品質を下げず生成自体を速く」→ 分析結果（**実測前、コード grep まで**）:
- chunk 総生成時間はほぼ文字数比例で分割数に非依存（0.6秒/字は chunk160〜410字で同率）。細切れで増えるのは chunk 毎固定費（decode/trim/保存で1〜3秒）だけ = 数%
- **品質を一切変えない現実的な高速化は chunk 並行化のみ**（自己回帰デコードは帯域律速、3090 で 2〜3 並行 → wall 2〜2.5倍見込み、出力音質は決定論的に同一）。案C（章並行）でも同一機構を再利用できる
- 品質無保証（int8/AWQ 量子化）とモデル縮小は要件外。dtype は既に bf16（3.4GB/1.7B）で改善余地なし
- 再入安全性（grep 確認済み）: qwen_tts 0.1.1 の `Qwen3TTSModel` は `__init__` 以外に self 書き換え無し・global/lazy 状態無し。fork の `task_queue` は worker が `await task` で**現状複数生成は直列**（= 同一モデル同時推論は今回新領域）
- **本質リスクはライブラリ再入でなく単一CUDA stream**: 明示 `torch.cuda.Stream` 無しでは kernel が既定 stream に直列化し「速くならない」可能性。効き量は実測必須（multi-stream 前提）

**PoC スクリプト（ユーザーが起動するだけで測れる、2026-11-17 作成）** `docs/ai/tools/poc_parallel_tts.py` + 起動用 `poc_parallel_tts.cmd`（tmp ではない・git 管理）:
- フェーズ A直列 / B 2本同時(既定stream) / C 2本同時(個別stream)、同テキスト2本・同seed=42（『こころ』抜粋約100字×2）で wall・sec/char・RTF・wavハッシュ一致（identity）を記録
- 出力: `docs/ai/tmp/poc-parallel-tts-<stamped>.log` + 履歴追記 `poc-parallel-tts-results.json`。data-dir は GUI と同じ `%APPDATA%\sh.voicebox.app`（実 profile「モルガナ」使用）。書き込みは `docs/ai/tmp` と prompt キャッシュのみ
- agent 側検証済み: `POC_CHECK=1` 環境変数でモデルロード直前まで（実 profile 取得・`PyTorchTTSBackend device=cuda` 確認、VRAM 不使用）。**実測（A/B/C）はユーザー起動待ち・未実施**
- 読み取り: B≈A なら単一stream直列＝multi-stream必須、B<0.8×A なら gather だけで速い。B/C が A とハッシュ DIFFERENT ならモデル競合でなく**グローバルRNG共有**の想定（manual_seed が global）

**並行化の実装設計（未実装・指示待ち）**: `GenerationRequest/GenerationSettings` に `concurrent_chunks:int=1`（1=現行動作同一）→ chunked_tts 内で semaphore+gather。再生順は spool が index キー済みで完成順シャッフルに不変・先頭chunk優先で初回再生時間は現状維持。リスクは上記 stream + 同一インスタンス同時推論の可否。

## 設計上のトレードオフ（既知）

- 段階再生中はチャンク間 crossfade なし（ハードカット）／effects chain は適用されない（完了後再生へ自然フォールバック）
- spool wav は generations ディレクトリに残留（retry で上書き、増分は小さい。cleanup は未実装）
- chunk ファイルの配信に DB チェックなし（UUID書式検証のみ。一時ファイル）

## 追加検討（案D・案C・案B）2026-11-15 観測ベース

### 案D: 日本語分割の改善（費用小・全案の品質基盤）
実地テスト（`docs/ai/tools/probe_jp_split.py`、日本語小説文2092字、vbtest-venvで実行）:
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

- [x] `current-task.tsv` の参照行を削除（task_manager end 実施）
- [x] 解決した `known-issues/` を `archive/` へ移動（hf-hub-online-retries-slow-model-load.md — J:キャッシュ移設で解決）
- [x] `backlog.md` の完了項目を削除（該当なし）
