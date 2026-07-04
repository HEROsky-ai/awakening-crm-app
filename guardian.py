# -*- coding: utf-8 -*-
"""
guardian.py - 覺醒行動app 自動重啟守護程式
當 web_app.py 崩潰時自動重啟，最多連續崩潰 5 次後暫停 10 分鐘再試。
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
PYTHON     = sys.executable

MAX_CONSECUTIVE_CRASHES = 5   # 連續崩潰超過這個次數就暫停
COOLDOWN_SECONDS        = 600 # 暫停 10 分鐘後再試
MIN_ALIVE_SECONDS       = 30  # 活超過這秒才算「正常啟動過」，否則計入連續崩潰


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run():
    consecutive_crashes = 0

    log("=" * 55)
    log("  覺醒行動app 守護程式啟動")
    log("=" * 55)

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

        if consecutive_crashes >= MAX_CONSECUTIVE_CRASHES:
            log(f"⚠️  連續崩潰 {consecutive_crashes} 次，暫停 {COOLDOWN_SECONDS // 60} 分鐘後再試...")
            time.sleep(COOLDOWN_SECONDS)
            consecutive_crashes = 0
            log("⏰ 冷卻結束，重新嘗試啟動")
        else:
            time.sleep(3)  # 短暫等待 3 秒後重啟


if __name__ == "__main__":
    run()
