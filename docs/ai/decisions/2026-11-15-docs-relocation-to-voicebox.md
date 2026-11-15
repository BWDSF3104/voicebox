# Voicebox の記録を Common_Operations から本リポジトリへ移管

**日付**: 2026-11-15
**状態**: 確定

## 決定

voicebox に関する Memory Bank（タスク・既知問題・アーキテクチャ・検証手順）の正典を `S:\Documents\Kilo_Commons\voicebox\docs\ai\` に移管する。voicebox に `AGENTS.md` + `docs/ai/` を配置し、Kilo 管理プロジェクトとした（作業可能範囲に含む）。

## 経緯

- Windows シャットダウン修正（2026-11-15）は Common_Operations 起点で開始され、調査・記録が同プロジェクトの docs/ai に分散していた。voicebox 側の作業（ビルド・検証・デプロイ・sidecar 再ビルド）が主になりつつあり、記録先と作業地が乖離していた
- ユーザー指示「今後必要な情報などすべてvoicebox内に他プロジェクトフォルダと同形式でdocsにまとめて」により移管

## 移管内容と方針

- `docs/ai/AGENTS.md`（リポジトリ直下）: fork/remote、検証コマンド、ビルド手順と罠、デプロイ状態
- `docs/ai/architecture.md`: 実測ベースの構成・生成パイプライン・ローカル修正・検証状態サマリー
- `docs/ai/tasks/`: windows-quit-fix（Common_Operations 側は `task_manager end` でクローズ）・longtext-streaming（**Common_Operations 側で CUDA sidecar 再ビルドが進行中のため tsv 行は残置**。以後の更新は本リポジトリ側を正典とする旨を両ファイル先頭に注記）
- `docs/ai/known-issues/voicebox-server-watchdog-lifespan.md`: 移管（Common_Operations 側は削除）
- `docs/ai/tmp/`: テストハーネス（vb_close_test.py 等）をコピー。gitignore 済み

## 影響

- Common_Operations の current-task.tsv の voicebox 系行は以後新規登録しない。新規 voicebox タスクは `task_manager --root S:\Documents\Kilo_Commons\voicebox add` で行う
