@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python start_web.py
pause
