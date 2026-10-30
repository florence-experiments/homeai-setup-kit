@echo off
rem Built by Florence for the community.
rem HomeAI Setup Kit - double-click to install HomeAI. No admin rights needed.
title HomeAI Setup
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kit\setup.ps1" %*
echo.
pause
