# voicebox系WebView2プロセス残存チェック（tasklist名では捕まらないためCIMで確認）
$p = Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'voicebox' }
if ($null -eq $p) { 'WEBVIEW2_CLEAN' } else { 'WEBVIEW2_LEFT: ' + ($p.ProcessId -join ',') }
