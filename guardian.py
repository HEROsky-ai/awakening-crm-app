# -*- coding: utf-8 -*-
"""
guardian.py - 覺醒行動app 自動重啟守護程式 v2.0
功能：
  - 啟動前自動驗證套件完整性，缺少自動補裝
  - 崩潰時自動重啟，最多連續崩潰 5 次後暫停 10 分鐘再試
  - 記錄所有啟動/崩潰事件到 guardian.log
"""

import subprocess
import sys
import os
import time
from datetime import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).parent.absolute()
LOG_FILE   = BASE_DIR / "guardian.log"
APP_SCRIPT = BASE_DIR / "web_app.py"

# 固定使用 Python 3.12（有安裝 Flask 等套件的版本）
PYTHON312  = r"C:\Users\1120804\AppData\Local\Programs\Python\Python312\python.exe"
PYTHON     = PYTHON312 if Path(PYTHON312).exists() else sys.executable

MAX_CONSECUTIVE_CRASHES = 5   # 連續崩潰超過這個次數就暫停
COOLDOWN_SECONDS        = 600 # 暫停 10 分鐘後再試
MIN_ALIVE_SECONDS       = 30  # 活超過這秒才算「正常啟動過」，否則計入連續崩潰

REQUIRED_PACKAGES = ["flask", "requests", "python-dateutil", "flask-login", "bcrypt"]


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def verify_and_fix_packages():
    """啟動前確認套件完整性，缺少自動補裝"""
    log("🔍 驗證套件完整性...")
    missing = []
    for pkg in ["flask", "requests", "flask_login", "bcrypt", "dateutil"]:
        result = subprocess.run(
            [PYTHON, "-c", f"import {pkg}"],
            capture_output=True
        )
        if result.returncode != 0:
            missing.append(pkg)

    if missing:
        log(f"⚠️  發現缺少套件：{missing}，正在自動安裝...")
        req_file = BASE_DIR / "requirements.txt"
        if req_file.exists():
            subprocess.run(
                [PYTHON, "-m", "pip", "install", "-r", str(req_file), "-q",
                 "--no-warn-script-location"],
                capture_output=True
            )
        else:
            subprocess.run(
                [PYTHON, "-m", "pip", "install"] + REQUIRED_PACKAGES + ["-q"],
                capture_output=True
            )
        # 再次驗證
        still_missing = []
        for pkg in ["flask", "requests"]:
            result = subprocess.run([PYTHON, "-c", f"import {pkg}"], capture_output=True)
            if result.returncode != 0:
                still_missing.append(pkg)
        if still_missing:
            log(f"❌ 套件修復失敗：{still_missing}，嘗試繼續啟動...")
        else:
            log("✅ 套件自動修復成功")
    else:
        log("✅ 所有套件正常")


def run():
    consecutive_crashes = 0

    log("=" * 55)
    log("  覺醒行動app 守護程式啟動 v2.0")
    log(f"  使用 Python：{PYTHON}")
    log("=" * 55)

    # 首次啟動前做一次套件驗證
    verify_and_fix_packages()

    while True:
        log(f"▶ 啟動 web_app.py（連續崩潰次數：{consecutive_crashes}）")
        start_time = time.time()

        try:
            proc = subprocess.run(
                [PYTHON, "-X", "utf8", str(APP_SCRIPT)],
                cwd=str(BASE_DIR),
            )
            exit_code = proc.returncode
        except Exception as e:
            exit_code = -1
            log(f"  啟動失敗：{e}")

        elapsed = time.time() - start_time

        if elapsed >= MIN_ALIVE_SECONDS:
            # 活了夠久才算正常跑過，重設連續崩潰計數
            consecutive_crashes = 0
            log(f"  程式結束（exit={exit_code}，運行了 {elapsed:.0f} 秒）→ 立即重啟")
        else:
            consecutive_crashes += 1
            log(f"  程式 {elapsed:.1f} 秒內就結束了（exit={exit_code}）"
                f"，連續崩潰 {consecutive_crashes} 次")

            # 快速崩潰時嘗試自動修復套件
            if consecutive_crashes <= 2:
                log("  🔧 嘗試自動修復套件後重啟...")
                verify_and_fix_packages()

        if consecutive_crashes >= MAX_CONSECUTIVE_CRASHES:
            log(f"⚠️  連續崩潰 {consecutive_crashes} 次，暫停 {COOLDOWN_SECONDS // 60} 分鐘後再試...")
            time.sleep(COOLDOWN_SECONDS)
            consecutive_crashes = 0
            log("⏰ 冷卻結束，重新嘗試啟動")
            verify_and_fix_packages()  # 冷卻後再驗證一次
        else:
            time.sleep(3)  # 短暫等待 3 秒後重啟


if __name__ == "__main__":
    run()
