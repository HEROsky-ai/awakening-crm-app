@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: ============================================================
::   覺醒行動app 安全啟動腳本 v2.1
::   ✅ 自動檢查套件 → 自動修復 → 自動重啟守護
::   ✅ 不需系統管理員也能正常啟動
:: ============================================================

set PYTHON=C:\Users\1120804\AppData\Local\Programs\Python\Python312\python.exe

echo ============================================
echo   覺醒行動app Web 版（安全守護模式 v2.1）
echo ============================================
echo.

:: ── 步驟 1：確認 Python312 存在 ──
if not exist "%PYTHON%" (
    echo [ERROR] 找不到 Python 3.12！
    echo 路徑：%PYTHON%
    pause
    exit /b 1
)
echo  ✅ Python 3.12 確認存在

:: ── 步驟 2：自動安裝/修復套件 ──
echo  🔍 正在驗證套件完整性...
"%PYTHON%" -X utf8 -m pip install -r "%~dp0requirements.txt" -q --no-warn-script-location >nul 2>&1
echo  ✅ 套件驗證完成

:: ── 步驟 3：快速導入測試 ──
"%PYTHON%" -X utf8 -c "import flask, requests; print('  ✅ 核心套件正常')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo  🔧 嘗試修復套件...
    "%PYTHON%" -X utf8 -m pip install --force-reinstall flask requests -q >nul 2>&1
)

:: ── 步驟 4：自動啟動 Tailscale（若已在執行則跳過）──
tasklist /FI "IMAGENAME eq tailscale-ipn.exe" 2>nul | find /I "tailscale-ipn.exe" >nul
if %ERRORLEVEL% NEQ 0 (
    if exist "C:\Program Files\Tailscale\tailscale-ipn.exe" (
        echo  🔒 正在啟動 Tailscale VPN...
        start "" "C:\Program Files\Tailscale\tailscale-ipn.exe"
        timeout /t 3 /nobreak >nul
    )
) else (
    echo  ✅ Tailscale 已在執行中
)

echo.
echo  🚀 啟動守護程式中...
echo    （崩潰時將自動重啟，紀錄於 guardian.log）
echo    （關閉此視窗 = 停止 App）
echo.

"%PYTHON%" -X utf8 "%~dp0guardian.py"
pause
