$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $python -m pip install -r "facebook_ads_monitor\requirements.txt"

if (-not (Test-Path "data\facebook_token.txt")) {
  New-Item -ItemType Directory -Force -Path "data" | Out-Null
  Write-Host "请把 Meta Access Token 写入 data\facebook_token.txt，然后重新运行 start.ps1。"
  exit 1
}

& $python -m facebook_ads_monitor.server --host 127.0.0.1 --port 8788

