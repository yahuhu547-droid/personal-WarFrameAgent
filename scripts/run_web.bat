@echo off
cd /d "%~dp0\.."
if not exist logs mkdir logs
"%CD%\.venv\Scripts\uvicorn.exe" warframe_agent.web.app:app --host 127.0.0.1 --port 8000 >> "%CD%\logs\web_runtime.log" 2>&1
