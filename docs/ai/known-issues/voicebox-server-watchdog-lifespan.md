# voicebox v0.5.0 サーバー側 parent-pid watchdog が起動しない（Windows）

**Date**: 2026-11-15
**Status**: 未解決（本番コード側は Rust の RunEvent::Exit taskkill で暫定代替済み / タスク 2026-11-15-voicebox-windows-quit-fix）
**対象**: upstream jamiepine/voicebox v0.5.0（`backend/server.py`）

## 症状

Tauri アプリ（voicebox.exe）が終了しても voicebox-server(-cuda).exe が self-terminate しない。`--parent-pid` を渡していても発火せず、`logs/watchdog.log` も作られない。

## 原因

`backend/app.py:100` 前後で FastAPI を `lifespan=lifespan` 付きで構築しているため、`backend/server.py:278` の `@app.on_event("startup")` に登録した `_start_parent_watchdog` が呼ばれない（Starlette/FastAPI はカスタム lifespan を渡すと on_startup/on_shutdown を無視する。ログにも `DeprecationWarning: on_event is deprecated` が出る）。テストログで watchdog ログファイル未作成＋panic痕跡を確認済み。

## 暫定回避（済み）

Rust 側 `RunEvent::Exit`（keep_running=false 時）で自前起動/voicebox名サーバーの PID を taskkill（コミット 9208365）。server_pid に外部サーバーは保存しないため誤殺しない。

## 恒久対策案

server.py の watchdog 起動を lifespan（`compose_lifespan` に追加、あるいは app 生成後ではなく lifespan 内で起動）へ移行。upstream への Issue/PR 候補。
