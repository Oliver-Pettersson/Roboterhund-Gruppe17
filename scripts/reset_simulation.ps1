$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RepoRoot

if (Test-Path "$HOME\.pixi\bin") {
    $env:PATH = "$HOME\.pixi\bin;$env:PATH"
}

Write-Host "[INFO] Sende Reset-Befehl an die Simulation..." -ForegroundColor Cyan
pixi run powershell -Command "cd workspace; . .\install\local_setup.ps1; ros2 topic pub --once /pren/reset std_msgs/msg/Empty '{}'"
