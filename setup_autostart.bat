@echo off
chcp 65001 >nul
echo ============================================
echo   覺醒行動app 開機自動啟動設定
echo ============================================
echo.

set APP1_DIR=C:\Users\1120804\Desktop\安麗行動App
set APP2_DIR=C:\Users\1120804\Desktop\安麗行動App_宜舫
set PYTHON="C:\Users\1120804\AppData\Local\Programs\Python\Python312\python.exe"

:: ── 設定「安麗行動App（東東）」自動啟動 ──
echo  🔧 設定「安麗行動App」開機自動啟動...
schtasks /Delete /TN "覺醒CRM_東東" /F >nul 2>&1
schtasks /Create /TN "覺醒CRM_東東" ^
    /TR "\"%APP1_DIR%\start.bat\"" ^
    /SC ONLOGON ^
    /DELAY 0001:00 ^
    /RL HIGHEST ^
    /F >nul
if %ERRORLEVEL% EQU 0 (
    echo  ✅ 安麗行動App 開機自動啟動設定成功
) else (
    echo  ⚠️  設定失敗，請用系統管理員身分執行此腳本
)

:: ── 設定「安麗行動App_宜舫」自動啟動 ──
echo  🔧 設定「安麗行動App_宜舫」開機自動啟動...
schtasks /Delete /TN "覺醒CRM_宜舫" /F >nul 2>&1
schtasks /Create /TN "覺醒CRM_宜舫" ^
    /TR "\"%APP2_DIR%\start.bat\"" ^
    /SC ONLOGON ^
    /DELAY 0001:30 ^
    /RL HIGHEST ^
    /F >nul
if %ERRORLEVEL% EQU 0 (
    echo  ✅ 安麗行動App_宜舫 開機自動啟動設定成功
) else (
    echo  ⚠️  設定失敗，請用系統管理員身分執行此腳本
)

echo.
echo ============================================
echo  ✅ 設定完成！
echo  重新開機後，兩個 App 將自動在背景啟動。
echo  （啟動延遲：東東 1 分鐘，宜舫 1.5 分鐘）
echo ============================================
echo.

:: 顯示目前已設定的排程任務
echo  📋 目前排程清單：
schtasks /Query /TN "覺醒CRM_東東" /FO LIST 2>nul | findstr "工作名稱\|狀態\|下次執行"
schtasks /Query /TN "覺醒CRM_宜舫" /FO LIST 2>nul | findstr "工作名稱\|狀態\|下次執行"

pause
