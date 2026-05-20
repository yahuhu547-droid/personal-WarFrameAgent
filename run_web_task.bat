@echo off
cd /d F:\giteeProject\warframe
.venv\Scripts\uvicorn.exe warframe_agent.web.app:app --host 127.0.0.1 --port 8000 --log-level debug > web_task.out.log 2> web_task.err.log
