# 案C 長文読本パイプライン: 分割粒度はリクエスト引数・入口は Stories Wizard（2026-11-19）

関連タスク: `tasks/2026-11-15-voicebox-audiobook-pipeline.md`

## 決定
1. **分割粒度は story に永続化せず、インポート時のリクエスト引数**（`paragraph` 既定／`chapter`／`chars`＋`max_chars`）。理由は 1 回限りの投入操作で、粒度は投入ごとに違い得るため。列を足すより引数が安い。
2. **入口は Stories タブの Wizard モーダル**（生成ページ側ではない）。完成物が story なので入口から story を作りに行く導線が単調。生成ページ側に置くと後から Stories へ紐付ける追加導線が必要になり二重管理。
3. **生成ファンアウトはバックエンドのバッチ endpoint**（`POST /stories/{id}/import-segments`）。フロントで `/generate` をループしない → item 数分だけ SSE/polling が増えるのを避ける。進捗は `GET /stories/{id}` を2秒ポーリング。
4. **リトライは既存 `POST /generate/{id}/retry` を流用**。同一 generation 行を更新するので story item の関連付けは無傷。新しい retry 機構を作らない。
5. **分割関数は新規 `utils/text_split.py` の純関数**。`chars` 粒度のみ既存 `chunked_tts.split_text_into_chunks` を再利用。段落/章は空行・見出し正規表現の単純ロジックで、chunk 分割（item 内 TTS 用・既存）とは層を分ける。

## 却下した案
- フロントで /generate ループ → 進捗購読が item 数線形、リトライ/順序の所有者がフロントになり脆弱。
- 章粒度のみ → item 数が粗くなり段単位の再生成粒度も粗い。段落を既定にし chapter/chars をオプション化することで解決。
- story へ分割粒度カラム追加 → 上記1の理由で過剰。
