# Voicebox v0.5.0.0 Windows終了不具合の修正

> **移管（2026-11-15）**: 正典は本ファイル（Common_Operations 側はクローズ済み・`decisions/2026-11-15-docs-relocation-to-voicebox.md` 参照）。

**Status**: 完了
**Date**: 2026-11-15
**Next Action**: ユーザーが通常運用でON設定時のホットキー音声・MCP接続を確認（OFF閉じの完全終了は確認済み）

## 意図 / 背景

Windows で Voicebox v0.5.0.0 のメインウィンドウを閉じても voicebox.exe / voicebox-server.exe / WebView2 が残存する。
作業コピーは `S:\Documents\Kilo_Commons\voicebox`（ブランチ `fix/windows-quit`、ベースライン 2bcb98d = tag v0.5.0）。
Keep server running ON のバックグラウンド動作は維持、macOS/Linux の既存動作は変更しない。

## 調査結果 / 変更内容

**原因**（v0.5.0 ソースの直接確認）:
- `main.rs` の `CloseRequested` は `prevent_close()` → フロントへ `window-close-requested` → フロントが条件付き `stop_server` → `window-close-allowed` → Rust は **メインウィンドウのみ** `window.close()`。
- setup 時に生成される非表示 `dictate` WebViewWindow が残り続けるため、Tauri のイベントループが生きたまま → voicebox.exe と WebView2 が終了しない。
- voicebox.exe が生きているため backend の parent-pid watchdog（`backend/server.py:102`）が発火せず、HTTP `/shutdown`（`backend/routes/health.py:35`）が不発だと voicebox-server.exe もポート 17493 を占有したまま残る。
- upstream main では同箇所が `finish_main_window_close()` に整理済み（Linux のみ `app.exit(0)`、#1040）。根本原因は同一と確認。
- MCP は `voicebox-server.exe` 内 `/mcp`（`backend/app.py:110`）マウント。`voicebox-mcp` stdio shim は MCP クライアントが起動するプロセスで、本修正では終了対象にしない。

**変更**（`tauri/src-tauri/src/main.rs` のみ）:
- `finish_main_window_close(&Window)` を追加: Windows かつ `keep_running_on_close == false` なら dictate pill を `destroy()` して `app.exit(0)`（RunEvent::Exit のクリーンアップは走る）、それ以外従来どおり `window.close()`。
- 呼び出し箇所 3 点を置換: emit 失敗パス / `window-close-allowed` 受信パス / 5 秒タイムアウトパス。

## 追加した修正（コミット 9208365, 変更1ファイル main.rs のみ）

実行中に実測で判明した Windows 固有の第2の原因:
- `stop_server` / `start_server` 再利用分岐が async ランタイム上で `reqwest::blocking` を呼び panic（`Cannot drop a runtime in a context where blocking is not allowed`）→ POST /shutdown が一度も届かず、OFF で閉じてもサーバー生存。`spawn_blocking` 化 + Windows で stop 失敗時 `taskkill /PID /T /F` フォールバック。
- `RunEvent::Exit`（keep_running=false 時）でも自前起動/voicebox名サーバーの PID を taskkill（Unix の既存 kill と対称化）。サーバー側の parent-pid watchdog は **実バイナリで起動しない**（backend/app.py がカスタム lifespan を渡すため server.py の `@app.on_event("startup")` が無視される。テストログで panic と DeprecationWarning を確認。known-issues 参照）。server_pid は自前起動/voicebox名プロセスのみ保存なので外部起動サーバーは誤殺しない。

## 検証結果（debugビルド+実voicebox-server-cuda.exe 0.5.0, 2026-11-15）
テストハーネス: `docs/ai/tmp/vb_close_test.py`（WM_CLOSE送信→プロセス/ポート/残留チェック、VB_TEST_* envフックでサーバー起動・stop相当を注入。フックはmain.rsから巻き戻し済み、コミット済みコードは clean）。

