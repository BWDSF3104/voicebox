# HF Hub オンライン確認リトライでモデルロードが遅延

- 発見日: 2026-11-16
- 状態: 未対応（非必須）

## 症状

モデルキャッシュ済みでも TTS モデルロードに約 154 秒かかり、そのうち約 100 秒は
huggingface.co への HEAD リクエストリトライ（DNS 解決失敗 `getaddrinfo failed`、
オフライン環境）で浪費されている。

## 証拠

`%APPDATA%\sh.voicebox.app\logs\backend.log` 2026-11-15 23:57:19 → 23:59:53
- `Qwen3-TTS-12Hz-1.7B-Base/resolve/main/config.json` HEAD × 5 リトライ
- 同様に `generation_config.json`・`custom_generate/generate.py` でも各 5 リトライ
- `qwen_tts` の config 読込自体はキャッシュから成功している（ロード自体は完走）

## 想定修正

サーバー起動時（`backend/server.py` 早期）に `HF_HUB_OFFLINE=1`（または
`local_files_only`）を設定。ただし初回ダウンロード時にオフラインだと失敗するため、
キャッシュ存在時のみ有効化する等の判定が必要。本番生成の実験はユーザー手動のため、
効果検証には GUI 生成が必要。
