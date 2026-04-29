@echo off
chcp 65001 >nul 2>&1
title Warframe Trading Agent
cd /d "F:\giteeProject\warframe"
"F:\giteeProject\warframe\.venv\Scripts\python.exe" -B main.py
pause
