# -*- coding: utf-8 -*-
"""
modules/contacts.py - 聯絡人管理模組
"""

import json
from typing import List, Optional
from database import Database, Contact


class ContactManager:
    """聯絡人管理器"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_contact(self, name: str, source: str = "", tags: List[str] = None) -> Contact:
        """建立新聯絡人"""
        contact = Contact(name=name, source=source, tags=tags or [])
        self.db.add_contact(contact)
        return contact
    
    def get_contact(self, contact_id: str) -> Optional[dict]:
        """取得聯絡人"""
        return self.db.get_contact(contact_id)
    
    def get_all_contacts(self) -> List[dict]:
        """取得所有聯絡人"""
        return self.db.get_all_contacts()
    
    def search_contacts(self, keyword: str) -> List[dict]:
        """搜尋聯絡人"""
        return self.db.search_contacts(keyword)
    
    def update_contact(self, contact_id: str, **kwargs) -> bool:
        """更新聯絡人"""
        return self.db.update_contact(contact_id, **kwargs)
    
    def delete_contact(self, contact_id: str) -> bool:
        """刪除聯絡人"""
        return self.db.delete_contact(contact_id)
    
    def add_tag(self, contact_id: str, tag: str) -> bool:
        """新增標籤"""
        contact = self.db.get_contact(contact_id)
        if not contact:
            return False
        
        tags = json.loads(contact.get("tags", "[]"))
        if tag not in tags:
            tags.append(tag)
            return self.db.update_contact(contact_id, tags=json.dumps(tags, ensure_ascii=False))
        return True
    
    def remove_tag(self, contact_id: str, tag: str) -> bool:
        """移除標籤"""
        contact = self.db.get_contact(contact_id)
        if not contact:
            return False
        
        tags = json.loads(contact.get("tags", "[]"))
        if tag in tags:
            tags.remove(tag)
            return self.db.update_contact(contact_id, tags=json.dumps(tags, ensure_ascii=False))
        return True
    
    def get_contacts_by_tag(self, tag: str) -> List[dict]:
        """依標籤取得聯絡人"""
        all_contacts = self.db.get_all_contacts()
        return [c for c in all_contacts if tag in json.loads(c.get("tags", "[]"))]
    
    def get_monthly_new_contacts(self) -> List[dict]:
        """取得本月新聯絡人"""
        from datetime import datetime
        all_contacts = self.db.get_all_contacts()
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        return [c for c in all_contacts if c.get("created_at", "") >= month_start]
