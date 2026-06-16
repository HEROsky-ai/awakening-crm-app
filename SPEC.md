# 覺醒行動app - 專案規格書

## 1. 專案概述

**專案名稱**：覺醒行動app (AwakeningAction)  
**目標**：幫助覺醒直銷商系統化管理客戶/新人，透過 FORMDH 個人檔案框架，建立深度客戶關係，並配合行事曆自動規劃互動時機。

**核心功能**：
- FORMDH 個人檔案建立與管理
- 行事曆串接（Google Calendar / 本地行事曆）
- 自動規劃互動排程（每月底前確保每人至少互動一次）
- 微信/Line 提醒通知

---

## 2. FORMDH 資料模型

### 2.1 聯絡人基本欄位
| 欄位 | 說明 | 範例 |
|------|------|------|
| id | 唯一識別碼 | UUID |
| name | 姓名 | 王小明 |
| source | 來源 | IG/LINE/活動/轉介紹 |
| created_at | 建立時間 | 2026-06-15 |
| updated_at | 更新時間 | 2026-06-15 |
| last_interaction | 最後互動日期 | 2026-06-10 |
| interaction_count | 總互動次數 | 5 |
| tags | 標籤 | ["新人", "高潛力", "興趣相同"] |

### 2.2 FORMDH 個人檔案
| 欄位 | 說明 | 資料型態 |
|------|------|----------|
| F_family | 家庭狀況 | 文字（配偶、小孩、家庭成員等） |
| F_family_notes | 家庭備註 | 文字 |
| O_occupation | 職業 | 文字 |
| O_occupation_notes | 工作狀況 | 文字 |
| O_work_style | 工作型態 | 文字（例：自由業、打工族） |
| R_interests | 興趣愛好 | 文字陣列 |
| R_interests_detail | 興趣詳細 | 文字 |
| R_hobbies | 業餘活動 | 文字 |
| M_money_values | 金錢觀 | 文字 |
| M_income_range | 收入區間 | 文字（例：30-50萬/年） |
| M_investment | 投資理財態度 | 文字 |
| M_financial_goals | 財務目標 | 文字 |
| D_dreams | 夢想目標 | 文字 |
| D_short_term | 短期夢想 | 文字 |
| D_long_term | 長期夢想 | 文字 |
| D_motivations | 動機/渴望 | 文字 |
| H_health | 健康狀況 | 文字 |
| H_fitness | 健身/運動 | 文字 |
| H_diet | 飲食習慣 | 文字 |
| H_stress | 壓力來源 | 文字 |
| H_goals | 健康目標 | 文字 |

### 2.3 互動記錄
| 欄位 | 說明 |
|------|------|
| id | 互動記錄ID |
| contact_id | 聯絡人ID |
| type | 互動類型（聊天/關心/分享/邀約） |
| date | 互動日期 |
| content | 互動內容摘要 |
| notes | 備註 |
| channel | 管道（IG/LINE/電話/見面） |

---

## 3. 功能模組

### 3.1 聯絡人管理
- 新增/編輯/刪除聯絡人
- FORMDH 檔案建立與完善度追蹤
- 標籤系統（新人/舊人/高潛力/待追蹤等）
- 搜尋與篩選

### 3.2 自動互動規劃引擎
**邏輯**：
1. 取得所有聯絡人清單
2. 計算每人距離上次互動的天數
3. 若超過 25 天未互動 → 標記為「需要互動」
4. 自動在行事曆建立「關心聯繫」事件
5. 根據互動頻率動態調整優先順序

**優先級計算**：
- 優先級分數 = (天數未互動 × 2) + (完善度分數) + (潛力標籤加成)
- 潛力標籤：「高潛力」+10分，「新人」+5分

### 3.3 行事曆整合
- Google Calendar API 串接（讀寫）
- 或本地 CSV 匯出
- 事件類型：
  - 定期關心（每月一次）
  - 特別事件（生日、紀念日）
  - 自訂提醒

### 3.4 提醒通知
- LINE Notify / WeChat  webhook 通知
- 當天待聯繫名單
- 每週客戶摘要
- 月互動達成率報告

---

## 4. 技術架構

### 4.1 技術棧
- **語言**：Python 3.10+
- **資料庫**：SQLite（本地端，簡單好維護）
- **前端**：CLI 介面 + 網頁儀表板（可選）
- **行事曆**：Google Calendar API
- **通知**：LINE Notify / Webhook

