# -*- coding: utf-8 -*-
"""
database/migrations/V002_add_users.py - 新增多用戶支援
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

def run(db_path: str):
    """執行遷移：新增 users 表 + user_id 欄位"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. 新增 users 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            created_at TEXT,
            last_login TEXT
        )
    """)
    
    # 2. 檢查 contacts 是否有 user_id 欄位，沒有的話就新增
    cursor.execute("PRAGMA table_info(contacts)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE contacts ADD COLUMN user_id TEXT DEFAULT ''")
        print("✅ 已新增 contacts.user_id 欄位")
    
    # 3. 檢查 formdh_profiles 是否有 user_id 欄位
    cursor.execute("PRAGMA table_info(formdh_profiles)")
    f_columns = [col[1] for col in cursor.fetchall()]
    
    if "user_id" not in f_columns:
        cursor.execute("ALTER TABLE formdh_profiles ADD COLUMN user_id TEXT DEFAULT ''")
        print("✅ 已新增 formdh_profiles.user_id 欄位")
    
    # 4. 檢查 interactions 是否有 user_id 欄位
    cursor.execute("PRAGMA table_info(interactions)")
    i_columns = [col[1] for col in cursor.fetchall()]
    
    if "user_id" not in i_columns:
        cursor.execute("ALTER TABLE interactions ADD COLUMN user_id TEXT DEFAULT ''")
        print("✅ 已新增 interactions.user_id 欄位")
    
    # 5. 檢查 calendar_events 是否有 user_id 欄位
    cursor.execute("PRAGMA table_info(calendar_events)")
    c_columns = [col[1] for col in cursor.fetchall()]
    
    if "user_id" not in c_columns:
        cursor.execute("ALTER TABLE calendar_events ADD COLUMN user_id TEXT DEFAULT ''")
        print("✅ 已新增 calendar_events.user_id 欄位")
    
    conn.commit()
    conn.close()
    print("✅ 資料庫遷移 V002 完成")
