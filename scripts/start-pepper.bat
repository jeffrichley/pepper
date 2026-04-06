@echo off
REM Start Pepper: Claude Code session with channel + Discord bot

set PEPPER_DIR=%~dp0..
set PID_DIR=%PEPPER_DIR%\.pids
if not exist "%PID_DIR%" mkdir "%PID_DIR%"

echo Starting Pepper...

REM Set Git Bash path for Claude Code
if not defined CLAUDE_CODE_GIT_BASH_PATH (
    set CLAUDE_CODE_GIT_BASH_PATH=E:\Program Files\Git\bin\bash.exe
)

REM Start Claude Code with channel
cd /d "%PEPPER_DIR%"
start /B "" claude --dangerously-load-development-channels server:pepper-channel

REM Wait for channel server
echo   Waiting for channel server...
:wait_loop
timeout /t 1 /nobreak >nul
curl.exe -s http://localhost:8788/health >nul 2>&1
if errorlevel 1 goto wait_loop
echo   Channel server ready!

REM Start Discord bot
cd /d "%PEPPER_DIR%\integrations\discord"
start /B "" uv run python bot.py

echo.
echo Pepper is running!
echo   Channel server: http://localhost:8788
echo.
echo Stop with: Ctrl+C or close this window
pause
