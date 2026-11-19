# Storiesサイドバーヘッダーのはみ出し重なり修正

**Status**: 進行中
**Date**: 2026-11-20
**Next Action**: コミット済み(85669e4)。要: tauri再ビルド+exe差し替え後の目視確認

## 意図 / 背景

ユーザー提供スクショ（2026-11-19）: Stories画面の左ペインで「新しいストーリー」金ボタンがペイン右端で切断されて右ペインと重なって見え、タイトル「ストーリー」が潰れて表示されていない。

## 調査結果 / 変更内容

- 左ペイン幅: `StoriesTab.tsx:14` の `max-w-[360px]`。
- `StoryList.tsx` のヘッダーはタイトル行（`ListPaneTitleRow`）内にボタン2個＋その下に検索を置く構造（`ListPaneHeader` は absolute・z-20、`ListPane.tsx:31`）。
- 実測ハーネス（vite 経由、Tailwind 実クラス）: 見出し内幅 328px に対し ボタン列 min-content = 332px（長文インポート 156 + 新しいストーリー 168 + gap）→ ペイン右端を約 20px 超えて `overflow-hidden` でクリップ＝はみ出し。タイトル `h2`（truncate・flex子）は 32px まで潰れてテキスト消滅＝重なりの見え方。
- ボタンラベルの CJK 幅で EN 前提レイアウトが溢れるのが根本原因。1行目と2行目（検索）だけでは収まらない。
- 修正案（実装未着手）: StoryList のヘッダーを「タイトル行 → ボタン行（右寄せ）→ 検索」の3行化、`ListPaneScroll` に `pt-36`、`ListPaneHeader` に `bg-background`（ HEADER 高さ増でカードがヘッダー下を透けるのを防止）。ボタンアイコンの `mr-2` は buttonVariants 側 `gap-2` と二重なので除去（幅 16px 節約）。ハーネス修正版で適合確認済み（actions 右端 376 ≤ ペイン 392）。
- 影響範囲: StoryList のみ。EffectsTab / CapturesTab は同一ヘッダー構造だが件数が少なく元々収まるため無変更。
- 実装（13:20）: `StoryList.tsx` をヘッダー3行化（タイトル行 → `ListPaneActions className="mb-2 justify-end"` → 検索）、`ListPaneHeader className="bg-background"`、`ListPaneScroll className="pt-36"`、ボタンアイコンの `mr-2` 除去。変更はこのファイルのみ（diff 24行）。

## Verification

- `npx tsc -p app/tsconfig.json --noEmit` → 合格（出力なし）。経過 約25秒。
- `npx @biomejs/biome check app/src/components/StoriesTab/StoryList.tsx` → organizeImports・format の2件だが、diff 非該当のファイル全体に対する既存 baseline（AGENTS.md 記載の biome error 群。`--write` は import 再整形で diff 膨張のため不使用）。
- Tailwind 実クラス・ハーネス計測: 修正前 actions 右端 412 > ペイン右端 392（はみ出し再現）→ 修正後 376 ≤ 392（適合、16px 余裕）。ハーネス `docs/ai/tmp/story-pane-repro.html` / `story-pane-fixed.html`。
- 未確認: 実機exeでの目視（要再ビルド）。ヘッダー不透明化によるリストカードのスクロール時フェード消失は意図した挙動。

## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
