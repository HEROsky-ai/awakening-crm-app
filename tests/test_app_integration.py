# -*- coding: utf-8 -*-
"""
tests/test_app_integration.py - 覺醒行動app 功能整合測試
"""

import unittest
import os
import json
import shutil
import sys
from pathlib import Path

# 將專案根目錄加入系統路徑，解決測試導入問題
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

# 在導入其他模組前 Mock 設定檔路徑，以防干擾正式資料
import config
test_db_path = config.BASE_DIR / "data" / "test_awakening.db"
config.DATABASE_PATH = test_db_path

# 備份正式的 storage_config.json
storage_config_path = config.BASE_DIR / "storage_config.json"
backup_config_path = config.BASE_DIR / "storage_config_backup_test.json"

if storage_config_path.exists():
    shutil.copyfile(storage_config_path, backup_config_path)

# 設定測試用的設定檔內容 (將儲存路徑指向 data 目錄，API Key 設為空)
with open(storage_config_path, "w", encoding="utf-8") as f:
    json.dump({
        "storage_path": str(config.BASE_DIR / "data"),
        "gemini_api_key": ""
    }, f, ensure_ascii=False)

# 導入 web_app 與 database
from database import Database
from web_app import app, db

class AwakeningAppTestCase(unittest.TestCase):
    def setUp(self):
        # 確保測試資料庫是乾淨的
        if test_db_path.exists():
            try:
                os.remove(test_db_path)
            except:
                pass
        
        # 初始化測試資料庫
        self.db = Database(str(test_db_path))
        
        # 替換 Flask app 中的 db 實例為測試用的 db
        import web_app
        web_app.db = self.db
        
        self.app = app.test_client()
        self.app.testing = True

    def tearDown(self):
        # 清除測試資料庫
        if test_db_path.exists():
            try:
                os.remove(test_db_path)
            except:
                pass

    def test_01_homepage_redirect(self):
        """測試首頁 (/) 正確重導向至行事曆 (/calendar)"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/calendar', response.headers['Location'])

    def test_02_calendar_view(self):
        """測試行事曆首頁網頁載入"""
        response = self.app.get('/calendar')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'calendar', response.data) # 檢查是否包含 calendar 元件

    def test_03_add_contact_manual(self):
        """測試手動新增新人聯絡人"""
        response = self.app.post('/contacts/add', data={
            'name': '測試新人',
            'source': 'IG',
            'tags': '新人,高潛力'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 驗證資料庫中是否成功存入
        contacts = self.db.get_all_contacts()
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]['name'], '測試新人')
        self.assertEqual(contacts[0]['source'], 'IG')
        self.assertIn('新人', json.loads(contacts[0]['tags']))

    def test_04_add_calendar_event(self):
        """測試手動加排行事曆日程"""
        # 先建立一個聯絡人
        from database.models import Contact
        c = Contact(name="小叮噹", source="LINE")
        self.db.add_contact(c)
        
        # POST 排定日程
        response = self.app.post('/calendar/add_event', data={
            'contact_id': c.id,
            'event_date': '2026-06-20',
            'event_time': '10:00',
            'title': '測試聊天日程',
            'event_type': 'followup'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 驗證事件是否在資料庫中
        events = self.db.get_calendar_events()
        manual_event = next((e for e in events if e['title'] == '測試聊天日程'), None)
        self.assertIsNotNone(manual_event)
        self.assertEqual(manual_event['contact_id'], c.id)
        self.assertEqual(manual_event['event_date'], '2026-06-20')
        self.assertEqual(manual_event['status'], 'pending')

    def test_05_update_formdh(self):
        """測試更新 FORMDH 檔案與完整度計算"""
        from database.models import Contact
        c = Contact(name="大雄", source="學校")
        self.db.add_contact(c)
        
        # 更新 FORMDH 欄位
        response = self.app.post(f'/contacts/{c.id}/formdh', data={
            'f_family': '與父母同住',
            'o_occupation': '小學生',
            'r_interests': '睡覺,翻花繩'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 驗證資料
        profile = self.db.get_formdh_profile(c.id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile['f_family'], '與父母同住')
        self.assertEqual(profile['o_occupation'], '小學生')
        self.assertEqual(profile['r_interests'], '睡覺,翻花繩')
        self.assertGreater(profile['completeness_score'], 0) # 完整度應大於 0

    def test_06_add_interaction(self):
        """測試新增互動記錄且同步更新最後聯繫日期"""
        from database.models import Contact
        c = Contact(name="靜香", source="LINE")
        self.db.add_contact(c)
        
        # 新增互動
        response = self.app.post(f'/contacts/{c.id}/interact', data={
            'type': 'chat',
            'channel': 'LINE',
            'content': '今天聊了音樂與鋼琴',
            'date': '2026-06-15'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 驗證互動記錄
        interactions = self.db.get_interactions(c.id)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0]['content'], '今天聊了音樂與鋼琴')
        
        # 驗證聯絡人最後聯繫天數更新
        updated_contact = self.db.get_contact(c.id)
        self.assertEqual(updated_contact['last_interaction'], '2026-06-15')
        self.assertEqual(updated_contact['interaction_count'], 1)

    def test_07_complete_cancel_event(self):
        """測試完成與取消行事曆日程"""
        from database.models import Contact, CalendarEvent
        c = Contact(name="胖虎", source="空地")
        self.db.add_contact(c)
        
        e1 = CalendarEvent(contact_id=c.id, event_date="2026-06-15", title="關心1", status="pending")
        e2 = CalendarEvent(contact_id=c.id, event_date="2026-06-16", title="關心2", status="pending")
        self.db.add_calendar_event(e1)
        self.db.add_calendar_event(e2)
        
        # 完成 e1
        response = self.app.get(f'/calendar/complete/{e1.id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 取消 e2
        response = self.app.get(f'/calendar/cancel/{e2.id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 檢查資料庫狀態
        events = self.db.get_calendar_events(include_cancelled=True)
        events_dict = {e['id']: e for e in events}
        self.assertEqual(events_dict[e1.id]['status'], 'completed')
        self.assertEqual(events_dict[e2.id]['status'], 'cancelled')

    def test_08_planner_bug_fix(self):
        """測試 Planner 自動規劃防崩潰修復"""
        from database.models import Contact
        c = Contact(name="小夫", source="轉介紹", tags=["高潛力"])
        self.db.add_contact(c)
        
        # 調用自動規劃與排程
        from modules.planner import Planner
        planner = Planner(self.db)
        
        # 如果 Bug 沒修復，在此處會引發 KeyError: 'suggestion' 崩潰
        try:
            count = planner.auto_schedule_interactions()
            self.assertTrue(True) # 無崩潰即為過關
        except KeyError as ke:
            self.fail(f"自動規劃崩潰！KeyError: 'suggestion' 未被修復。詳情: {ke}")

    def test_09_complete_event_with_progress_notes(self):
        """測試打勾完成任務並附帶聊天進度以更新新人備註與互動記錄"""
        from database.models import Contact, CalendarEvent
        c = Contact(name="小新", source="幼稚園")
        self.db.add_contact(c)
        
        e = CalendarEvent(contact_id=c.id, event_date="2026-06-16", title="聊聊日常", status="pending")
        self.db.add_calendar_event(e)
        
        # POST 請求打勾完成並輸入備註
        response = self.app.post(f'/calendar/complete_with_notes/{e.id}', data={
            'chat_progress': '聊得很好，對紐崔萊有興趣'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 1. 驗證事件狀態是否變更為 completed
        events = self.db.get_calendar_events()
        event_dict = {evt['id']: evt for evt in events}
        self.assertEqual(event_dict[e.id]['status'], 'completed')
        
        # 2. 驗證聯絡人 notes 內是否更新了聊天進度
        updated_contact = self.db.get_contact(c.id)
        self.assertIsNotNone(updated_contact['notes'])
        self.assertIn('聊得很好，對紐崔萊有興趣', updated_contact['notes'])
        
        # 3. 驗證是否新增了對應的互動記錄
        interactions = self.db.get_interactions(c.id)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0]['content'], '聊得很好，對紐崔萊有興趣')
        self.assertEqual(interactions[0]['type'], 'chat')

    def test_10_ai_text_import(self):
        """測試 AI 文字智慧分析與自動建檔"""
        from unittest.mock import patch
        
        mock_ai_response = {
            "status": "ok",
            "name": "陳阿明",
            "source": "讀書會",
            "tags": ["正面", "愛學習"],
            "f_family": "已婚有一子",
            "o_occupation": "軟體工程師",
            "r_interests": "登山與看書",
            "m_money_values": "保守理財",
            "d_dreams": "三年內買房",
            "h_health": "常常胃食道逆流",
            "ai_chat_suggestions": "可以聊聊爬山的話題",
            "ai_current_affairs": "近期熱門登山路線推薦",
            "ai_missing_info_suggestions": "可以問他平時工作壓力大不大"
        }
        
        # 模擬呼叫 AI 分析模組
        with patch('modules.ai_analyst.analyze_contact_info', return_value=mock_ai_response):
            response = self.app.post('/contacts/ai_import', data={
                'contact_id': 'new',
                'new_contact_name': '',
                'raw_text': '我今天認識了陳阿明，他是在讀書會認識的...'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            
            # 驗證是否建立了新的聯絡人
            contacts = self.db.search_contacts("陳阿明")
            self.assertEqual(len(contacts), 1)
            c = contacts[0]
            self.assertEqual(c['name'], '陳阿明')
            self.assertEqual(c['source'], '讀書會')
            self.assertIn('正面', json.loads(c['tags']))
            
            # 驗證 FORMDH 是否有被 AI 鍵入
            profile = self.db.get_formdh_profile(c['id'])
            self.assertIsNotNone(profile)
            self.assertEqual(profile['f_family'], '已婚有一子')
            self.assertEqual(profile['o_occupation'], '軟體工程師')
            self.assertEqual(profile['r_interests'], '登山與看書')
            self.assertEqual(profile['m_money_values'], '保守理財')
            self.assertEqual(profile['d_dreams'], '三年內買房')
            self.assertEqual(profile['h_health'], '常常胃食道逆流')
            self.assertEqual(profile['ai_chat_suggestions'], '可以聊聊爬山的話題')
            
            # 驗證是否新增了系統建檔的互動記錄
            interactions = self.db.get_interactions(c['id'])
            self.assertEqual(len(interactions), 1)
            self.assertIn('透過 AI 文字分析自動建檔', interactions[0]['content'])

    def test_11_self_healing_profile(self):
        """測試當聯絡人缺少 FORMDH 檔案時，系統會自動建立 (自我修復)"""
        # 手動直接插入一個聯絡人至資料庫，不建立 FORMDH 檔案以模擬舊數據
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO contacts (id, name, source, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("legacy_id_999", "舊聯絡人", "Legacy", "[]", "2026-01-01", "2026-01-01"))
        conn.commit()
        conn.close()
        
        # 呼叫 get_formdh_profile，此時應該會觸發自動修復建立空的 Profile
        profile = self.db.get_formdh_profile("legacy_id_999")
        self.assertIsNotNone(profile)
        self.assertEqual(profile['contact_id'], "legacy_id_999")
        self.assertEqual(profile['completeness_score'], 0)

    def test_12_contacts_list_view(self):
        """測試聯絡人清單頁面載入且正常解析標籤"""
        from database.models import Contact
        c = Contact(name="測試清單人", source="測試管道", tags=["標籤A", "標籤B"])
        self.db.add_contact(c)
        
        response = self.app.get('/contacts')
        self.assertEqual(response.status_code, 200)
        self.assertIn("測試清單人".encode('utf-8'), response.data)
        self.assertIn("標籤A".encode('utf-8'), response.data)

    def test_13_auto_schedule_random_distribution(self):
        """測試自動規劃關心事件按鈕，會隨機平均分配聯絡人、每日上限<=15人、溢出自動排到下個月。
        並且：
        1. 新建聯絡人會在近期的 3 到 5 天內提醒。
        2. 新人免除 15 人上限限制，且當天人數過多時可調整到一週內天數進行平均。
        """
        from database.models import Contact, CalendarEvent
        from modules.planner import Planner
        from datetime import datetime, timedelta
        import json
        
        # 為了獨立且精確地測試，我們先清空資料庫
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts")
        cursor.execute("DELETE FROM calendar_events")
        conn.commit()
        conn.close()
        
        planner = Planner(self.db)
        
        # 1. 建立新建非新人的聯絡人 (7天內建立且無互動，不含「新人」標籤)
        # 這些應該落在 today+3 到 today+5 天內
        new_contacts = []
        for i in range(5):
            c = Contact(
                name=f"新建非新人_{i}",
                source="系統測試",
                tags=[],
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M")
            )
            self.db.add_contact(c)
            new_contacts.append(c)
            
        # 2. 建立新建的新人聯絡人 (7天內建立且無互動，含有「新人」標籤)
        # 這些在普通情況下也會落在 today+3 到 today+5 內，若人過多會在一週內 (1-7天) 進行分攤
        xinren_contacts = []
        for i in range(20):
            c = Contact(
                name=f"新建新人_{i}",
                source="系統測試",
                tags=["新人"],
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M")
            )
            self.db.add_contact(c)
            xinren_contacts.append(c)
            
        # 3. 建立一般聯絡人 (非新建，比如 created_at 是 10 天前)
        # 這些應該被平均分到 12 個月中
        for i in range(20):
            c = Contact(
                name=f"一般人_{i}",
                source="系統測試",
                created_at=(datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M"),
                last_interaction=(datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
            )
            self.db.add_contact(c)
            
        # 4. 執行自動規劃
        count = planner.auto_schedule_interactions()
        self.assertEqual(count, 45) # 5 + 20 + 20 = 45 人均建立事件
        
        events = self.db.get_calendar_events()
        
        # 5. 驗證新建非新人的聯絡人全部都在 3-5 天內
        today = datetime.now()
        dates_3_to_5 = [(today + timedelta(days=d)).strftime("%Y-%m-%d") for d in [3, 4, 5]]
        dates_1_to_7 = [(today + timedelta(days=d)).strftime("%Y-%m-%d") for d in range(1, 8)]
        
        for c in new_contacts:
            c_events = [e for e in events if e["contact_id"] == c.id]
            self.assertEqual(len(c_events), 1)
            self.assertIn(c_events[0]["event_date"], dates_3_to_5)
            
        # 6. 驗證「新人」分配到一週內 (1-7天內) 以做平均且免除 15 人限制
        for c in xinren_contacts:
            c_events = [e for e in events if e["contact_id"] == c.id]
            self.assertEqual(len(c_events), 1)
            self.assertIn(c_events[0]["event_date"], dates_1_to_7)
            
        # 7. 驗證一般人被分派到後面（非 1-7 天短時間）
        # 我們測試是否有一般人排在未來的各個月份中
        # 可以藉由檢查排程日期是否有大於 today + 7 天的來確認
        future_7_days = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        has_long_term = False
        for event in events:
            if event["event_date"] > future_7_days:
                has_long_term = True
                break
        self.assertTrue(has_long_term, "一般人應該被平均分佈到較長遠的月份中")

    def test_09_add_contact_with_image_and_app_source(self):
        """測試新增聯絡人同時帶有圖片和來源 App 以及後續編輯功能"""
        import io
        data = {
            'name': '測試新圖片好友',
            'source': 'IG',
            'from_app': 'Instagram',
            'tags': '新人',
            'image': (io.BytesIO(b"fake image content"), 'test_avatar.png')
        }
        response = self.app.post('/contacts/add', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # 驗證資料庫
        contacts = self.db.search_contacts('測試新圖片好友')
        self.assertEqual(len(contacts), 1)
        contact = contacts[0]
        self.assertEqual(contact['name'], '測試新圖片好友')
        self.assertEqual(contact['from_app'], 'Instagram')
        self.assertTrue(contact['image_path'].startswith('avatar_'))

        # 驗證檔案是否成功儲存到 uploads
        import config
        saved_file = config.BASE_DIR / 'uploads' / contact['image_path']
        self.assertTrue(saved_file.exists())

        # 驗證編輯功能
        edit_data = {
            'name': '編輯後圖片好友',
            'source': 'LINE',
            'from_app': 'LINE_App',
            'tags': '舊人',
            'notes': '修改測試',
            'image': (io.BytesIO(b"updated fake image content"), 'test_avatar_updated.png')
        }
        edit_response = self.app.post(f"/contacts/{contact['id']}/edit", data=edit_data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(edit_response.status_code, 200)

        # 驗證編輯後的資料庫與檔案
        updated_contact = self.db.get_contact(contact['id'])
        self.assertEqual(updated_contact['name'], '編輯後圖片好友')
        self.assertEqual(updated_contact['from_app'], 'LINE_App')
        self.assertEqual(updated_contact['source'], 'LINE')
        self.assertTrue(updated_contact['image_path'].startswith('avatar_'))

        # 驗證靜態 uploads 路由是否可存取該圖片
        image_response = self.app.get(f"/uploads/{updated_contact['image_path']}")
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.data, b"updated fake image content")

        # 刪除測試產生的上傳檔案以保持乾淨
        try:
            saved_file.unlink()
        except:
            pass
        try:
            (config.BASE_DIR / 'uploads' / updated_contact['image_path']).unlink()
        except:
            pass

# 測試結束後還原正式的設定檔
def restore_backup():
    if backup_config_path.exists():
        if storage_config_path.exists():
            try:
                os.remove(storage_config_path)
            except:
                pass
        shutil.copyfile(backup_config_path, storage_config_path)
        try:
            os.remove(backup_config_path)
        except:
            pass

import atexit
atexit.register(restore_backup)

if __name__ == '__main__':
    unittest.main()
