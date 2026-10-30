@echo off
rem Removes Sysmon completely. Run as administrator.
setlocal
net session >nul 2>&1
if errorlevel 1 (
  echo Run as administrator.
  pause
  exit /b 1
)
if exist "%~dp0sysmon\Sysmon64.exe" (
  "%~dp0sysmon\Sysmon64.exe" -u
) else (
  "%SystemRoot%\Sysmon64.exe" -u
)
pause
