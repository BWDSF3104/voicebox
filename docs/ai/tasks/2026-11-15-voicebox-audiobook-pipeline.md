# 案C: 長文読本パイプライン（テキスト取込→章分割→生成→story追加）

**Status**: 未着手
**Date**: 2026-11-15
**Next Action**: 章分割の粒度とUI入口の設計（decisions記録）→既存/generate+stories API再利用でパイプライン実装

## 意図 / 背景

小説等の長文を「本」として朗読化する audiobook パイプライン。観測により下地が大きいことを確認（詳細: `2026-11-15-voicebox-longtext-streaming.md` 追加検討）:
- Stories は多トラック・クリップ編集機として実装済み（`routes/stories.py`: timecode/reorder/trim/split/volume/混合書き出しWAV。`StoryItem.track`）
- item=generation なので **item ごとに別 profile（語り手/登場人物）を当てられる**
- フロントに連続再生（`useStoryPlayback`）と StoriesTab が実装済み
- 案A の進捗表示・段階再生（chunk spool）が章単位の生成/聴取にそのまま効く

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
