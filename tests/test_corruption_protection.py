# -*- coding: utf-8 -*-
"""
tests/test_corruption_protection.py - 雲端同步損毀偵測與自動還原測試
"""

import unittest
import os
import json
import shutil
import sqlite3
import sys
import time
import gc
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

import config
# 指向測試 DB，不干擾正式資料
test_db_path = str(config.BASE_DIR / "data" / "test_corruption.db")

# 備份 storage_config 並改指向 data 目錄
storage_config_path = config.BASE_DIR / "storage_config.json"
backup_config_path  = config.BASE_DIR / "storage_config_backup_corruption_test.json"
if storage_config_path.exists():
    shutil.copyfile(storage_config_path, backup_config_path)
with open(storage_config_path, "w", encoding="utf-8") as f:
    json.dump({"storage_path": str(config.BASE_DIR / "data"), "gemini_api_key": ""}, f)

from database import Database
from database.models import Contact, Interaction


def _create_db_with_data(path, contacts=5, interactions=10):
    """在指定路徑建立一個已有資料的 DB"""
    conn = sqlite3.connect(path)
    cur  = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY, name TEXT, source TEXT, tags TEXT DEFAULT '[]',
        created_at TEXT, updated_at TEXT, last_interaction TEXT,
        interaction_count INTEGER DEFAULT 0, notes TEXT, user_id TEXT DEFAULT '',
        image_path TEXT DEFAULT '', from_app TEXT DEFAULT ''
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS interactions (
        id TEXT PRIMARY KEY, contact_id TEXT, type TEXT, channel TEXT,
        content TEXT, date TEXT, created_at TEXT, user_id TEXT DEFAULT ''
    )""")
    for i in range(contacts):
        cur.execute("INSERT OR IGNORE INTO contacts (id,name,source,tags,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                    (f"c{i}", f"聯絡人{i}", "IG", "[]", "2026-01-01", "2026-01-01"))
    for i in range(interactions):
        cur.execute("INSERT OR IGNORE INTO interactions (id,contact_id,type,channel,content,date,created_at) VALUES (?,?,?,?,?,?,?)",
                    (f"i{i}", "c0", "chat", "LINE", f"聊天{i}", "2026-01-01", "2026-01-01"))
    conn.commit()
    conn.close()


def _create_empty_db(path):
    """在指定路徑建立一個有結構但無資料的空 DB"""
    conn = sqlite3.connect(path)
    cur  = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY, name TEXT, source TEXT, tags TEXT DEFAULT '[]',
        created_at TEXT, updated_at TEXT, last_interaction TEXT,
        interaction_count INTEGER DEFAULT 0, notes TEXT, user_id TEXT DEFAULT '',
        image_path TEXT DEFAULT '', from_app TEXT DEFAULT ''
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS interactions (
        id TEXT PRIMARY KEY, contact_id TEXT, type TEXT, channel TEXT,
        content TEXT, date TEXT, created_at TEXT, user_id TEXT DEFAULT ''
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS formdh_profiles (id TEXT PRIMARY KEY, contact_id TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS calendar_events (id TEXT PRIMARY KEY, contact_id TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY)""")
    conn.commit()
    conn.close()


def _count(path, table):
    try:
        conn = sqlite3.connect(path)
        cur  = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        n = cur.fetchone()[0]
        conn.close()
        return n
    except Exception:
        return -1


class TestGetTableCount(unittest.TestCase):
    """測試 _get_table_count 輔助方法"""

    def _close_db(self, db_obj=None):
        """強制關閉 DB 連線（Windows 需要這步才能刪檔）"""
        if db_obj is not None:
            try:
                conn = db_obj._get_connection()
                conn.close()
            except Exception:
                pass
        gc.collect()  # 強制釋放所有 SQLite 物件的 file handle

    def setUp(self):
        self.db = Database(test_db_path)

    def tearDown(self):
        self._close_db(self.db)
        self.db = None
        for f in [test_db_path]:
            try: os.remove(f)
            except: pass
        backup_dir = os.path.join(os.path.dirname(test_db_path), "backups")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

    def test_valid_table(self):
        """正確計算存在的表"""
        n = self.db._get_table_count(test_db_path, "contacts")
        self.assertGreaterEqual(n, 0)

    def test_invalid_table(self):
        """不存在的表應回傳 -1"""
        n = self.db._get_table_count(test_db_path, "nonexistent_table")
        self.assertEqual(n, -1)

    def test_invalid_path(self):
        """不存在的路徑應回傳 -1"""
        n = self.db._get_table_count("/not/exist/path.db", "contacts")
        self.assertEqual(n, -1)


