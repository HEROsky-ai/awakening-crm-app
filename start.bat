@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: ============================================================
::   覺醒行動app 安全啟動腳本 v2.0
::   ✅ 自動檢查套件 → 自動修復 → 自動重啟守護
:: ============================================================

set PYTHON="C:\Users\1120804\AppData\Local\Programs\Python\Python312\python.exe"
set APP_DIR=%~dp0

echo ============================================
echo   覺醒行動app Web 版（安全守護模式 v2.0）
echo ============================================
echo.

:: ── 步驟 1：確認 Python312 存在 ──
if not exist C:\Users\1120804\AppData\Local\Programs\Python\Python312\python.exe (
    echo ❌ 找不到 Python 3.12！
    echo    請確認已安裝 Python 3.12：
    echo    C:\Users\1120804\AppData\Local\Programs\Python\Python312\python.exe
    pause
    exit /b 1
)
echo  ✅ Python 3.12 確認存在

:: ── 步驟 2：自動安裝/修復套件 ──
echo  🔍 正在驗證套件完整性...
%PYTHON% -X utf8 -m pip install -r requirements.txt -q --no-warn-script-location 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo  ⚠️  套件安裝失敗，嘗試使用備用方式安裝...
    %PYTHON% -X utf8 -m pip install flask flask-login bcrypt requests python-dateutil -q
)
echo  ✅ 套件驗證完成

:: ── 步驟 3：快速導入測試（0.1 秒確認不會崩） ──
%PYTHON% -X utf8 -c "import flask, requests; print('  ✅ 核心套件正常')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo  ❌ 核心套件驗證失敗！嘗試強制重新安裝...
    %PYTHON% -X utf8 -m pip install --force-reinstall flask requests -q
    %PYTHON% -X utf8 -c "import flask" 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo  ❌ 修復失敗，請聯絡支援。
        pause
        exit /b 1
    )
)

:: ── 步驟 4：自動啟動 Tailscale（若已在執行則跳過）──
set TAILSCALE="C:\Program Files\Tailscale\tailscale-ipn.exe"
tasklist /FI "IMAGENAME eq tailscale-ipn.exe" 2>nul | find /I "tailscale-ipn.exe" >nul
if %ERRORLEVEL% NEQ 0 (
    if exist %TAILSCALE% (
        echo  🔒 正在啟動 Tailscale VPN...
        start "" %TAILSCALE%
        timeout /t 3 /nobreak >nul
        echo  ✅ Tailscale 已啟動
    )
) else (
    echo  ✅ Tailscale 已在執行中
)

echo.
echo  🚀 所有檢查通過，啟動守護程式...
echo    （崩潰時將自動重啟，紀錄於 guardian.log）
echo.

%PYTHON% -X utf8 guardian.py
pause
