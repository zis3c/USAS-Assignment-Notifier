# Assignment Notifier — PowerShell launcher
# Usage: .\run.ps1

$ErrorActionPreference = "Stop"
chcp 65001 >$null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$checkEmoji = [char]::ConvertFromUtf32(0x2705)
$rocketEmoji = [char]::ConvertFromUtf32(0x1F680)

# Note: .env is loaded automatically by python-dotenv within the application code.
Write-Host "$checkEmoji  Launcher initialized (Encoding: UTF8)" -ForegroundColor Green


# Ensure data directory
New-Item -ItemType Directory -Force -Path "data" | Out-Null

Write-Host "$rocketEmoji  Starting Assignment Notifier Bot..." -ForegroundColor Cyan
python bot.py
