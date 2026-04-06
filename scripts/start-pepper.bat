@echo off
REM Start Pepper: Claude Code session with channel and Discord MCP servers
REM Claude Code spawns both MCP servers automatically via .mcp.json.

set PEPPER_DIR=%~dp0..

echo Starting Pepper...
echo   Claude Code will spawn:
echo     - pepper-channel (TypeScript, message router)
echo     - pepper-discord (Python, Discord bot + scheduler)
echo.

if not defined CLAUDE_CODE_GIT_BASH_PATH (
    set CLAUDE_CODE_GIT_BASH_PATH=E:\Program Files\Git\bin\bash.exe
)

cd /d "%PEPPER_DIR%"
claude --dangerously-load-development-channels server:pepper-channel
