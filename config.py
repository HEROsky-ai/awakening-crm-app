# -*- coding: utf-8 -*-
"""
覺醒行動app - 設定檔
"""

import os
from pathlib import Path

# 專案根目錄
BASE_DIR = Path(__file__).parent.absolute()

# 資料庫路徑
DATABASE_PATH = BASE_DIR / "data" / "awakening.db"

# 匯出資料夾
EXPORT_DIR = BASE_DIR / "data" / "exports"

# 設定檔案
CONFIG_FILE = BASE_DIR / "config.yaml"

# LINE Notify Token（用戶需要自行設定）
LINE_NOTIFY_TOKEN = ""

# Google Calendar 設定
GOOGLE_CREDENTIALS_PATH = BASE_DIR / "data" / "google_credentials.json"
GOOGLE_TOKEN_PATH = BASE_DIR / "data" / "google_token.json"

# 預設標籤
DEFAULT_TAGS = [
    "A",
    "B",
    "C",
    "新人",
    "舊人", 
    "高潛力",
    "待追蹤",
    "已成交",
    "放棄"
]

# 互動類型
INTERACTION_TYPES = [
    "chat",      # 聊天
    "care",      # 關心問候
    "share",     # 分享資訊
    "invite",    # 邀約活動
    "followup"   # 後續追蹤
]

# 互動管道
INTERACTION_CHANNELS = [
    "IG",
    "LINE",
    "電話",
    "見面",
    "訊息",
    "其他"
]

# FORMDH 欄位定義
FORMDH_FIELDS = {
    "F": {
        "name": "家庭 Family",
        "fields": {
            "f_family": "家庭狀況",
            "f_family_notes": "家庭備註"
        }
    },
    "O": {
        "name": "工作 Occupation",
        "fields": {
            "o_occupation": "職業",
            "o_occupation_notes": "工作狀況",
            "o_work_style": "工作型態"
        }
    },
    "R": {
        "name": "興趣 Recreation",
        "fields": {
            "r_interests": "興趣愛好（多個用逗號分隔）",
            "r_interests_detail": "興趣詳細描述",
            "r_hobbies": "業餘活動"
        }
    },
    "M": {
        "name": "金錢觀 Money",
        "fields": {
            "m_money_values": "金錢觀",
            "m_income_range": "收入區間",
            "m_investment": "投資理財態度",
            "m_financial_goals": "財務目標"
        }
    },
    "D": {
        "name": "夢想 Dreams",
        "fields": {
            "d_dreams": "夢想目標",
            "d_short_term": "短期夢想（1年內）",
            "d_long_term": "長期夢想（5-10年）",
            "d_motivations": "動機與渴望"
        }
    },
    "H": {
        "name": "健康 Health",
        "fields": {
            "h_health": "健康狀況",
            "h_fitness": "健身/運動習慣",
            "h_diet": "飲食習慣",
            "h_stress": "壓力來源",
            "h_goals": "健康目標"
        }
    }
}

# 自動規劃設定
PLANNING_CONFIG = {
    "max_days_without_interaction": 25,  # 超過25天未互動就標記
    "min_interactions_per_month": 1,     # 每月至少一次互動
    "high_priority_threshold": 35,        # 高優先級分數門檻
    "reminder_days_before": 3            # 提前幾天提醒
}

# 通知設定
NOTIFICATION_CONFIG = {
    "daily_reminder_time": "09:00",       # 每日提醒時間
    "weekly_report_day": "sunday",        # 每週報告日
    "enable_line_notify": False,
    "enable_wechat_notify": False
}

# 建立必要目錄
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
