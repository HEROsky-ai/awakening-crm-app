@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   覺醒行動app Web 版
echo ============================================
echo.
echo  啟動中...
echo.
python -X utf8 web_app.py
pause
