# 検証用 backend の 17493 掴み/誤 data-dir で GUI のデータが消えたように見える（dev環境）

**種別**: ローカル known-issue（fork 開発環境。ユーザーデータは消失していない）
**日付**: 2026-11-17
**関連タスク**: `tasks/2026-11-15-voicebox-longtext-streaming.md`

## 症状
GUI（インストール版 voicebox.exe）を開いた際、作成済みボイスプロファイルと生成音声が**すべて空**に表示された。「消えた」と報告された。

## 実際の原因（データは消失していない）
agent が段階再生の画面検証中に、**GUI と同じ既定ポート 17493** に検証用バックエンド（`--data-dir ...\docs\ai\tmp\vbverify-data` や `backend\data` 等の**別 DB**）を起動したまま、ユーザーが GUI を起動した瞬間に当たった。GUI は「自分の本物 DB」でなく「agent の検証用・空のバックエンド」に繋がったため空に見えた。voicebox 単体では **Tauri が渡す data-dir に応じて複数 `voicebox.db` が共存**する:

| パス | 内容 | 用途 |
|---|---|---|
| `%APPDATA%\sh.voicebox.app\voicebox.db` | profile 2 / generations 24 / story 1 | **本物（GUI が接続）** |
| `%APPDATA%\sh.voicebox.app\data\voicebox.db` | 旧・未使用（voice_profiles 無し） | 混同注意 |
| `voicebox\backend\data\voicebox.db` | 0件（`--data-dir` 指定で生成） | agent 検証用・空 |
| `voicebox\docs\ai\tmp\vbverify-data\voicebox.db` | 0件 | agent 検証用・空 |

GUI exe は `--data-dir %APPDATA%\sh.voicebox.app --port 17493` で sidecar を起動する（`main.rs` で確認）。`config.get_db_path()` は `_data_dir/voicebox.db`。

## 確認・復旧手順（データ無傷の判定法）
1. 競合プロセス調査: `Get-CimInstance Win32_Process | ? { $_.Name -match 'voicebox' } | select CommandLine` → `--data-dir` が本物か、17493 二重起動でないか
2. 本物 DB を read-only 集計（`docs/ai/tmp/inspect_dbs.py` に実装）: profile 2 / generation 24 を確認、消失なし
3. agent 検証用プロセスを全停止 → port 17493 解放 → GUI 再起動で正常表示（API `/profiles`=2件、`/history` items=24 で確認済み）

## 教訓（再発防止）
- 検証用 backend を立てる時は既定 17493 を避けるか、検証終了後に必ずプロセス停止・port 解放を確認してから報告する
- 「見えた/消えた」は DB 実物の read-only 集計で先に確認し、削除・書き換え系操作に先立たせない
