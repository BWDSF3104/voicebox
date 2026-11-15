# Voicebox アーキテクチャと現状（2026-11-15 実測ベース）

## 全体構成

```
voicebox/
├── app/            React フロント（実UI本体。tauri の vite から参照される）
├── tauri/          Tauri v2 アプリ（src/ は薄いラッパ、src-tauri/src/main.rs が本体ロジック）
│   ├── src-tauri/binaries/  sidecar 配置先（build.rs がチェック）
│   └── dist/                フロントビルド出力（tauri.conf frontendDist: ../dist）
├── backend/        Python バックエンド（FastAPI :17493、voicebox-server.exe 化される）
│   ├── routes/     API ルート（generations/audio/speak/stories/tasks/events…）
│   ├── services/   generation.py（生成ジョブの単一入口 run_generation）、task_queue.py
│   ├── utils/      chunked_tts.py（長文分割）、tasks.py（タスク進捗メモリ）
│   └── build_binary.py      PyInstaller 定義（CUDA=--onedir / CPU=--onefile）
└── backend/mcp_*   MCP（FastMCP を /mcp にマウント + stdio シム voicebox-mcp）
```

- 実行時: voicebox.exe が sidecar `voicebox-server.exe`（exe と同ディレクトリ、名前は `<name>.exe`、target triple なし — plugin-shell 2.3.4 の解決規約）を shell().sidecar() で起動。フロント（WebView2）が REST/SSE を叩く
- CUDA モデル実体は `%APPDATA%\sh.voicebox.app\backends\cuda`（ランタイムダウンロード、exe 外）
- 設定・履歴 DB・音声は `%APPDATA%\sh.voicebox.app`（dev/debug/インストール版で共有）

## 生成パイプライン（長文）

1. フロント `POST /generate` → ジョブ投入（`services/task_queue.enqueue_generation`）→ status SSE `/generate/{id}/status`（**サーバー側1秒DBポーリング**で payload 配信）
2. `run_generation` → `utils/chunked_tts.generate_chunked`（既定800字/チャンク、文末優先分割 `。！？` 対応、チャンク間 crossfade 既定50ms）→ 全チャンク完了後に連結WAV保存
3. フロントは完成時に履歴 refetch + オートプレイ（idle時のみ、agent発話は除く）

### ローカル追加（fix/windows-quit）
- `on_chunk` コールバック → `utils/tasks.TaskManager` にメモリ進捗（DB書込みなし）→ status SSE に `progress:{completed,total}` → フロント `HistoryTable` に `x/N (~ETA)` 表示
- effects_chain 未使用時はチャンクWAVを generations ディレクトリへ spool → `GET /audio/{id}/chunk/{i}` → フロント `LiveListenButton` が順次再生（段階再生）→ 完了後最終音声へ継続

## Windows 終了処理（ローカル修正済み）

- OFF（keep server running off）+ メインウィンドウクローズ → `finish_main_window_close` → `app.exit(0)`（hidden dictate ウィンドウ対策）。`RunEvent::Exit` で自前起動 sidecar を taskkill（**サーバー側の parent-pid watchdog はカスタム lifespan のせいで起動しない** — known-issues 参照）
- ON 時は背景継続（既存動作）。外部起動サーバーは server_pid に保存しないので誤殺しない

## 検証状態サマリー（詳細は tasks/ の2ファイル）

- Windows OFF クローズ完全終了: 実機 PASS（タスク完了、インストール版反映済み）
- ON 背景継続: 状態 PASS（ホットキー実操作のみユーザー任せ）
- 進捗表示・段階再生: コード+pytest+typecheck 完了、fork push 済み。**sidecar 再ビルド後に実機確認**（再ビルド見積もり30〜60分、venv+torch が支配的）

## 既知の落とし穴（再現しないために）

- `cargo build --release` 直執行 → devUrl 指向で白画面。**tauri CLI 経由必須**（AGENTS.md）
- voicebox.exe は stdout 継承 → PowerShell パイプライン起動でハング
- Windows の `taskkill /PID x /T /F` は子プロセスツリーごと殺す（WM_CLOSE 相当の graceful とは別の経路。RunEvent::Exit は graceful の後段）
- biome の `--write` を既存ファイルにかけると import 再整形で diff が膨らむ
