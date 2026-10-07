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

REM Detect WEBOTS_HOME if not already explicitly set
if not defined WEBOTS_HOME (
    if exist "%LOCALAPPDATA%\Programs\Webots" (
        set "WEBOTS_HOME=%LOCALAPPDATA%\Programs\Webots"
    ) else if exist "%ProgramFiles%\Webots" (
        set "WEBOTS_HOME=%ProgramFiles%\Webots"
    )
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
echo  Starting PREN Webots Simulation (Webots + ROS Bridge)
echo ========================================================
pixi run cmd /c "cd workspace && call .\install\local_setup.bat && ros2 launch pren_bringup simulation.launch.py"

if errorlevel 1 (
    echo [ERROR] Simulation exited with an error.
    pause
)
