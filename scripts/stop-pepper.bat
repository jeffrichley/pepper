@echo off
REM Stop Pepper: kill all managed processes
echo Stopping Pepper...
taskkill /IM claude.exe /F 2>nul
taskkill /IM python.exe /F 2>nul
echo Pepper stopped.
