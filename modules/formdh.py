# -*- coding: utf-8 -*-
"""
modules/formdh.py - FORMDH 檔案管理模組
"""

from typing import Optional, Dict
from database import Database, FormDHProfile


class FormDHManager:
    """FORMDH 檔案管理器"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_profile(self, contact_id: str) -> Optional[dict]:
        """取得 FORMDH 檔案"""
        return self.db.get_formdh_profile(contact_id)
    
    def update_profile(self, contact_id: str, **kwargs) -> bool:
        """更新 FORMDH 檔案"""
        return self.db.update_formdh_profile(contact_id, **kwargs)
    
    def get_completeness(self, contact_id: str) -> int:
        """取得檔案完整度"""
        profile = self.db.get_formdh_profile(contact_id)
        if not profile:
            return 0
        return profile.get("completeness_score", 0)
    
    def get_missing_fields(self, contact_id: str) -> list:
        """取得尚未填寫的欄位"""
        profile = self.db.get_formdh_profile(contact_id)
        if not profile:
            return list(FormDHProfile.__dataclass_fields__.keys())
        
        import config
        missing = []
        for letter, section in config.FORMDH_FIELDS.items():
            for field_name, field_desc in section["fields"].items():
                if not profile.get(field_name, "").strip():
                    missing.append({
                        "letter": letter,
                        "field": field_name,
                        "description": field_desc,
                        "section_name": section["name"]
                    })
        
        return missing
    
    def get_summary_by_letter(self, contact_id: str, letter: str) -> Dict:
        """依 FORMDH 字母取得摘要"""
        profile = self.db.get_formdh_profile(contact_id)
        if not profile:
            return {}
        
        import config
        section = config.FORMDH_FIELDS.get(letter, {})
        fields = section.get("fields", {})
        
        summary = {
            "letter": letter,
            "name": section.get("name", ""),
            "fields": {}
        }
        
        for field_key, field_desc in fields.items():
            summary["fields"][field_key] = {
                "value": profile.get(field_key, ""),
                "description": field_desc,
                "filled": bool(profile.get(field_key, "").strip())
            }
        
        return summary
    
    def fill_from_conversation(self, contact_id: str, conversation_text: str) -> Dict:
        """
        從對話文字中自動識別 FORMDH 資訊
        這是一個簡單的關鍵字匹配實現
        """
        text = conversation_text.lower()
        updates = {}
        
        # 家庭關鍵字
        family_keywords = ["結婚", "單身", "老公", "老婆", "先生", "太太", "女友", "男友", "小孩", "孩子", "家庭"]
        for kw in family_keywords:
            if kw in text:
                updates["f_family"] = f"從對話識別：提到{kw}"
                break
        
        # 工作關鍵字
        work_keywords = ["工作", "上班", "公司", "老闆", "同事", "辭職", "失業", "創業", "自由業"]
        for kw in work_keywords:
            if kw in text:
                updates["o_occupation"] = f"從對話識別：提到{kw}"
                break
        
        # 興趣關鍵字
        interest_keywords = ["運動", "健身", "旅行", "美食", "音樂", "電影", "閱讀", "投資", "股票"]
        found_interests = [kw for kw in interest_keywords if kw in text]
        if found_interests:
            updates["r_interests"] = "、".join(found_interests)
        
        # 夢想關鍵字
        dream_keywords = ["夢想", "目標", "希望", "想要", "將來", "退休", "財富自由"]
        for kw in dream_keywords:
            if kw in text:
                updates["d_dreams"] = f"從對話識別：提到{kw}"
                break
        
        # 健康關鍵字
        health_keywords = ["健康", "運動", "減肥", "健身", "疾病", "醫生"]
        for kw in health_keywords:
            if kw in text:
                updates["h_health"] = f"從對話識別：提到{kw}"
                break
        
        if updates:
            self.db.update_formdh_profile(contact_id, **updates)
        
        return updates