| 項目 | 内容 | 結果 |
|---|---|---|
| A1 | OFF+自前起動サーバー+フロント相当stop→クローズ→voicebox.exe終了 | PASS（"Shutdown request sent"→全終了） |
| A2 | 同上→voicebox-server.exe終了 | PASS（POST /shutdown 200→ポート解放） |
| A3 | 同上→WebView2終了 | PASS（WEBVIEW2_CLEAN, CIM cmdline判定） |
| A4 | 同上→ポート17493解放 | PASS |
| A5 | 再起動でサーバー再利用・増殖なし | PASS（"Found existing voicebox-server on port 17493 (PID: N), reusing it"） |
| B1 | ON→クローズ→アプリ継続生存 | PASS（mainAlive=True） |
| B2 | ON→サーバー継続（/health 200 healthy） | PASS |
| B3 | ON→MCPエンドポイント生存（/mcp/ が406=要Acceptヘッダで応答、接続生存） | PASS（実音声/MCP操作は未実施） |
| B4 | ON→再起動時に既存サーバー再利用 | PASS（A5と同一実行で確認） |
| C1 | サーバー起動なしでOFFクローズ→即終了 | PASS |
| C2 | stop呼ばず→app終了→Exitのtaskkillでサーバー殺害→ポート解放 | PASS |
| C3 | CloseRequested emitタイムアウト（5秒）→終了経路 | PASS（"Window close timeout, closing anyway"→exit） |
| C4 | 外部起動サーバー（/health応答stub, 非voicebox名）+OFFクローズ→app終了・外部サーバー生存 | PASS（ポート開いたまま、voicebox系プロセスなし） |
| 対照 | 無修正v0.5.0（2bcb98d）で同操作→voicebox.exe+WebView2残存を再現 | 確認済み（RESULT=MAIN_STILL_ALIVE） |

ビルド: `cargo check` / `cargo build` ともに Finished（既存keyboard_layout警告3件のみ、変更ファイル由来の警告なし）。frontendDist/binariesはcargo通し用のスタブ（tauri/dist\index.html, src-tauri/binaries/*.exe=gitignore済）。

## 検証追加（2026-11-15 02:20 JST）: 差し替え用 production release ビルド

- ビルド: `npx tauri build --no-bundle --config '{"build":{"beforeBuildCommand":"npm run build"}}'`（tauri/ で実行。`npm install` 後、`app/node_modules` が無いため `app\node_modules` に root node_modules への junction が必要だった）
- **注意点**: `cargo build --release` 直執行は tauri マクロが dev 扱いで devUrl（localhost:5173）を埋め込み、起動すると webview が「localhost 接続拒否」白画面になる。必ず **tauri CLI 経由**でビルド（debug の cargo build が白画面だった原因もこれ。当時の close 挙動検証は Rust 側のみなので影響なし）
- sidecar: `C:\Program Files\Voicebox\voicebox-server.exe`（490MB）と `voicebox-mcp.exe` を `target\release\` に同名コピー（plugin-shell 2.3.4 の sidecar 解決は exe と同ディレクトリの `<name>.exe`、target triple なし）
- 実機結果（release\voicebox.exe）: 起動→フロント実コードが自動で sidecar 起動（**16.6秒**で :17493 open, /health 200）→スクショで実UI確認（モデル一覧=サーバー連携済み）→ WM_CLOSE → **アプリ・サーバー・WebView2 全終了・ポート解放・WEBVIEW2_CLEAN（RESULT=PASS）**
- 成果物: `S:\Documents\Kilo_Commons\voicebox\tauri\src-tauri\target\release\voicebox.exe` を `C:\Program Files\Voicebox\voicebox.exe` と差し替えで「修正入りインストール版」として使用可（差し替えはユーザーの手動・要管理者権限。バックアップ推奨。updater 有効時は上書きされうる）

## 実施済み（2026-11-15 11:20 JST）: インストール版への差し替え

- 修正コミットの保存先: フォーク `BWDSF3104/voicebox`（remote名 `fork`）へ `fix/windows-quit`（2bcb98d ベース、96ff381 + 9208365）を push 済み。origin は上流 jamiepine/voicebox のまま。

- `C:\Program Files\Voicebox\voicebox.exe` を release 版へ差し替え（バックアップ: 同ディレクトリ `voicebox.exe.bak`、元 exe とハッシュ一致確認）。sidecar は据え置き。
- 差し替え後インストール版で end-to-end 再検証: フロント自動でサーバー起動 → 実UI → WM_CLOSE でアプリ・サーバー・WebView2 全終了（RESULT=PASS、ポート解放）。

## 未検証

- ON時の実際の音声入力・ホットキー・MCPクライアント接続の実操作確認。
- macOS/Linux 動作（変更なし、テスト環境なし）。


## 完了時 Memory Bank 操作

- [ ] `current-task.tsv` の参照行を削除
- [ ] 解決した `known-issues/` ファイルを `known-issues/archive/` へ `mv`（該当する場合）
- [ ] `backlog.md` の完了項目を削除（該当する場合）
