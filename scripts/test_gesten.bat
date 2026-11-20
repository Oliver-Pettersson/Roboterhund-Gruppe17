@echo off
setlocal
REM T2 Gestenerkennung fuer den Testnachweis (Bericht Kapitel 7). Doppelklick genuegt.
cd /d "%~dp0\.."

if exist "%USERPROFILE%\.pixi\bin" set "PATH=%USERPROFILE%\.pixi\bin;%PATH%"
where pixi >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] Pixi nicht gefunden. Installation:
    echo powershell -ExecutionPolicy Bypass -c "irm -useb https://pixi.sh/install.ps1 | iex"
    pause
    exit /b 1
)

if "%PREN_KEIN_BUILD%"=="1" goto start
echo [INFO] Baue den ROS-2-Workspace ...
call pixi run cmd /c "cd workspace && colcon build --merge-install"
if not errorlevel 1 goto start
echo [FEHLER] Build fehlgeschlagen. Laeuft noch die Simulation? Dann zuerst beenden.
if not exist "workspace\install\local_setup.bat" (
    pause
    exit /b 1
)
choice /c JN /m "Mit dem bestehenden Build weitermachen"
if errorlevel 2 exit /b 1

:start

pixi run cmd /c "cd workspace && call .\install\local_setup.bat && cd ..\testnachweis && python t2_gesten.py %*"
echo.
echo Ergebnisse liegen in testnachweis\ergebnisse
pause
