# 案C: 長文読本パイプライン（テキスト取込→章分割→生成→story追加）

**Status**: 実装完了・exe適用済み（生成系 end-to-end はユーザー実機確認待ち）
**Date**: 2026-11-15
**Next Action**: 実機: Stories→「長文インポート」→短文10段落で生成→全item完了→連続再生→1件retry確認→OKなら end＋案Bへ

## 意図 / 背景

小説等の長文を「本」として朗読化する audiobook パイプライン。観測により下地が大きいことを確認（詳細: `2026-11-15-voicebox-longtext-streaming.md` 追加検討）:
- Stories は多トラック・クリップ編集機として実装済み（`routes/stories.py`: timecode/reorder/trim/split/volume/混合書き出しWAV。`StoryItem.track`）
- item=generation なので **item ごとに別 profile（語り手/登場人物）を当てられる**
- フロントに連続再生（`useStoryPlayback`）と StoriesTab が実装済み
- 案A の進捗表示・段階再生（chunk spool）が章単位の生成/聴取にそのまま効く

## 実装計画（2026-11-19 確定・推奨案）

### 設計骨格（コード観測に基づく）
- 生成ファンアウト: `routes/generations.py:57 generate_speech` の「generation 行作成＋`enqueue_generation`（`services/task_queue.py:96`、直列キュー）」ブロックを共有ヘルパーへ抽出し、`POST /stories/{story_id}/import-segments`（新）が `[{text, profile_id, language?}]` を受けて段落毎に呼ぶ。**フロントで /generate をループしない**（item 数だけ SSE/ポーリングが増えるため却下。decisions 参照）
- 分割: 新規 `utils/text_split.py: split_for_story(text, granularity, chapter_regex, max_chars)`。`paragraph`=空行分割（既定）、`chapter`=見出し正規表現（既定 `^第[0-9一二三四五六七八九十百〇]+章`、不発時 paragraph に fallback）、`chars`=既存 `chunked_tts.split_text_into_chunks(max_chars)` を再利用。粒度は**インポート時のリクエスト引数**（story への列永続化なし — 1回限りの操作）
- story item 紐付け: 投入時に `story_items` を章順で作成（`track=0`、`generation_id` FK は pending 行でも成立）。音声完了後に duration が揃うので既存 `PUT /stories/{id}/items/times` で累積タイムコード確定。段の順序保証は投入順＝キュー直列処理順
- リトライ: 段落失敗時は既存 `POST /generate/{id}/retry`（同一 generation 行更新なので story item の関連付けは無傷のまま再試行できる）
- 進捗: フロントは SSE ではなく **`GET /stories/{id}` を2秒ポーリング**（item の generation status/duration）。`StoryItemDetail` に generation status が無い場合のみバックエンドに1フィールド追加
- キャスト割当: Wizard 表の行毎 profile ドロップダウン＋全体既定（語り手）。音声プロファイルは再生時差替不可なので**生成前確定必須**。同一段落内の話者切替はスコープ外

### 実装ステップ
1. `utils/text_split.py` ＋ `backend/tests/test_text_split.py`（段落/章/文字数の3粒度・空行連続・章見出し混在・上限境界。vbtest-venv で回せる純関数のみ）
2. バックエンド: generate_speech からヘルパー抽出（挙動不変。既存実機経路なので py_compile＋/generate 起動確認必須）＋ `POST /stories/{id}/import-segments`（items 一括作成＋fan-out、generation_id 一覧を返却）
3. フロント: StoriesTab ヘッダに「長文をインポート」→ Wizard モーダル4ステップ（テキスト投入/ファイル読込 → 粒度選択＋プレビュー表 → プロファイル割当 → 投入と進捗表示）。i18n 4ロケール
4. 検証: pytest（新規＋既存16件）→ 変更全 py の py_compile → dev/raw backend＋ヘッドレスで Wizard 画面確認（モデル非ロード可）→ 実機 end-to-end（ユーザー手動: 短文10段落→全 item 完了→連続再生→1件 retry）

### スケール上の注意（観測済み制約）
- 1生成50000字上限（`GenerationRequest.text`）→ 段落分割なら自然に内。入力ファイルは 2M 字で切る
- 生成は直列 0.6秒/字 → 10万字の本≈17時間。全体高速化は chunk 並行 PoC（`docs/ai/tools/poc_parallel_tts.py`）結果待ちの別案件。パイプライン自体は途中完成分から聴ける
- `enqueue_generation` の一括投入は DB 行＋メモリ上のジョブだけなので安全