class TestCorruptionDetection(unittest.TestCase):
    """測試損毀偵測邏輯"""

    def _cleanup(self):
        """釋放所有 SQLite file handle 再刪檔"""
        gc.collect()
        try: os.remove(test_db_path)
        except: pass
        backup_dir = os.path.join(os.path.dirname(test_db_path), "backups")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        gc.collect()
        self._cleanup()

    def _make_backup(self, path, contacts=12, interactions=26, ts=None):
        """在 backups 資料夾建立一個指定資料量的備份檔"""
        backup_dir = os.path.join(os.path.dirname(path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = ts or datetime.now().strftime("%Y%m%d_%H%M%S")
        bak_path = os.path.join(backup_dir, f"awakening_{ts}.db")
        _create_db_with_data(bak_path, contacts=contacts, interactions=interactions)
        return bak_path

    # ── contacts 損毀偵測 ────────────────────────────────────────────────────

    def test_contacts_corruption_triggers_restore(self):
        """contacts 從 12 掉到 0：應自動還原"""
        self._make_backup(test_db_path, contacts=12, interactions=26, ts="20260101_120000")
        _create_empty_db(test_db_path)

        db = Database(test_db_path)
        del db; gc.collect()

        self.assertEqual(_count(test_db_path, "contacts"), 12,
                         "contacts 應已從備份還原為 12 筆")

    def test_contacts_small_decrease_no_restore(self):
        """contacts 從 12 掉到 10（差距 2，< 閾值 3）：不應還原"""
        self._make_backup(test_db_path, contacts=12, interactions=26, ts="20260101_120000")

        _create_db_with_data(test_db_path, contacts=10, interactions=26)

        db = Database(test_db_path)
        del db; gc.collect()

        self.assertEqual(_count(test_db_path, "contacts"), 10,
                         "差距僅 2 筆不應觸發還原，contacts 應維持 10")

    def test_contacts_above_70pct_no_restore(self):
        """contacts 從 12 掉到 9（差距 3 但 9/12 = 75% > 70%）：不應還原"""
        self._make_backup(test_db_path, contacts=12, interactions=26, ts="20260101_120000")
        _create_db_with_data(test_db_path, contacts=9, interactions=26)

        db = Database(test_db_path)
        del db; gc.collect()

        self.assertEqual(_count(test_db_path, "contacts"), 9,
                         "9/12 = 75% > 70%，不應觸發還原")

    # ── interactions 嚴格偵測 ────────────────────────────────────────────────

    def test_interactions_any_decrease_triggers_restore(self):
        """interactions 從 26 掉到 20（少 6 筆）：應嚴格觸發還原"""
        self._make_backup(test_db_path, contacts=12, interactions=26, ts="20260101_120000")
        _create_db_with_data(test_db_path, contacts=12, interactions=20)

        db = Database(test_db_path)
        del db; gc.collect()

        self.assertEqual(_count(test_db_path, "interactions"), 26,
                         "interactions 減少應立即還原")

    def test_interactions_zero_no_backup_no_restore(self):
        """沒有備份時，即使 interactions 為 0 也不應嘗試還原（不崩潰）"""
        _create_empty_db(test_db_path)
        try:
            db = Database(test_db_path)
            del db; gc.collect()
            success = True
        except Exception as e:
            success = False
            self.fail(f"無備份時應能正常啟動，但發生例外：{e}")
        self.assertTrue(success)

    # ── 備份機制 ─────────────────────────────────────────────────────────────

    def test_backup_created_on_startup(self):
        """啟動後應自動在 backups 資料夾產生備份"""
        _create_db_with_data(test_db_path, contacts=5, interactions=10)
        db = Database(test_db_path)
        del db; gc.collect()

        backup_dir = os.path.join(os.path.dirname(test_db_path), "backups")
        backups = [f for f in os.listdir(backup_dir)
                   if f.startswith("awakening_") and f.endswith(".db")
                   and "corrupt" not in f]
        self.assertGreater(len(backups), 0, "啟動後應有備份產生")

    def test_no_duplicate_backup_within_1hr(self):
        """1 小時內再次啟動不應重複備份（只有 1 份）"""
        _create_db_with_data(test_db_path, contacts=5, interactions=10)
        db1 = Database(test_db_path)
        del db1; gc.collect()
        db2 = Database(test_db_path)  # 第二次啟動（1 小時內）
        del db2; gc.collect()

        backup_dir = os.path.join(os.path.dirname(test_db_path), "backups")
        backups = [f for f in os.listdir(backup_dir)
                   if f.startswith("awakening_") and f.endswith(".db")
                   and "corrupt" not in f]
        self.assertEqual(len(backups), 1, "1 小時內不應產生重複備份")

    def test_corrupt_db_saved_separately(self):
        """觸發還原時，損毀版本應另存為 awakening_corrupt_*.db"""
        self._make_backup(test_db_path, contacts=12, interactions=26, ts="20260101_120000")
        _create_empty_db(test_db_path)

        db = Database(test_db_path)
        del db; gc.collect()

        backup_dir = os.path.join(os.path.dirname(test_db_path), "backups")
        corrupt_files = [f for f in os.listdir(backup_dir) if "corrupt" in f]
        self.assertGreater(len(corrupt_files), 0, "損毀版本應另存為 awakening_corrupt_*.db")

    def test_best_backup_selected(self):
        """有多份備份時，應選擇 contacts+interactions 合計最多的那份還原"""
        self._make_backup(test_db_path, contacts=5,  interactions=10, ts="20260101_080000")
        self._make_backup(test_db_path, contacts=12, interactions=26, ts="20260101_100000")  # 最多
        self._make_backup(test_db_path, contacts=8,  interactions=15, ts="20260101_120000")

        _create_empty_db(test_db_path)
        db = Database(test_db_path)
        del db; gc.collect()

        self.assertEqual(_count(test_db_path, "contacts"),     12, "應從資料最多的備份還原 contacts=12")
        self.assertEqual(_count(test_db_path, "interactions"), 26, "應從資料最多的備份還原 interactions=26")

    def test_empty_db_skip_backup(self):
        """DB 大小為 0 時不應執行備份或崩潰"""
        open(test_db_path, 'w').close()
        try:
            db = Database(test_db_path)
            del db; gc.collect()
            success = True
        except Exception as e:
            success = False
            self.fail(f"空 DB 不應崩潰：{e}")
        self.assertTrue(success)


class TestDatabaseCRUD(unittest.TestCase):
    """基本 CRUD 操作測試"""

    def _cleanup(self):
        gc.collect()
        try: os.remove(test_db_path)
        except: pass
        backup_dir = os.path.join(os.path.dirname(test_db_path), "backups")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

    def setUp(self):
        self._cleanup()
        self.db = Database(test_db_path)

    def tearDown(self):
        self.db = None
        self._cleanup()

    def test_add_and_get_contact(self):
        c = Contact(name="測試人", source="IG")
        self.assertTrue(self.db.add_contact(c))
        result = self.db.get_contact(c.id)
        self.assertEqual(result["name"], "測試人")
        self.assertEqual(result["source"], "IG")

    def test_update_contact(self):
        c = Contact(name="原本", source="IG")
        self.db.add_contact(c)
        self.db.update_contact(c.id, name="更新後")
        result = self.db.get_contact(c.id)
        self.assertEqual(result["name"], "更新後")

    def test_delete_contact(self):
        c = Contact(name="刪除測試", source="LINE")
        self.db.add_contact(c)
        self.db.delete_contact(c.id)
        self.assertIsNone(self.db.get_contact(c.id))

    def test_search_contacts(self):
        self.db.add_contact(Contact(name="王小明", source="IG"))
        self.db.add_contact(Contact(name="李小花", source="LINE"))
        results = self.db.search_contacts("小明")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "王小明")

    def test_add_interaction_updates_contact(self):
        c = Contact(name="互動測試", source="LINE")
        self.db.add_contact(c)
        from database.models import Interaction
        i = Interaction(contact_id=c.id, type="chat", channel="LINE",
                        content="測試訊息", date="2026-06-01")
        self.db.add_interaction(i)
        updated = self.db.get_contact(c.id)
        self.assertEqual(updated["interaction_count"], 1)
        self.assertEqual(updated["last_interaction"], "2026-06-01")

    def test_get_all_contacts_returns_list(self):
        for i in range(5):
            self.db.add_contact(Contact(name=f"人{i}", source="IG"))
        all_c = self.db.get_all_contacts()
        self.assertEqual(len(all_c), 5)

    def test_duplicate_contact_id_rejected(self):
        c = Contact(name="重複測試", source="IG")
        self.db.add_contact(c)
        # 手動插入相同 id
        conn = self.db._get_connection()
        cur  = conn.cursor()
        try:
            cur.execute("INSERT INTO contacts (id,name,source,tags,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                        (c.id, "重複", "IG", "[]", "2026-01-01", "2026-01-01"))
            conn.commit()
            duplicate_inserted = True
        except Exception:
            duplicate_inserted = False
        conn.close()
        self.assertFalse(duplicate_inserted, "相同 ID 不應被插入")


# 還原 storage_config
import atexit

def _restore():
    if backup_config_path.exists():
        shutil.copyfile(backup_config_path, storage_config_path)
        try: os.remove(backup_config_path)
        except: pass

atexit.register(_restore)

if __name__ == "__main__":
    unittest.main(verbosity=2)
