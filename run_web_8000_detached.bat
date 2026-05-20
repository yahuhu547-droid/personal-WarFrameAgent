@echo off
cd /d "%~dp0"
echo Starting Warframe web service on http://127.0.0.1:8000
echo Working directory: %CD%
echo Started at %DATE% %TIME% > web_manual_8000.log
.venv\Scripts\python.exe -m uvicorn warframe_agent.web.app:app --host 127.0.0.1 --port 8000 >> web_manual_8000.log 2>&1
echo Exited at %DATE% %TIME% with code %ERRORLEVEL% >> web_manual_8000.log
pause