## 調査結果 / 変更内容（2026-11-19 実装）

計画からの実装上の変更点:
- **generate_speech のヘルパー抽出は不要だった**: fan-out endpoint から `routes/generations.py` の `generate_speech(data, db)` を直接呼ぶ。FastAPI ルート関数はそのまま async 関数なので import して呼べる。進捗SSE・リトライ・暴走ガード等 `/generate` の全機能が自動的に同じ。**検証済み生成経路に手を入れない**ため安全で差分も最小。

バックエンド（commit 7511fb5 ほか）:
- `utils/text_split.py`: `split_for_story(text, granularity, chapter_regex, max_chars)`。`paragraph`（既定・1行=1段落）/`chapter`（見出し正規表現、既定`^第…章`、不発時 paragraph に fallback、不正正規表現も paragraph）/`chars`（既存 `chunked_tts.split_text_into_chunks` 再利用）
- `routes/stories.py`: `POST /stories/split-preview`（生テキスト→分割案、stateless、モデル非起動）と `POST /stories/{id}/import-segments`（segments を受けて段落毎に generate_speech→add_item。空/不在storyは 400/404 で fan-out 前に拒绝）
- `models.py`: `StoryItemDetail.generation_status`（進捗ポーリング対象、既定unknown）、`StorySplitPreviewRequest/Response`。`StoryItemDetail` に status があったので新規列・DB migration なし
- 時刻確定は投入時 placeholder（既存 add_item の自動末尾配置）。**再生順の確定はフロント完了時に既存 `PUT /items/reorder`（timecode再計算）を import 順で1回呼ぶ**（新規 endpoint 追加なし）

フロント（commit 予定）:
- `StoryImportDialog.tsx`（新規・StoriesTab）: 本のタイトル＋テキスト投入→粒度セレクト→プレビュー→item毎 profile ドロップダウン→生成開始。進捗は `GET /stories/{id}` を2秒ポーリング（`generation_status` 完了+失敗>=total で reorder 後トースト）。fan-out 完了後はサーバー側生成でも dialog を閉じられる
- `StoryList.tsx`: ヘッダに「長文インポート」按钮 → dialog 起動。client.ts に `previewStorySplit`/`importStorySegments`、型に `generation_status`、i18n 4ロケール

## Verification（2026-11-19）

- pytest `test_text_split.py` 新規7件 pass（3粒度・空行除去・章見出し保持・不発/不正正規表現 fallback・chars 上限）。既存 `test_chunked_tts.py` と合わせて **23 passed**
- 変更 backend py すべて py_compile pass
- backend 起動（`backend\venv`、uvicorn）: `/stories/split-preview` 章粒度で2 segment 返却、`import-segments` は空body→400、不在story→404（**いずれも fan-out 前拒绝でモデル非起動**）確認
- フロント `tsc --noEmit` clean、新規 `StoryImportDialog.tsx` biome clean（既存 StoryList/StoryContent の baseline error は据え置き）、i18n 4ロケール JSON妥当性 pass、`vite build` 成功（16.3s）
- ヘッドレスブラウザ（vite dev 5173 + raw backend 17493・孤立 data-dir）: Stories→「長文インポート」→テキスト投入→プレビューで「5項目に分割」＋行毎 profile ドロップ表示→**ボイス未設定で「生成開始」押下も fan-out せずトースト警告**（モデル非起動）。証拠 `docs/ai/tools/audiobook-import-wizard.png`
- exe ビルド（`cargo build --release --features tauri/custom-protocol` 2m12s）・`C:\Program Files\Voicebox\voicebox.exe` へ適用（旧→`voicebox.exe.bak-1119a`）。**sidecar cuda9 再ビルド＋robocopy /MIR 必須**（cuda8=11/17ビルドは新ルート不在でインストール版は 404 になる。ログ `docs/ai/tmp/vb-build-cuda9.log`、完了後に本行へ結果記録）
- **未確認（ユーザー手動）**: 実プロファイルでの生成 fan-out・連続再生・item リトライ

## 依存 / 順序

- 案D（`2026-11-15-voicebox-jp-chunk-split.md`）が先だと章内分割の品質が上がって有利（非依存ではある）
- 実施順は D → C → 案B（`2026-11-15-voicebox-stream-tts.md`）

## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
