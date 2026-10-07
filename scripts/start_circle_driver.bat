@echo off
setlocal

cd /d "%~dp0\.."

REM Ensure pixi from standard user install is in PATH
if exist "%USERPROFILE%\.pixi\bin" (
    set "PATH=%USERPROFILE%\.pixi\bin;%PATH%"
)

REM Check for Pixi
where pixi >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Pixi could not be found. Please install Pixi first:
    echo powershell -ExecutionPolicy Bypass -c "irm -useb https://pixi.sh/install.ps1 | iex"
    pause
    exit /b 1
)

REM If workspace has not been built yet, build it automatically
if not exist "workspace\install\local_setup.bat" (
    echo [INFO] Workspace not built yet. Running colcon build...
    call pixi run cmd /c "cd workspace && colcon build --merge-install"
    if errorlevel 1 (
        echo [ERROR] colcon build failed.
        pause
        exit /b 1
    )
)

echo ========================================================
echo  Starting circle_driver test node
echo ========================================================
pixi run cmd /c "cd workspace && call .\install\local_setup.bat && ros2 run pren_control circle_driver"

if errorlevel 1 (
    echo [ERROR] circle_driver exited with an error.
    pause
)
