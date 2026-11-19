Add-Type -AssemblyName System.Windows.Forms,System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W2 {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc l, IntPtr x);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr x);
}
"@
$app = Get-Process voicebox -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $app) { 'NO_APP'; exit }
$cands = New-Object System.Collections.ArrayList
$cb = [W2+EnumWindowsProc]{ param($h,$x)
  $p=0; [W2]::GetWindowThreadProcessId($h,[ref]$p) | Out-Null
  if ($p -eq $app.Id -and [W2]::IsWindowVisible($h) -and [W2]::GetWindowTextLength($h) -eq 0) {
    $r = New-Object W2+RECT
    if ([W2]::GetWindowRect($h,[ref]$r)) { if (($r.R-$r.L) -gt 400) { [void]$cands.Add($h) } }
  }
  return $true }
[W2]::EnumWindows($cb,[IntPtr]::Zero) | Out-Null
if ($cands.Count -eq 0) { 'NO_MAIN_WIN'; exit }
$h = $cands[0]
$r = New-Object W2+RECT; [W2]::GetWindowRect($h,[ref]$r) | Out-Null
$bmp = New-Object Drawing.Bitmap ($r.R-$r.L), ($r.B-$r.T)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
$out = 'S:\Documents\Kilo_Commons\Common_Operations\docs\ai\tmp\voicebox_main.png'
$bmp.Save($out)
"SAVED $out $($r.R-$r.L)x$($r.B-$r.T)"
