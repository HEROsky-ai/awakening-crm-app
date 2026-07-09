# -*- coding: utf-8 -*-
"""
database/database.py - 資料庫管理
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import config


class Database:
    """SQLite 資料庫管理器"""

    def __init__(self, db_path: str = None):
        import os
        from pathlib import Path
        
        # Check storage_config.json for custom database path
        base_dir = Path(__file__).parent.parent.absolute()
        config_file = base_dir / "storage_config.json"
        custom_db_path = None
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    sp = cfg.get("storage_path")
                    if sp and os.path.exists(sp):
                        custom_db_path = os.path.join(sp, "awakening.db")
            except:
                pass
                
        chosen_path = db_path or custom_db_path or str(config.DATABASE_PATH)
        
        # If using custom path and it doesn't exist yet, but local database exists, migrate it
        if custom_db_path and chosen_path == custom_db_path and not os.path.exists(custom_db_path):
            local_db = str(config.DATABASE_PATH)
            if os.path.exists(local_db):
                try:
                    import shutil
                    os.makedirs(os.path.dirname(custom_db_path), exist_ok=True)
                    shutil.copyfile(local_db, custom_db_path)
                    print(f"Migrated database from {local_db} to {custom_db_path}")
                except Exception as e:
                    print(f"Failed to migrate database to custom path: {e}")
                    
        self.db_path = chosen_path
        self._auto_backup_and_cleanup()
        self._init_db()

    def _get_table_count(self, db_file: str, table: str) -> int:
        """取得指定 DB 檔案某張表的列數，失敗回傳 -1"""
        import sqlite3 as _sqlite3
        try:
            conn = _sqlite3.connect(db_file)
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return -1

    def _auto_backup_and_cleanup(self):
        """自動備份資料庫並清理 7 天前的舊備份。

        同時偵測雲端同步損毀：若目前 DB 的 contacts 或 interactions 數量
        遠少於備份中最高水位（差距 >= 3 筆且目前 < 備份的 70%），
        代表可能是 Google Drive/OneDrive 同步把舊的空版本覆蓋下來，
        此時自動從「有最多資料」的備份還原，再重新備份一次。
        """
        import os
        import shutil
        from datetime import datetime, timedelta

        # 確定資料庫檔案存在且大小大於 0 才進行備份
        if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
            return

        try:
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            backup_dir = os.path.join(db_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)

            now = datetime.now()
            backup_files = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith("awakening_") and f.endswith(".db")],
                key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
                reverse=True  # 最新的在前
            )

            # ── 雲端同步損毀偵測 ──────────────────────────────────────────
            # contacts：差距 >= 3 筆且目前 < 備份 70% 才觸發（允許正常刪除）
            # interactions：只要比備份最高水位少就觸發（聊天記錄只增不減）
            WATCHED_TABLES = [
                ("contacts",     "loose"),   # 寬鬆：差距 >= 3 且 < 70%
                ("interactions", "strict"),  # 嚴格：任何減少都觸發
            ]

            # 找出每張表在備份中的最高水位，以及對應的最佳備份檔
            best_backup_file = None
            best_backup_score = -1  # 用 contacts+interactions 總數做為評分

            table_best = {}  # table -> (best_count, best_file)
            for bf in backup_files:
                bf_path = os.path.join(backup_dir, bf)
                score = 0
                for table, _ in WATCHED_TABLES:
                    c = self._get_table_count(bf_path, table)
                    score += max(c, 0)
                    prev_best, _ = table_best.get(table, (0, None))
                    if c > prev_best:
                        table_best[table] = (c, bf)
                if score > best_backup_score:
                    best_backup_score = score
                    best_backup_file = bf

            # 判斷目前 DB 是否有任何一張表觸發損毀條件
            corruption_detected = False
            corruption_reason = ""
            for table, mode in WATCHED_TABLES:
                best_count, _ = table_best.get(table, (0, None))
                current = self._get_table_count(self.db_path, table)
                if mode == "strict":
                    # 只要比最高水位少就還原
                    triggered = (best_count > 0 and current >= 0 and current < best_count)
                else:
                    # 寬鬆：差距 >= 3 且 < 70%
                    triggered = (
                        best_count >= 3
                        and current >= 0
                        and current < best_count
                        and (best_count - current) >= 3
                        and current < best_count * 0.7
                    )
                if triggered:
                    corruption_detected = True
                    corruption_reason = (
                        f"{table}({mode}): current={current}, best_backup={best_count}"
                    )
                    break

            if corruption_detected and best_backup_file:
                restore_src = os.path.join(backup_dir, best_backup_file)
                emergency_bak = os.path.join(
                    backup_dir,
                    f"awakening_corrupt_{now.strftime('%Y%m%d_%H%M%S')}.db"
                )
                shutil.copyfile(self.db_path, emergency_bak)  # 保留損毀版本以備查
                shutil.copyfile(restore_src, self.db_path)
                print(
                    f"[Backup] WARNING: Cloud sync corruption detected! "
                    f"Reason: {corruption_reason}. "
                    f"Auto-restored from {best_backup_file}. "
                    f"Corrupt copy saved as {os.path.basename(emergency_bak)}"
                )
                # 重新整理 backup_files（還原後需重新判斷）
                backup_files = sorted(
                    [f for f in os.listdir(backup_dir)
                     if f.startswith("awakening_") and f.endswith(".db")
                     and not f.startswith("awakening_corrupt_")],
                    key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
                    reverse=True
                )
            # ──────────────────────────────────────────────────────────────

            # 1. 檢查是否需要備份 (限制每小時最多備份一次，以防爆量)
            need_backup = True
            if backup_files:
                latest_backup = backup_files[0]
                latest_time = datetime.fromtimestamp(
                    os.path.getmtime(os.path.join(backup_dir, latest_backup))
                )
                if now - latest_time < timedelta(hours=1):
                    need_backup = False

            if need_backup:
                timestamp = now.strftime("%Y%m%d_%H%M%S")
                backup_file_path = os.path.join(backup_dir, f"awakening_{timestamp}.db")
                shutil.copyfile(self.db_path, backup_file_path)
                print(f"[Backup] Auto backup created: {backup_file_path}")

            # 2. 自動清理 7 天前 (168小時) 的備份
            seven_days_ago = now - timedelta(days=7)
            for f in os.listdir(backup_dir):
                if f.startswith("awakening_") and f.endswith(".db"):
                    file_path = os.path.join(backup_dir, f)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < seven_days_ago:
                        os.remove(file_path)
                        print(f"[Backup] Auto cleaned old backup: {f}")
        except Exception as e:
            print(f"[Backup] Auto backup or cleanup failed: {e}")


    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化資料庫結構"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 聯絡人表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_at TEXT,
                updated_at TEXT,
                last_interaction TEXT,
                interaction_count INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                user_id TEXT DEFAULT '',
                image_path TEXT DEFAULT '',
                from_app TEXT DEFAULT ''
            )
        """)

        # FORMDH 檔案表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS formdh_profiles (
                id TEXT PRIMARY KEY,
                contact_id TEXT UNIQUE,
                f_family TEXT DEFAULT '',
                f_family_notes TEXT DEFAULT '',
                o_occupation TEXT DEFAULT '',
                o_occupation_notes TEXT DEFAULT '',
                o_work_style TEXT DEFAULT '',
                r_interests TEXT DEFAULT '',
                r_interests_detail TEXT DEFAULT '',
                r_hobbies TEXT DEFAULT '',
                m_money_values TEXT DEFAULT '',
                m_income_range TEXT DEFAULT '',
                m_investment TEXT DEFAULT '',
                m_financial_goals TEXT DEFAULT '',
                d_dreams TEXT DEFAULT '',
                d_short_term TEXT DEFAULT '',
                d_long_term TEXT DEFAULT '',
                d_motivations TEXT DEFAULT '',
                h_health TEXT DEFAULT '',
                h_fitness TEXT DEFAULT '',
                h_diet TEXT DEFAULT '',
                h_stress TEXT DEFAULT '',
                h_goals TEXT DEFAULT '',
                completeness_score INTEGER DEFAULT 0,
                updated_at TEXT,
                ai_chat_suggestions TEXT DEFAULT '',
                ai_current_affairs TEXT DEFAULT '',
                ai_missing_info_suggestions TEXT DEFAULT '',
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
            )
        """)

        # 互動記錄表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                contact_id TEXT,
                type TEXT DEFAULT '',
                date TEXT,
                content TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                channel TEXT DEFAULT '',
                created_at TEXT,
                user_id TEXT DEFAULT '',
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
            )
        """)

        # 行事曆事件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id TEXT PRIMARY KEY,
                contact_id TEXT,
                title TEXT DEFAULT '',
                description TEXT DEFAULT '',
                event_date TEXT,
                event_time TEXT DEFAULT '12:00',
                event_type TEXT DEFAULT '',
                google_event_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                user_id TEXT DEFAULT '',
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
            )
        """)

        # 系統設定表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # 動態遷移：確保所有現有資料庫的表也具備所需的 user_id 和 AI 建議欄位
        try:
            # 檢查 contacts 表
            cursor.execute("PRAGMA table_info(contacts)")
            contacts_cols = [row[1] for row in cursor.fetchall()]
            if "user_id" not in contacts_cols:
                cursor.execute("ALTER TABLE contacts ADD COLUMN user_id TEXT DEFAULT ''")
            if "image_path" not in contacts_cols:
                cursor.execute("ALTER TABLE contacts ADD COLUMN image_path TEXT DEFAULT ''")
            if "from_app" not in contacts_cols:
                cursor.execute("ALTER TABLE contacts ADD COLUMN from_app TEXT DEFAULT ''")
            
            # 檢查 formdh_profiles 表
            cursor.execute("PRAGMA table_info(formdh_profiles)")
            profiles_cols = [row[1] for row in cursor.fetchall()]
            if "ai_chat_suggestions" not in profiles_cols:
                cursor.execute("ALTER TABLE formdh_profiles ADD COLUMN ai_chat_suggestions TEXT DEFAULT ''")
            if "ai_current_affairs" not in profiles_cols:
                cursor.execute("ALTER TABLE formdh_profiles ADD COLUMN ai_current_affairs TEXT DEFAULT ''")
            if "ai_missing_info_suggestions" not in profiles_cols:
                cursor.execute("ALTER TABLE formdh_profiles ADD COLUMN ai_missing_info_suggestions TEXT DEFAULT ''")

            # 檢查 interactions 表
            cursor.execute("PRAGMA table_info(interactions)")
            interactions_cols = [row[1] for row in cursor.fetchall()]
            if "user_id" not in interactions_cols:
                cursor.execute("ALTER TABLE interactions ADD COLUMN user_id TEXT DEFAULT ''")

            # 檢查 calendar_events 表
            cursor.execute("PRAGMA table_info(calendar_events)")
            events_cols = [row[1] for row in cursor.fetchall()]
            if "user_id" not in events_cols:
                cursor.execute("ALTER TABLE calendar_events ADD COLUMN user_id TEXT DEFAULT ''")
        except Exception as migrate_err:
            print(f"資料庫欄位自動遷移失敗: {migrate_err}")

        # 清理已孤立的資料 (以防之前沒有 Cascade Delete)
        try:
            cursor.execute("DELETE FROM calendar_events WHERE contact_id NOT IN (SELECT id FROM contacts)")
            cursor.execute("DELETE FROM interactions WHERE contact_id NOT IN (SELECT id FROM contacts)")
            cursor.execute("DELETE FROM formdh_profiles WHERE contact_id NOT IN (SELECT id FROM contacts)")
        except Exception as cleanup_err:
            print(f"資料庫孤立資料清理失敗: {cleanup_err}")

        conn.commit()
        conn.close()

    # ========== 聯絡人操作 ==========

    def add_contact(self, contact, user_id: str = "") -> bool:
        """新增聯絡人"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            d = contact.to_dict()
            cursor.execute("""
                INSERT INTO contacts (id, name, source, tags, created_at, updated_at, 
                                     last_interaction, interaction_count, notes, user_id,
                                     image_path, from_app)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (d["id"], d["name"], d["source"], d["tags"], d["created_at"],
                  d["updated_at"], d["last_interaction"], d["interaction_count"], d["notes"], user_id,
                  d.get("image_path", ""), d.get("from_app", "")))
            conn.commit()
            
            # 同時建立空的 FORMDH 檔案
            from database.models import FormDHProfile
            profile = FormDHProfile(contact_id=d["id"])
            self.add_formdh_profile(profile)
            
            return True
        except Exception as e:
            print(f"新增聯絡人失敗: {e}")
            return False
        finally:
            conn.close()

    def get_contact(self, contact_id: str) -> Optional[dict]:
        """取得聯絡人"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_contacts(self, user_id: str = "") -> List[dict]:
        """取得所有聯絡人（按用戶篩選）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("SELECT * FROM contacts WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM contacts ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_contact(self, contact_id: str, **kwargs) -> bool:
        """更新聯絡人"""
        conn = self._get_connection()
        cursor = conn.cursor()
        kwargs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            for key, value in kwargs.items():
                cursor.execute(f"UPDATE contacts SET {key} = ? WHERE id = ?", (value, contact_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"更新聯絡人失敗: {e}")
            return False
        finally:
            conn.close()

    def delete_contact(self, contact_id: str) -> bool:
        """刪除聯絡人"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"刪除聯絡人失敗: {e}")
            return False
        finally:
            conn.close()

    def search_contacts(self, keyword: str, user_id: str = "") -> List[dict]:
        """搜尋聯絡人（支援按用戶）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("""
                SELECT * FROM contacts 
                WHERE (name LIKE ? OR source LIKE ? OR tags LIKE ? OR notes LIKE ?)
                AND (user_id = ? OR user_id = '')
                ORDER BY updated_at DESC
            """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", user_id))
        else:
            cursor.execute("""
                SELECT * FROM contacts 
                WHERE name LIKE ? OR source LIKE ? OR tags LIKE ? OR notes LIKE ?
                ORDER BY updated_at DESC
            """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_contacts_by_tag(self, tag: str, user_id: str = "") -> List[dict]:
        """依標籤取得聯絡人"""
        all_contacts = self.get_all_contacts(user_id)
        return [c for c in all_contacts if tag in json.loads(c.get("tags", "[]"))] if all_contacts else []

    # ========== FORMDH 檔案操作 ==========

    def add_formdh_profile(self, profile) -> bool:
        """新增 FORMDH 檔案"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            d = profile.to_dict()
            fields = ", ".join(d.keys())
            placeholders = ", ".join(["?"] * len(d))
            cursor.execute(f"INSERT INTO formdh_profiles ({fields}) VALUES ({placeholders})", 
                         tuple(d.values()))
            conn.commit()
            return True
        except Exception as e:
            print(f"新增 FORMDH 檔案失敗: {e}")
            return False
        finally:
            conn.close()

    def get_formdh_profile(self, contact_id: str) -> dict:
        """取得 FORMDH 檔案（若無則自動建立並返回空檔案）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM formdh_profiles WHERE contact_id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
            
        # 自動建立空的 FORMDH 檔案
        from database.models import FormDHProfile
        profile = FormDHProfile(contact_id=contact_id)
        self.add_formdh_profile(profile)
        
        # 再次查詢
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM formdh_profiles WHERE contact_id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {}

    def update_formdh_profile(self, contact_id: str, **kwargs) -> bool:
        """更新 FORMDH 檔案"""
        conn = self._get_connection()
        cursor = conn.cursor()
        kwargs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # 重新計算完整度
        profile = self.get_formdh_profile(contact_id)
        if profile:
            profile.update(kwargs)
            from database.models import FormDHProfile
            p = FormDHProfile.from_dict(profile)
            kwargs["completeness_score"] = p.calculate_completeness()
        try:
            for key, value in kwargs.items():
                cursor.execute(f"UPDATE formdh_profiles SET {key} = ? WHERE contact_id = ?", 
                            (value, contact_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"更新 FORMDH 檔案失敗: {e}")
            return False
        finally:
            conn.close()

    # ========== 互動記錄操作 ==========

    def add_interaction(self, interaction, user_id: str = "") -> bool:
        """新增互動記錄"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            d = interaction.to_dict()
            d["user_id"] = user_id
            fields = ", ".join(d.keys())
            placeholders = ", ".join(["?"] * len(d))
            cursor.execute(f"INSERT INTO interactions ({fields}) VALUES ({placeholders})", 
                         tuple(d.values()))
            
            # 更新聯絡人的 last_interaction 和 interaction_count
            cursor.execute("""
                UPDATE contacts 
                SET last_interaction = ?, interaction_count = interaction_count + 1, updated_at = ?
                WHERE id = ?
            """, (d["date"], datetime.now().strftime("%Y-%m-%d %H:%M"), d["contact_id"]))
            
            # 自動調整行事曆中的 pending 關心事件日期 (新增聊天狀況時往後延 1 週)
            from datetime import timedelta
            cursor.execute("""
                SELECT id, event_date FROM calendar_events 
                WHERE contact_id = ? AND status = 'pending' AND event_type = 'followup'
            """, (d["contact_id"],))
            pending_events = cursor.fetchall()
            for ev in pending_events:
                ev_dict = dict(ev)
                orig_date_str = ev_dict.get("event_date")
                if orig_date_str:
                    try:
                        orig_date = datetime.strptime(orig_date_str, "%Y-%m-%d")
                        new_date = orig_date + timedelta(days=7)
                        new_date_str = new_date.strftime("%Y-%m-%d")
                        cursor.execute("""
                            UPDATE calendar_events 
                            SET event_date = ? 
                            WHERE id = ?
                        """, (new_date_str, ev_dict["id"]))
                    except Exception as ex:
                        print(f"自動調整行事曆日期失敗: {ex}")

            conn.commit()
            return True
        except Exception as e:
            print(f"新增互動記錄失敗: {e}")
            return False
        finally:
            conn.close()

    def get_interactions(self, contact_id: str) -> List[dict]:
        """取得聯絡人的互動記錄"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM interactions 
            WHERE contact_id = ? 
            ORDER BY date DESC
        """, (contact_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_interactions(self, user_id: str = "") -> List[dict]:
        """取得所有互動記錄（按用戶所屬聯絡人篩選）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("""
                SELECT i.* FROM interactions i
                JOIN contacts c ON i.contact_id = c.id
                WHERE c.user_id = ? OR c.user_id = ''
                ORDER BY i.date DESC
            """, (user_id,))
        else:
            cursor.execute("SELECT * FROM interactions ORDER BY date DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ========== 行事曆事件操作 ==========

    def add_calendar_event(self, event) -> bool:
        """新增行事曆事件"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            d = event.to_dict()
            fields = ", ".join(d.keys())
            placeholders = ", ".join(["?"] * len(d))
            cursor.execute(f"INSERT INTO calendar_events ({fields}) VALUES ({placeholders})", 
                         tuple(d.values()))
            conn.commit()
            return True
        except Exception as e:
            print(f"新增行事曆事件失敗: {e}")
            return False
        finally:
            conn.close()

    def get_calendar_events(self, contact_id: str = None, start_date: str = None, 
                           end_date: str = None, user_id: str = None, include_cancelled: bool = False) -> List[dict]:
        """取得行事曆事件（按用戶篩選）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM calendar_events WHERE 1=1"
        if not include_cancelled:
            query += " AND status != 'cancelled'"
        params = []
        if contact_id:
            query += " AND contact_id = ?"
            params.append(contact_id)
        if start_date:
            query += " AND event_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND event_date <= ?"
            params.append(end_date)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY event_date ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_calendar_event(self, event_id: str, **kwargs) -> bool:
        """更新行事曆事件"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            for key, value in kwargs.items():
                cursor.execute(f"UPDATE calendar_events SET {key} = ? WHERE id = ?", 
                            (value, event_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"更新行事曆事件失敗: {e}")
            return False
        finally:
            conn.close()

    def delete_calendar_event(self, event_id: str) -> bool:
        """刪除行事曆事件"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"刪除行事曆事件失敗: {e}")
            return False
        finally:
            conn.close()

    # ========== 統計查詢 ==========

    def get_stats(self) -> dict:
        """取得統計資料"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 總聯絡人數
        cursor.execute("SELECT COUNT(*) FROM contacts")
        total_contacts = cursor.fetchone()[0]
        
        # 本月新聯絡人
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE created_at >= ?", (month_start,))
        new_this_month = cursor.fetchone()[0]
        
        # 本月互動次數
        cursor.execute("SELECT COUNT(*) FROM interactions WHERE date >= ?", (month_start,))
        interactions_this_month = cursor.fetchone()[0]
        
        # 逾期未聯繫人數（超過25天）
        from datetime import timedelta
        overdue_date = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COUNT(*) FROM contacts 
            WHERE last_interaction IS NULL OR last_interaction < ?
        """, (overdue_date,))
        overdue_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_contacts": total_contacts,
            "new_this_month": new_this_month,
            "interactions_this_month": interactions_this_month,
            "overdue_count": overdue_count
        }

    # ========== 系統設定操作 ==========

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """讀取系統設定值"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
        except Exception as e:
            print(f"讀取設定失敗: {e}")
            return default
        finally:
            conn.close()

    def set_setting(self, key: str, value: str) -> bool:
        """寫入/更新系統設定值"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            conn.commit()
            return True
        except Exception as e:
            print(f"儲存設定失敗: {e}")
            return False
        finally:
            conn.close()