### 4.2 目錄結構
```
覺醒行動app/
├── SPEC.md              # 規格書
├── README.md           # 使用說明
├── requirements.txt    # 依賴套件
├── main.py             # 主程式入口
├── config.py           # 設定檔
├── database/
│   ├── __init__.py
│   ├── models.py       # 資料模型
│   ├── database.py     # 資料庫連線
│   └── migrations/     # 資料庫遷移
├── modules/
│   ├── __init__.py
│   ├── contacts.py     # 聯絡人管理
│   ├── formdh.py       # FORMDH 檔案管理
│   ├── planner.py      # 自動規劃引擎
│   ├── calendar.py     # 行事曆整合
│   └── notifications.py # 通知系統
├── data/               # 資料存放
│   ├── awakening.db        # SQLite 資料庫
│   └── exports/        # 匯出檔案
└── tests/              # 測試
    └── test_*.py
```

### 4.3 資料庫 Schema
```sql
-- 聯絡人表
CREATE TABLE contacts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT,
    tags TEXT,  -- JSON array
    created_at TEXT,
    updated_at TEXT,
    last_interaction TEXT,
    interaction_count INTEGER DEFAULT 0
);

-- FORMDH 檔案表
CREATE TABLE formdh_profiles (
    id TEXT PRIMARY KEY,
    contact_id TEXT UNIQUE REFERENCES contacts(id),
    -- F
    f_family TEXT,
    f_family_notes TEXT,
    -- O
    o_occupation TEXT,
    o_occupation_notes TEXT,
    o_work_style TEXT,
    -- R
    r_interests TEXT,  -- JSON array
    r_interests_detail TEXT,
    r_hobbies TEXT,
    -- M
    m_money_values TEXT,
    m_income_range TEXT,
    m_investment TEXT,
    m_financial_goals TEXT,
    -- D
    d_dreams TEXT,
    d_short_term TEXT,
    d_long_term TEXT,
    d_motivations TEXT,
    -- H
    h_health TEXT,
    h_fitness TEXT,
    h_diet TEXT,
    h_stress TEXT,
    h_goals TEXT,
    -- 完整度計算
    completeness_score INTEGER DEFAULT 0,
    updated_at TEXT
);

-- 互動記錄表
CREATE TABLE interactions (
    id TEXT PRIMARY KEY,
    contact_id TEXT REFERENCES contacts(id),
    type TEXT,  -- chat/care/share/invite
    date TEXT,
    content TEXT,
    notes TEXT,
    channel TEXT,  -- IG/LINE/phone/meet
    created_at TEXT
);

-- 行事曆事件表
CREATE TABLE calendar_events (
    id TEXT PRIMARY KEY,
    contact_id TEXT REFERENCES contacts(id),
    title TEXT,
    description TEXT,
    event_date TEXT,
    event_time TEXT,
    event_type TEXT,  -- reminder/birthday/followup
    google_event_id TEXT,
    status TEXT,  -- pending/completed/cancelled
    created_at TEXT
);

-- 系統設定表
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

---

## 5. 使用者流程

### 5.1 初次使用
1. 啟動程式
2. 輸入基本設定（LINE Notify Token 等）
3. 開始新增第一位聯絡人

### 5.2 日常使用
1. **新增新人** → 填寫 FORMDH 檔案 → 系統自動排入互動時程
2. **每日啟動** → 查看今日待聯繫名單 → 執行關心互動
3. **每週回顧** → 查看互動達成率 → 調整規劃

### 5.3 自動流程
- 每天早上 9:00 發送今日待聯繫名單
- 每月底檢查是否有超過 30 天未互動的人
- 自動在 Google Calendar 建立「關心」時段

---

## 6. 產出成果

### CLI 指令
```bash
# 聯絡人管理
python main.py add "王小明" --source IG
python main.py list --tag 新人
python main.py edit <id> --formdh
python main.py delete <id>

# FORMDH 檔案
python main.py profile <id>  # 查看檔案
python main.py profile <id> --fill  # 互動式填寫

# 互動記錄
python main.py interact <id> --type chat --content "聊了工作機會"

# 規劃與提醒
python main.py plan          # 產生本月規劃
python main.py today         # 今日待辦
python main.py overdue       # 逾期未聯繫

# 行事曆同步
python main.py calendar sync
python main.py calendar export --format csv

# 通知測試
python main.py notify test
```

---

## 7. 開發階段規劃

### Phase 1：核心功能（MVP）
- [ ] 專案架構建立
- [ ] SQLite 資料庫設定
- [ ] 聯絡人 CRUD
- [ ] FORMDH 檔案管理
- [ ] 基本 CLI 介面

### Phase 2：互動規劃
- [ ] 自動規劃引擎
- [ ] 優先級計算
- [ ] 互動記錄追蹤
- [ ] 逾期名單查詢

### Phase 3：行事曆整合
- [ ] Google Calendar API 串接
- [ ] 事件同步
- [ ] CSV 匯出

### Phase 4：通知系統
- [ ] LINE Notify 整合
- [ ] 每日提醒
- [ ] 達成率報告

---

## 8. 成功指標

- 每月底互動達成率 > 90%
- FORMDH 檔案完整度平均 > 60%
- 使用者每日主動開啟使用
