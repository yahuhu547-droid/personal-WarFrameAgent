@echo off
cd /d "%~dp0\.."
start "" "%CD%\.venv\Scripts\uvicorn.exe" warframe_agent.web.app:app --host 127.0.0.1 --port 8000
