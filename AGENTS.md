# Voicebox (fork: BWDSF3104/voicebox)

jamiepine/voicebox v0.5.0 のフォーク。ローカル修正（Windowsシャットダウン修正、長文生成の進捗表示・段階再生）を保持する。

## 共通規約

言語・実装開始ゲート・ターミナル安全・コマンド実行ルール・正典ツール（`bin/`）・コード検証の共通条・Memory Bank 運用・commit message 規約は global 正典 `AGENTS.md`（`C:\Users\fujim\.config\kilo\AGENTS.md`）を参照。このファイルにはプロジェクト固有項目のみ記載する。

## Git

- `origin` = 上流 `https://github.com/jamiepine/voicebox.git`（fetch用、push禁止）
- `fork` = `https://github.com/BWDSF3104/voicebox.git`（作業ブランチの push 先）
- 作業ブランチ: `fix/windows-quit`（ベース `2bcb98d` = tag v0.5.0）。コミット済み: `96ff381` Windows OFF時全体終了 / `9208365` blocking-in-async修正+watchdog代替 / `bc2cb4a` 進捗表示 / `ab3241f` 段階再生
- upstream への PR 出すとき: `gh pr create -R jamiepine/voicebox --head BWDSF3104:fix/windows-quit`

## コード検証（本プロジェクト）

- **backend（Python）変更後**: `docs/ai/tmp/vbtest-venv` の python で `python -m pytest backend/tests/test_chunked_tts.py -v`。venv は numpy+pytest のみ。フルテストは torch 等の依存が入った venv が必要（未構築）
- **app（TS）変更後**: `npx tsc -p app/tsconfig.json --noEmit`、変更ファイルのみ `npx @biomejs/biome check <files>`（既存の biome error 6件は baseline、`--write` を全ファイルにかけると import が再整形され diff が膨らむので注意）
- **Rust（tauri/src-tauri）変更後**: `cd tauri/src-tauri && cargo check`。既存の keyboard_layout.rs 警告3件は baseline
- **実モデルロード・生成を伴う実機検証はユーザーの手動実施**（エージェントは自動生成テストしない。VRAM 逼迫で不安定なため）: `docs/ai/decisions/2026-11-15-manual-generation-verification.md`

## Build / 開発（Windows・bun 無し環境の実測手順）

- **フロント込みアプリ exe（`--no-bundle`）**: `cd tauri && npx tauri build --no-bundle --config '{"build":{"beforeBuildCommand":"npm run build"}}'`（実測: vite 15秒 + cargo release 2分）
  - **罠**: `cargo build --release` 直執行は tauri マクロが dev 扱いで devUrl（localhost:5173）を埋め込み webview が白画面になる。**必ず tauri CLI 経由**（debug の cargo build も同様）
- `npm install` はリポジトリルート（workspace 一式）。tauri の vite は `app/node_modules` を参照するため、root の `node_modules` への **junction** が必要: `New-Item -ItemType Junction -Path app\node_modules -Target <root>\node_modules`
- `bun` 未インストール（`bun.lock` 基準のリポジトリだが npm で通る。CI スクリプトの `bun run` 系は未使用）
- **sidecar（voicebox-server.exe）再ビルド**: `backend/build_binary.py`（PyInstaller、CUDA は --onedir / CPU は --onefile）。フル venv は `backend/venv`（py3.12、requirements.txt+pyinstaller 導入済み・2026-11-15 構築）。venv 済みのビルド実測 **8.2分**（CUDA onedir 1.4GB）。`scripts/build-server.sh` は bash 前提で Windows では使えない（requirements.txt は `PYTHONUTF8=1` 付きでないと pip が cp932 で読解失敗）
  - **罠（GPU 無効化）**: Windows で `pip install torch` の既定（PyPI）wheel は **CPU 版**。CUDA sidecar には必ず `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128`。ビルド後の確認: `backend/venv/Lib/site-packages/torch/lib` に `cublas64_12.dll` 等があり、ビルド成果物 `_internal/torch/lib` にも同梱されていること（GPU 無効だと `gpu_available:false`・CPU で激遅）

## テストハーネス（docs/ai/tmp/ に常備）

- `vb_close_test.py` — WM_CLOSE 送信→プロセス/ポート/残留検証（ctypes EnumWindows）。テスト用 env フック（`VB_TEST_KEEP/START/STOP`）は debug ビルド専用の一時仕込み（main.rs から除去済み）
- `check-webview2.ps1` / `check-windows.ps1` / `screenshot-main.ps1` — WebView2 残留 / ウィンドウ列挙 / メインウィンドウ撮像（ローカル視覚判定用）
- `vbtest-venv/` — numpy+pytest の最小 venv
- 注意: voicebox.exe は stdout を継承するため、PowerShell パイプラインで起動するとハングする（Start-Process やファイルリダイレクトで回避）

## 実機デプロイ状態

- インストール版 `C:\Program Files\Voicebox\voicebox.exe` は 2026-11-15 差し替え済み（バックアップ `voicebox.exe.bak`）＝ Windows 修正＋新フロント（進捗表示・段階再生 UI）入り
- CUDA sidecar（`%APPDATA%\sh.voicebox.app\backends\cuda\`）は 2026-11-15 に fork ソースの再ビルド版へ差し替え済み（バックアップ `cuda.bak-20261115`）＝ 新 backend（進捗 SSE・チャンク spool）稼働中。CPU 版 sidecar（`C:\Program Files\Voicebox\voicebox-server.exe`）は上流 0.5.0 のまま（CUDA が主経路のため未更新）
- 進捗表示・段階再生の UI 効果確認のみユーザー手動で残っている（2026-11-15）

## AI Memory Bank

- タスク: `docs/ai/tasks/`（2026-11-15 windows-quit-fix・longtext-streaming は Common_Operations 側から移行/コピー。経緯は `docs/ai/decisions/2026-11-15-docs-relocation-to-voicebox.md`）
- 決定: `docs/ai/decisions/`、既知問題: `docs/ai/known-issues/`（server watchdog の lifespan バグなど）
- `current-task.tsv` は task_manager 経由（voicebox ルートで `task_manager add/update`）
