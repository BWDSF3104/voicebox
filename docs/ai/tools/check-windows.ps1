Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc l, IntPtr x);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(out bool v);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr x);
}
"@
$app = Get-Process voicebox -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $app) { 'NO_APP'; exit }
$titles = New-Object System.Collections.ArrayList
$cb = [W+EnumWindowsProc]{
  param($h, $x)
  $pid2 = 0
  [W]::GetWindowThreadProcessId($h, [ref]$pid2) | Out-Null
  if ($pid2 -eq $app.Id) {
    $len = [W]::GetWindowTextLength($h)
    if ($true) {
      $sb = New-Object Text.StringBuilder 512
      [W]::GetWindowText($h, $sb, 512) | Out-Null
      [void]$titles.Add("$pid2 :: $($sb.ToString())")
    }
  }
  return $true
}
[W]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
"app pid=$($app.Id) windows:"
$titles
$wv = Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" | Where-Object { $_.CommandLine -match 'voicebox' }
"webview2 procs: $(@($wv).Count)"
