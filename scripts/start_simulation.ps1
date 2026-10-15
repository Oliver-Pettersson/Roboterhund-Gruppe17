$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RepoRoot

if (Test-Path "$HOME\.pixi\bin") {
    $env:PATH = "$HOME\.pixi\bin;$env:PATH"
}

if (-not (Get-Command pixi -ErrorAction SilentlyContinue)) {
    Write-Error "Pixi could not be found. Please install Pixi first: powershell -ExecutionPolicy Bypass -c `"irm -useb https://pixi.sh/install.ps1 | iex`""
    exit 1
}

if (-not $env:WEBOTS_HOME) {
    if (Test-Path "$env:LOCALAPPDATA\Programs\Webots") {
        $env:WEBOTS_HOME = "$env:LOCALAPPDATA\Programs\Webots"
    } elseif (Test-Path "$env:ProgramFiles\Webots") {
        $env:WEBOTS_HOME = "$env:ProgramFiles\Webots"
    }
}

Write-Host "[INFO] Building ROS 2 workspace..." -ForegroundColor Cyan
pixi run --manifest-path "$RepoRoot\pixi.toml" colcon build --merge-install

Write-Host "=========================================================================" -ForegroundColor Green
Write-Host " Starting PREN Integrated Simulation Pipeline (Gruppe 17)" -ForegroundColor Green
Write-Host " Webots R2025a + Bridge + Search Driver + Control Panel + Voice + Gestures" -ForegroundColor Green
Write-Host "=========================================================================" -ForegroundColor Green

pixi run powershell -NoExit -Command "cd workspace; . .\install\local_setup.ps1; ros2 launch pren_bringup simulation.launch.py"
