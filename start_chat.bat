@echo off
chcp 65001 >nul 2>&1
title Warframe Trading Agent - Chat
cd /d "F:\giteeProject\warframe"
echo ========================================
echo   Warframe 本地交易 Agent - 对话模式
echo ========================================
echo.
"F:\giteeProject\warframe\.venv\Scripts\python.exe" -B -c "from main import configure_console_encoding; configure_console_encoding(); from warframe_agent.agent import WarframeAgent; from main import handle_chat; handle_chat(WarframeAgent())"
pause
