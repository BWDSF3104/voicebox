# docs/ai/tools — 恒久調査・検証スクリプト

`docs/ai/tmp/` は 7 日無更新で正典 `archive_memory_bank.py` により消えるため、再利用する調査スクリプトはここに置く（git 管理）。実行は概ね `backend\venv\Scripts\python.exe` または vbtest-venv、cwd はプロジェクトルート。

| スクリプト | 目的 | 参照 |
|---|---|---|
| `poc_parallel_tts.py` / `poc_parallel_tts.cmd` | chunk 並行生成の速度 PoC（A直列/B同時/C multi-stream）。**実測はユーザー起動**。`POC_CHECK=1` でモデル非ロード起動確認のみ先跑可能。ログ/JSON は `docs/ai/tmp/` に吐く | tasks/2026-11-15-voicebox-longtext-streaming.md「chunk 並行生成の調査と PoC」 |
| `inspect_dbs.py` | voicebox.db コピー（本物/旧/backend\\data 等）の read-only 集計。プロファイル・生成が消えた系の一次調査 | known-issues/verify-backend-port-conflict-empties-gui.md |
| `probe_jp_split.py` | 日本語分割挙観の実地観測（案D 評価のソース） | 同タスク 案D |
| `vb-sse-repro.py` | 進捗 SSE を REST 側から購読して再現（進捗UI不表示の診断に使用） | 同タスク 2026-11-16 診断 |
| `vb_close_test.py` / `check-webview2.ps1` / `check-windows.ps1` / `screenshot-main.ps1` | Windows シャットダウン検証ハーネス（WM_CLOSE 残留検証・WebView2 残留・ウィンドウ列挙・撮像） | tasks/2026-11-15-windows-quit-fix.md |
| `natural-min-slider.png` | natural_min スライダー画面検証の証拠スクショ | 同タスク 案A スライダー |
