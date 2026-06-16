# -*- coding: utf-8 -*-
"""
modules/notifications.py - 通知系統模組
"""

import requests
from datetime import datetime
from typing import List

import config


class NotificationManager:
    """通知管理器"""
    
    def __init__(self, db):
        self.db = db
    
    def send_line_notify(self, message: str, token: str = None) -> bool:
        """發送 LINE Notify 通知"""
        token = token or self.db.get_setting("line_notify_token") or config.LINE_NOTIFY_TOKEN
        if not token:
            print("⚠️ 未設定 LINE Notify Token")
            return False
        
        try:
            url = "https://notify-api.line.me/api/notify"
            headers = {"Authorization": f"Bearer {token}"}
            data = {"message": message}
            
            response = requests.post(url, headers=headers, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ LINE Notify 發送失敗：{e}")
            return False

    def send_ntfy(self, message: str, topic: str = None) -> bool:
        """發送 ntfy 推播通知"""
        topic = topic or self.db.get_setting("ntfy_topic")
        if not topic:
            print("⚠️ 未設定 ntfy Topic")
            return False
            
        try:
            import base64
            # RFC 2047 encoding for unicode title
            encoded_title = f"=?utf-8?B?{base64.b64encode('覺醒行動app'.encode('utf-8')).decode('utf-8')}?="
            
            url = f"https://ntfy.sh/{topic}"
            headers = {
                "Title": encoded_title,
                "Priority": "default",
                "Tags": "bell,white_check_mark"
            }
            response = requests.post(url, data=message.encode('utf-8'), headers=headers, timeout=10)
            return response.status_code == 200
        except Exception as e:
            # Avoid printing emoji to console if it can cause UnicodeEncodeError on Windows
            print(f"[ntfy] 發送失敗: {e}")
            return False

    def send_all_notifications(self, message: str) -> bool:
        """發送所有已啟用的通知管道"""
        success = True
        
        # 1. LINE Notify
        db_line_enable = self.db.get_setting("enable_line_notify")
        is_line_enabled = (db_line_enable == "true") if db_line_enable is not None else config.NOTIFICATION_CONFIG.get("enable_line_notify", False)
        if is_line_enabled:
            if not self.send_line_notify(message):
                success = False
                
        # 2. ntfy
        db_ntfy_enable = self.db.get_setting("enable_ntfy")
        is_ntfy_enabled = (db_ntfy_enable == "true")
        if is_ntfy_enabled:
            if not self.send_ntfy(message):
                success = False
                
        if not is_line_enabled and not is_ntfy_enabled:
            print("（未啟用任何推播通知管道）")
            
        return success
    
    def send_daily_reminder(self) -> bool:
        """發送每日提醒"""
        from modules.planner import Planner
        
        planner = Planner(self.db)
        today_tasks = planner.get_today_tasks()
        overdue = planner.get_overdue_contacts()
        
        if not today_tasks and not overdue:
            message = f"📋 {datetime.now().strftime('%m/%d')} 每日提醒\n\n✅ 今日無待關心名單"
        else:
            message = f"📋 {datetime.now().strftime('%m/%d')} 每日提醒\n\n"
            
            if overdue:
                message += f"⚠️ 逾期未聯繫：{len(overdue)}人\n"
                for c in overdue[:3]:
                    message += f"  • {c['name']}\n"
                if len(overdue) > 3:
                    message += f"  • ...還有 {len(overdue) - 3} 人\n"
                message += "\n"
            
            if today_tasks:
                message += f"🔔 今日優先關心：{len(today_tasks)}人\n"
                for task in today_tasks[:5]:
                    message += f"  • {task['name']} - {task['reason']}\n"
                if len(today_tasks) > 5:
                    message += f"  • ...還有 {len(today_tasks) - 5} 人\n"
        
        print(f"📤 發送通知：\n{message}")
        return self.send_all_notifications(message)
    
    def send_weekly_report(self) -> bool:
        """發送每週報告"""
        stats = self.db.get_stats()
        
        message = f"""📊 每週報告 {datetime.now().strftime('%Y/%m/%d')}
 
👥 聯絡人概況：
  • 總人數：{stats['total_contacts']}人
  • 本月新人：{stats['new_this_month']}人
  • 本月互動：{stats['interactions_this_month']}次
  • 逾期未聯繫：{stats['overdue_count']}人
 
💡 建議：
"""
        
        if stats['overdue_count'] > 5:
            message += "  • 有較多人逾期未聯繫，建議加強關心"
        else:
            message += "  • 維持得很好，繼續保持！"
        
        print(f"📤 發送每週報告：\n{message}")
        return self.send_all_notifications(message)
    
    def send_monthly_report(self) -> bool:
        """發送每月報告"""
        stats = self.db.get_stats()
        
        # 計算互動達成率
        contacts = self.db.get_all_contacts()
        monthly_interactors = 0
        for c in contacts:
            if c.get("last_interaction"):
                last = datetime.strptime(c["last_interaction"], "%Y-%m-%d")
                if (datetime.now() - last).days <= 30:
                    monthly_interactors += 1
        
        achievement_rate = int((monthly_interactors / len(contacts) * 100)) if contacts else 0
        
        message = f"""📊 每月報告 {datetime.now().strftime('%Y/%m')}
 
🏆 互動達成率：{achievement_rate}%
  • 達到月度互動：{monthly_interactors}/{len(contacts)}人
 
📈 數據概況：
  • 總聯絡人：{stats['total_contacts']}人
  • 本月新人的：{stats['new_this_month']}人
  • 本月互動次數：{stats['interactions_this_month']}次
  • 逾期未聯繫：{stats['overdue_count']}人
 
{'🎉 達成目標！' if achievement_rate >= 90 else '💪 下個月再加油！'}
"""
        
        print(f"📤 發送每月報告：\n{message}")
        return self.send_all_notifications(message)
    
    def send_test(self) -> bool:
        """發送測試通知"""
        message = f"""🔔 覺醒行動app 測試通知
 
 時間：{datetime.now().strftime('%Y/%m/%d %H:%M')}
 狀態：✅ 系統運作正常
"""
        return self.send_all_notifications(message)
