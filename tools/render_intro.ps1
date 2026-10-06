# 重新渲染介绍图（HTML -> PNG），需要 Edge 或 Chrome
# 用法: powershell -ExecutionPolicy Bypass -File tools\render_intro.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$assets = Join-Path $root 'assets'
$tmp = Join-Path $env:TEMP 'qrsuite-shot'

$browser = @(
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { Write-Error '未找到 Edge / Chrome'; exit 1 }

New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$jobs = @(
  @{ h = 'intro-vertical.html'; o = 'QRSuite-v2-介绍图.png';       w = 1200; hh = 1650 },
  @{ h = 'intro-square.html';   o = 'QRSuite-v2-介绍图-方版.png';   w = 1080; hh = 1080 },
  @{ h = 'og.html';             o = 'QRSuite-v2-og.png';           w = 1200; hh = 630  }
)
foreach ($j in $jobs) {
  $out = Join-Path $assets $j.o
  if (Test-Path $out) { Remove-Item $out -Force }
  $url = 'file:///' + ((Join-Path $assets $j.h) -replace '\\', '/')
  & $browser --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 `
             --window-size="$($j.w),$($j.hh)" --user-data-dir="$tmp" --screenshot="$out" $url 2>$null | Out-Null
  Start-Sleep -Seconds 3
  if (Test-Path $out) { Write-Host ("OK   {0}  {1:N0} KB" -f $j.o, ((Get-Item $out).Length / 1KB)) }
  else { Write-Host "FAIL $($j.o)" }
}
Write-Host "输出目录: $assets"
