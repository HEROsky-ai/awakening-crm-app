# -*- coding: utf-8 -*-
"""
database/models.py - 資料模型
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional


@dataclass
class Contact:
    """聯絡人模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    source: str = ""  # 來源：IG/LINE/活動/轉介紹
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    last_interaction: Optional[str] = None
    interaction_count: int = 0
    notes: str = ""
    image_path: str = ""
    from_app: str = ""

    def to_dict(self):
        d = asdict(self)
        d["tags"] = json.dumps(self.tags, ensure_ascii=False)
        return d

    @classmethod
    def from_dict(cls, d):
        tags = d.get("tags", "[]")
        if isinstance(tags, str):
            tags = json.loads(tags)
        return cls(
            id=d["id"],
            name=d["name"],
            source=d.get("source", ""),
            tags=tags,
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            last_interaction=d.get("last_interaction"),
            interaction_count=d.get("interaction_count", 0),
            notes=d.get("notes", ""),
            image_path=d.get("image_path", ""),
            from_app=d.get("from_app", "")
        )

    def days_since_interaction(self) -> int:
        """計算距離上次互動的天數"""
        if not self.last_interaction:
            return 999  # 從未互動
        try:
            last = datetime.strptime(self.last_interaction, "%Y-%m-%d")
            return (datetime.now() - last).days
        except:
            return 999


@dataclass
class FormDHProfile:
    """FORMDH 個人檔案模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    contact_id: str = ""
    # F - 家庭
    f_family: str = ""
    f_family_notes: str = ""
    # O - 工作
    o_occupation: str = ""
    o_occupation_notes: str = ""
    o_work_style: str = ""
    # R - 興趣
    r_interests: str = ""  # JSON array string
    r_interests_detail: str = ""
    r_hobbies: str = ""
    # M - 金錢觀
    m_money_values: str = ""
    m_income_range: str = ""
    m_investment: str = ""
    m_financial_goals: str = ""
    # D - 夢想
    d_dreams: str = ""
    d_short_term: str = ""
    d_long_term: str = ""
    d_motivations: str = ""
    # H - 健康
    h_health: str = ""
    h_fitness: str = ""
    h_diet: str = ""
    h_stress: str = ""
    h_goals: str = ""
    # AI 建議與分析
    ai_chat_suggestions: str = ""
    ai_current_affairs: str = ""
    ai_missing_info_suggestions: str = ""
    # 完整度
    completeness_score: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    def calculate_completeness(self) -> int:
        """計算檔案完整度百分比"""
        fields_to_check = [
            self.f_family, self.f_family_notes,
            self.o_occupation, self.o_occupation_notes, self.o_work_style,
            self.r_interests, self.r_interests_detail, self.r_hobbies,
            self.m_money_values, self.m_income_range, self.m_investment, self.m_financial_goals,
            self.d_dreams, self.d_short_term, self.d_long_term, self.d_motivations,
            self.h_health, self.h_fitness, self.h_diet, self.h_stress, self.h_goals
        ]
        filled = sum(1 for f in fields_to_check if f and f.strip())
        total = len(fields_to_check)
        return int((filled / total) * 100)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Interaction:
    """互動記錄模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    contact_id: str = ""
    type: str = ""  # chat/care/share/invite/followup
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    content: str = ""
    notes: str = ""
    channel: str = ""  # IG/LINE/電話/見面
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CalendarEvent:
    """行事曆事件模型"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    contact_id: str = ""
    title: str = ""
    description: str = ""
    event_date: str = ""  # 日期
    event_time: str = "12:00"  # 時間
    event_type: str = ""  # reminder/birthday/followup
    google_event_id: str = ""
    status: str = "pending"  # pending/completed/cancelled
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
