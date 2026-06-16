# -*- coding: utf-8 -*-
"""
modules/planner.py - 自動互動規劃引擎
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict

import config
from database import Database


class Planner:
    """自動互動規劃引擎"""
    
    def __init__(self, db: Database, user_id: str = ""):
        self.db = db
        self.user_id = user_id
        self.max_days = config.PLANNING_CONFIG["max_days_without_interaction"]
        self.high_priority_threshold = config.PLANNING_CONFIG["high_priority_threshold"]
    
    def calculate_priority(self, contact: dict) -> tuple:
        """
        計算聯絡人優先級
        返回 (priority_level, score, reason)
        priority_level: high / medium / low
        """
        import json
        
        score = 0
        reasons = []
        tags = json.loads(contact.get("tags", "[]"))
        
        # 天數未互動（基礎分數）
        days = contact.get("last_interaction")
        if not days:
            score += 40  # 從未互動
            reasons.append("從未互動")
            days_num = 999
        else:
            days_num = (datetime.now() - datetime.strptime(days, "%Y-%m-%d")).days
            if days_num > 30:
                score += 40
                reasons.append(f"超過30天未聯繫")
            elif days_num > 25:
                score += 30
                reasons.append(f"超過25天未聯繫")
            elif days_num > 14:
                score += 15
                reasons.append(f"超過14天未聯繫")
        
        # 標籤加成
        if "高潛力" in tags:
            score += 10
            reasons.append("高潛力客户")
        if "新人" in tags:
            score += 5
            reasons.append("需要持續關注的新人")
        if "待追蹤" in tags:
            score += 8
            reasons.append("待追蹤客户")
        
        # 沒有 FORMDH 檔案或完整度低
        profile = self.db.get_formdh_profile(contact["id"])
        if not profile:
            score += 5
            reasons.append("尚無個人檔案")
        else:
            completeness = profile.get("completeness_score", 0)
            if completeness < 30:
                score += 5
                reasons.append("個人檔案不完整")
        
        # 決定優先級
        if score >= self.high_priority_threshold:
            priority = "high"
        elif score >= 15:
            priority = "medium"
        else:
            priority = "low"
            
        return priority, score, "、".join(reasons)
    
    def get_overdue_contacts(self) -> List[dict]:
        """取得逾期未聯繫的聯絡人"""
        contacts = self.db.get_all_contacts(self.user_id)
        overdue = []
        
        for c in contacts:
            tags = []
            try:
                tags = json.loads(c.get("tags", "[]"))
            except:
                pass
                
            max_days = self.max_days
            if "新人" in tags:
                max_days = 7
            elif "高潛力" in tags or "待追蹤" in tags:
                max_days = 14
                
            last = c.get("last_interaction")
            if not last:
                overdue.append(c)
            else:
                days = (datetime.now() - datetime.strptime(last, "%Y-%m-%d")).days
                if days >= max_days:
                    overdue.append(c)
        
        # 按天數排序
        overdue.sort(key=lambda x: 
                    999 if not x.get("last_interaction") 
                    else (datetime.now() - datetime.strptime(x["last_interaction"], "%Y-%m-%d")).days,
                    reverse=True)
        
        return overdue
    
    def get_today_tasks(self) -> List[Dict]:
        """取得今日應執行的任務"""
        contacts = self.db.get_all_contacts(self.user_id)
        tasks = []
        today = datetime.now()
        
        for c in contacts:
            priority, score, reason = self.calculate_priority(c)
            
            if priority == "high":
                tasks.append({
                    "contact_id": c["id"],
                    "name": c["name"],
                    "priority": priority,
                    "reason": reason,
                    "suggestion": self._get_suggestion(c, priority)
                })
        
        # 按優先級排序
        tasks.sort(key=lambda x: 
                  (0 if x["priority"] == "high" else 1 if x["priority"] == "medium" else 2))
        
        return tasks[:10]  # 最多返回10個
    
    def _get_suggestion(self, contact: dict, priority: str) -> str:
        """根據聯絡人情況給出建議"""
        import json
        tags = json.loads(contact.get("tags", "[]"))
        
        if "新人" in tags:
            return "新朋友，可以分享一些覺醒事業機會或生活小故事"
        
        profile = self.db.get_formdh_profile(contact["id"])
        if profile:
            interests = profile.get("r_interests", "")
            if interests:
                return f"對方對 {interests} 有興趣，可以從這個話題切入"
        
        if priority == "high":
            return "盡快主動關心，展現誠意"
        
        return "例行問候，保持聯繫"
    
    def generate_monthly_plan(self) -> List[Dict]:
        """產生本月互動規劃"""
        contacts = self.db.get_all_contacts(self.user_id)
        plan = []
        today = datetime.now()
        month_end = today.replace(day=28) + timedelta(days=4)  # 月底
        
        for c in contacts:
            priority, score, reason = self.calculate_priority(c)
            
            tags = []
            try:
                tags = json.loads(c.get("tags", "[]"))
            except:
                pass
                
            max_days = self.max_days
            if "新人" in tags:
                max_days = 7
            elif "高潛力" in tags or "待追蹤" in tags:
                max_days = 14
            
            # 計算距離月底還有多少天
            last = c.get("last_interaction")
            if last:
                days_since = (today - datetime.strptime(last, "%Y-%m-%d")).days
                days_until_month_end = (month_end - today).days
                
                # 如果到月底會超過最大未互動天數，就規劃進來
                if days_since + days_until_month_end >= max_days:
                    plan.append({
                        "contact": c,
                        "priority": priority,
                        "score": score,
                        "reason": reason,
                        "suggestion": self._get_suggestion(c, priority),
                        "days_since": days_since,
                        "suggested_date": self._suggest_date(c, today, month_end, max_days)
                    })
            else:
                # 從未互動
                plan.append({
                    "contact": c,
                    "priority": priority,
                    "score": score,
                    "reason": reason,
                    "suggestion": self._get_suggestion(c, priority),
                    "days_since": 999,
                    "suggested_date": self._suggest_date(c, today, month_end, max_days)
                })
        
        # 按優先級和分數排序
        plan.sort(key=lambda x: (
            0 if x["priority"] == "high" else 1,
            -x["score"]
        ))
        
        return plan
    
    def _suggest_date(self, contact: dict, start: datetime, end: datetime, max_days: int = 25) -> str:
        """建議互動日期"""
        # 簡單策略：優先排比較久沒聯繫的人
        last = contact.get("last_interaction")
        if not last:
            # 從未互動的優先
            return start.strftime("%Y-%m-%d")
        
        days_since = (start - datetime.strptime(last, "%Y-%m-%d")).days
        
        # 越久沒聯繫，越早建議
        if days_since >= max_days:
            return start.strftime("%Y-%m-%d")
        
        # 根據不同的最大天數計算合適的延遲
        if max_days <= 7:
            offset = 2
        elif max_days <= 14:
            offset = 4
        else:
            offset = 7
        
        suggested = start + timedelta(days=offset)
        if suggested > end:
            return end.strftime("%Y-%m-%d")
        
        return suggested.strftime("%Y-%m-%d")
    
    def auto_schedule_interactions(self) -> int:
        """自動在行事曆建立互動事件"""
        from database.models import CalendarEvent
        
        plan = self.generate_monthly_plan()
        count = 0
        
        for item in plan:
            if item["priority"] in ["high", "medium"]:
                # 檢查是否已有即將到來的事件
                existing = self.db.get_calendar_events(
                    contact_id=item["contact"]["id"],
                    start_date=datetime.now().strftime("%Y-%m-%d")
                )
                
                if not existing:
                    event = CalendarEvent(
                        contact_id=item["contact"]["id"],
                        title=f"關心：{item['contact']['name']}",
                        description=f"原因：{item['reason']}\n建議：{item['suggestion']}",
                        event_date=item["suggested_date"],
                        event_time="14:00",
                        event_type="followup",
                        status="pending"
                    )
                    
                    if self.db.add_calendar_event(event):
                        count += 1
        
        return count
