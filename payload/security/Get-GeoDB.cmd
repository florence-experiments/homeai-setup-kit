@echo off
rem Downloads the free DB-IP Lite country + network-owner files (CC BY 4.0, no account).
rem They let alerts show a country/owner without sending the IP anywhere. Re-run monthly if you like.
setlocal
set "G=%~dp0geo"
if not exist "%G%" mkdir "%G%"
for /f %%m in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM"') do set "YM=%%m"
for /f %%m in ('powershell -NoProfile -Command "(Get-Date).AddMonths(-1).ToString('yyyy-MM')"') do set "PM=%%m"

for %%k in (country asn) do (
  echo Getting dbip-%%k-lite ...
  curl.exe -L --fail -s -S -o "%G%\dbip-%%k-lite-%YM%.csv.gz" "https://download.db-ip.com/free/dbip-%%k-lite-%YM%.csv.gz"
  if errorlevel 1 (
    del "%G%\dbip-%%k-lite-%YM%.csv.gz" >nul 2>&1
    echo   this month's file is not out yet - trying last month
    curl.exe -L --fail -s -S -o "%G%\dbip-%%k-lite-%PM%.csv.gz" "https://download.db-ip.com/free/dbip-%%k-lite-%PM%.csv.gz"
  )
)
dir /b "%G%\dbip-*.csv.gz" 2>nul
echo (The watcher loads the newest file of each kind when it starts.)
if not defined NOPAUSE pause
exit /b 0
