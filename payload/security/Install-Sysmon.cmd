@echo off
rem Installs or updates Microsoft Sysmon with the sysmon-modular config + HomeAI additions.
rem Run as administrator (Install-All.cmd calls this for you).
setlocal
set "HERE=%~dp0"
set "PY=%~dp0..\..\python\python.exe"
set "T=%HERE%sysmon"
set "CFG_URL=https://github.com/olafhartong/sysmon-modular/releases/download/configs-a45dedb13a43/sysmonconfig.xml"
set "CFG_SHA=64bec37ba849c5f2934a55d2a29e7ddfae46a30d56f7f2908d1f8a454898797e"
cd /d "%HERE%"

net session >nul 2>&1
if errorlevel 1 (
  echo Run as administrator.
  goto fail
)
if not exist "%T%" mkdir "%T%"

echo Downloading Sysmon from Microsoft Sysinternals...
curl.exe -L --fail -s -S -o "%T%\Sysmon.zip" https://download.sysinternals.com/files/Sysmon.zip
if errorlevel 1 goto fail
tar -xf "%T%\Sysmon.zip" -C "%T%"
if not exist "%T%\Sysmon64.exe" goto fail

echo Checking Microsoft signature...
powershell -NoProfile -Command "(Get-AuthenticodeSignature '%T%\Sysmon64.exe').Status" | find "Valid" >nul
if errorlevel 1 (
  echo Signature is NOT valid - stopping. Nothing was installed.
  goto fail
)
powershell -NoProfile -Command "(Get-AuthenticodeSignature '%T%\Sysmon64.exe').SignerCertificate.Subject" | find "O=Microsoft Corporation" >nul
if errorlevel 1 (
  echo Not signed by Microsoft - stopping. Nothing was installed.
  goto fail
)
echo Signature OK - Microsoft Corporation.

echo Downloading sysmon-modular config (pinned release)...
curl.exe -L --fail -s -S -o "%T%\sysmonconfig.xml" "%CFG_URL%"
if errorlevel 1 goto fail
certutil -hashfile "%T%\sysmonconfig.xml" SHA256 | find /i "%CFG_SHA%" >nul
if errorlevel 1 (
  echo Config file hash does not match the pinned value - stopping.
  goto fail
)
echo Config hash OK.

"%PY%" "%HERE%merge_sysmon_config.py" "%T%\sysmonconfig.xml" "%HERE%sysmon-override.xml" "%T%\sysmonconfig-merged.xml"
if errorlevel 1 goto fail

sc query Sysmon64 >nul 2>&1
if errorlevel 1 (
  echo Installing Sysmon...
  "%T%\Sysmon64.exe" -accepteula -i "%T%\sysmonconfig-merged.xml"
) else (
  echo Sysmon already installed - updating its config...
  "%T%\Sysmon64.exe" -c "%T%\sysmonconfig-merged.xml"
)
if errorlevel 1 goto fail

sc query Sysmon64 | find "RUNNING" >nul
if errorlevel 1 goto fail
echo Sysmon is running.
if not defined NOPAUSE pause
exit /b 0

:fail
echo Sysmon install FAILED.
if not defined NOPAUSE pause
exit /b 1
