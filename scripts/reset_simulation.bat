@echo off
setlocal
cd /d "%~dp0\.."
if exist "%USERPROFILE%\.pixi\bin" set "PATH=%USERPROFILE%\.pixi\bin;%PATH%"

echo [INFO] Sende Reset-Befehl an die laufende Simulation...
pixi run cmd /c "cd workspace && call .\install\local_setup.bat && ros2 topic pub --once /pren/reset std_msgs/msg/Empty \"{}\""
