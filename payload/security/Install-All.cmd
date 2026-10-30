@echo off
rem Security Watcher - one-time install. Right-click > Run as administrator.
rem Does: Sysmon + config, offline geo files, bigger Security log, file baseline, logon task, start.
setlocal
set "HERE=%~dp0"
set "PY=%~dp0..\..\python\python.exe"
set "NOPAUSE=1"
cd /d "%HERE%"

net session >nul 2>&1
if errorlevel 1 (
  echo Please right-click Install-All.cmd and choose "Run as administrator".
  pause
  exit /b 1
)
if not exist "%PY%" (
  echo HomeAI's Python was not found at %PY% - run HomeAI setup first
  pause
  exit /b 1
)
if not exist "%HERE%logs" mkdir "%HERE%logs"
if not exist "%HERE%state" mkdir "%HERE%state"

echo.
echo === 1 of 5: Sysmon ===
call "%HERE%Install-Sysmon.cmd"
if errorlevel 1 (
  echo Sysmon step failed - see above. The watcher still works without it, with less detail.
)

echo.
echo === 2 of 5: offline country / network-owner files ===
call "%HERE%Get-GeoDB.cmd"

echo.
echo === 3 of 5: Security event log size 64 MB ===
wevtutil sl Security /ms:67108864

echo.
echo === 4 of 5: HomeAI file baseline ===
if exist "%HERE%state\baseline-hashes.csv" (
  echo Existing baseline kept: %HERE%state\baseline-hashes.csv
) else (
  "%PY%" "%HERE%wctl.py" baseline
)

echo.
echo === 5 of 5: start at logon + start now ===
call "%HERE%Install-Watcher-Task.cmd"

echo.
echo Done. Next: double-click Test-Watcher.cmd (no admin needed).
pause
