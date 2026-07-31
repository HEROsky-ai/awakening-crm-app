@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   覺醒行動app Web 版（自動重啟守護模式）
echo ============================================
echo.

:: ── 自動啟動 Tailscale（若已在執行則跳過）──
set TAILSCALE="C:\Program Files\Tailscale\tailscale-ipn.exe"
tasklist /FI "IMAGENAME eq tailscale-ipn.exe" 2>nul | find /I "tailscale-ipn.exe" >nul
if %ERRORLEVEL% NEQ 0 (
    echo  🔒 正在啟動 Tailscale VPN...
    start "" %TAILSCALE%
    timeout /t 3 /nobreak >nul
    echo  ✅ Tailscale 已啟動
) else (
    echo  ✅ Tailscale 已在執行中，略過啟動
)
echo.

echo  啟動中...（崩潰時將自動重啟，紀錄於 guardian.log）
echo.
python -X utf8 guardian.py
pause
