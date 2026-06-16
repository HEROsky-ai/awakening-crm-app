# -*- coding: utf-8 -*-
"""
modules/calendar.py - 行事曆整合模組
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import config


class CalendarManager:
    """行事曆管理器"""
    
    def __init__(self, db):
        self.db = db
    
    def add_event(self, contact_id: str, title: str, event_date: str, 
                  event_time: str = "12:00", description: str = "",
                  event_type: str = "reminder") -> bool:
        """新增行事曆事件"""
        from database.models import CalendarEvent
        
        event = CalendarEvent(
            contact_id=contact_id,
            title=title,
            description=description,
            event_date=event_date,
            event_time=event_time,
            event_type=event_type,
            status="pending"
        )
        
        return self.db.add_calendar_event(event)
    
    def get_upcoming_events(self, days: int = 7) -> List[dict]:
        """取得即將到來的行事曆事件"""
        from datetime import timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        return self.db.get_calendar_events(start_date=today, end_date=end_date)
    
    def get_today_events(self) -> List[dict]:
        """取得今日事件"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.db.get_calendar_events(start_date=today, end_date=today)
    
    def mark_event_completed(self, event_id: str) -> bool:
        """標記事件為已完成"""
        return self.db.update_calendar_event(event_id, status="completed")
    
    def cancel_event(self, event_id: str) -> bool:
        """取消事件"""
        return self.db.update_calendar_event(event_id, status="cancelled")
    
    def sync_to_google(self) -> bool:
        """同步到 Google Calendar"""
        # 檢查是否有 Google API 憑證
        if not config.GOOGLE_CREDENTIALS_PATH.exists():
            print("⚠️ 找不到 Google API 憑證，跳過同步")
            print(f"   請將憑證檔案放置於：{config.GOOGLE_CREDENTIALS_PATH}")
            return False
        
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            
            # 驗證
            creds = None
            if config.GOOGLE_TOKEN_PATH.exists():
                creds = Credentials.from_authorized_user_file(str(config.GOOGLE_TOKEN_PATH))
            
            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(config.GOOGLE_CREDENTIALS_PATH),
                    ['https://www.googleapis.com/auth/calendar']
                )
                creds = flow.run_local_server(port=0)
                
                # 儲存 token
                with open(config.GOOGLE_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            # 建立 Calendar API 服務
            service = build('calendar', 'v3', credentials=creds)
            
            # 取得本系統的事件
            events = self.db.get_calendar_events(
                start_date=datetime.now().strftime("%Y-%m-%d"),
                end_date=(datetime.now().replace(day=28) + __import__('datetime').timedelta(days=4)).strftime("%Y-%m-%d")
            )
            
            # 同步到 Google
            synced = 0
            for event in events:
                if event.get("google_event_id"):
                    continue  # 已有同步，跳過
                
                contact = self.db.get_contact(event["contact_id"])
                contact_name = contact["name"] if contact else "未知"
                
                google_event = {
                    'summary': event["title"],
                    'description': f"{event['description']}\n\n聯絡人：{contact_name}",
                    'start': {
                        'dateTime': f"{event['event_date']}T{event['event_time']}:00",
                        'timeZone': 'Asia/Taipei',
                    },
                    'end': {
                        'dateTime': f"{event['event_date']}T{event['event_time']}:00",
                        'timeZone': 'Asia/Taipei',
                    },
                }
                
                result = service.events().insert(calendarId='primary', body=google_event).execute()
                
                # 更新本系統的 google_event_id
                self.db.update_calendar_event(event["id"], google_event_id=result['id'])
                synced += 1
            
            print(f"✅ 已同步 {synced} 個事件到 Google Calendar")
            return True
            
        except Exception as e:
            print(f"❌ Google Calendar 同步失敗：{e}")
            return False
    
    def export_to_csv(self, filepath: str = None) -> str:
        """匯出到 CSV"""
        if not filepath:
            filename = f"calendar_export_{datetime.now().strftime('%Y%m%d')}.csv"
            filepath = config.EXPORT_DIR / filename
        
        events = self.db.get_calendar_events()
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['日期', '時間', '標題', '類型', '狀態', '聯絡人', '說明'])
            
            for e in events:
                contact = self.db.get_contact(e["contact_id"])
                contact_name = contact["name"] if contact else "未知"
                writer.writerow([
                    e["event_date"],
                    e["event_time"],
                    e["title"],
                    e["event_type"],
                    e["status"],
                    contact_name,
                    e["description"]
                ])
        
        return str(filepath)
    
    def import_from_csv(self, filepath: str) -> int:
        """從 CSV 匯入"""
        count = 0
        from database.models import CalendarEvent
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                event = CalendarEvent(
                    title=row['標題'],
                    description=row.get('說明', ''),
                    event_date=row['日期'],
                    event_time=row.get('時間', '12:00'),
                    event_type=row.get('類型', 'reminder'),
                    status='pending'
                )
                if self.db.add_calendar_event(event):
                    count += 1
        
        return count
