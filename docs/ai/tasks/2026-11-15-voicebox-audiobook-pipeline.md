# 案C: 長文読本パイプライン（テキスト取込→章分割→生成→story追加）

**Status**: 計画作成完了（実装開始指示待ち）
**Date**: 2026-11-15
**Next Action**: 実装開始指示→計画ステップ1（utils/text_split.py＋テスト）から。設計は decisions/2026-11-19-audiobook-import-design.md

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

## 調査結果 / 変更内容

（着手時に記入。実装方針: 足りないのは入口だけ — テキスト取込→章/段落分割→item毎に `/generate` キュー投入→story へ自動追加。新推論経路は不要。章分割粒度・UI入口（新規タブかStories内インポートか）・章の再試行/停止は設計段階で decisions に記録）

## Verification

（未実施。予定: 章分割ロジックのユニットテスト、パイプライン end-to-end は dev モードまたは sidecar 再ビルド版で実機確認）

## 依存 / 順序

- 案D（`2026-11-15-voicebox-jp-chunk-split.md`）が先だと章内分割の品質が上がって有利（非依存ではある）
- 実施順は D → C → 案B（`2026-11-15-voicebox-stream-tts.md`）

## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
