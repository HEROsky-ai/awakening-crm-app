@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   覺醒行動app Web 版（自動重啟守護模式）
echo ============================================
echo.
echo  啟動中...（崩潰時將自動重啟，紀錄於 guardian.log）
echo.
python -X utf8 guardian.py
pause
