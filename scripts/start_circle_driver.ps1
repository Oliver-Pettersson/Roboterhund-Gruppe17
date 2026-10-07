$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RepoRoot

if (Test-Path "$HOME\.pixi\bin") {
    $env:PATH = "$HOME\.pixi\bin;$env:PATH"
}

if (-not (Get-Command pixi -ErrorAction SilentlyContinue)) {
    Write-Error "Pixi could not be found. Please install Pixi first."
    exit 1
}

if (-not (Test-Path "$RepoRoot\workspace\install\local_setup.ps1")) {
    Write-Host "[INFO] Workspace not built yet. Running colcon build..." -ForegroundColor Cyan
    pixi run --manifest-path "$RepoRoot\pixi.toml" colcon build --merge-install
}

Write-Host "========================================================" -ForegroundColor Green
Write-Host " Starting circle_driver test node" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green

pixi run powershell -NoExit -Command "cd workspace; . .\install\local_setup.ps1; ros2 run pren_control circle_driver"
