# -*- coding: utf-8 -*-
"""
覺醒行動app - 公開版（無需登入，雲端儲存自選）
每個人第一次使用需自行設定儲存路徑（OneDrive / iCloud / Google Drive 等）
"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
import json
from pathlib import Path

from config import BASE_DIR
from database import Database

# ========== 雲端儲存設定 ==========
CONFIG_FILE = BASE_DIR / "storage_config.json"

def get_storage_path():
    """讀取儲存路徑，沒設定過就回傳 None"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("storage_path")
        except:
            pass
    return None

def is_storage_configured():
    return get_storage_path() is not None

def save_storage_path(path):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "storage_path": path,
            "set_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }, f, ensure_ascii=False)

def get_storage_info():
    path = get_storage_path()
    if not path:
        return {"type": "未設定", "path": "", "size": "尚無資料"}

    if "OneDrive" in path or "onedrive" in path.lower():
        storage_type = "微軟 OneDrive"
    elif "iCloud" in path or "icloud" in path.lower():
        storage_type = "蘋果 iCloud"
    elif "Google Drive" in path or "google" in path.lower():
        storage_type = "Google 雲端硬碟"
    elif "Dropbox" in path or "dropbox" in path.lower():
        storage_type = "Dropbox"
    elif path.startswith("\\\\") or (len(path) > 2 and path[1] == ":"):
        storage_type = "本機/網路資料夾"
    else:
        storage_type = "自訂路徑"

    db_file = Path(path) / "awakening.db"
    if db_file.exists():
        size = db_file.stat().st_size
        size_str = f"{size / 1024 / 1024:.1f} MB" if size > 1024 * 1024 else f"{size / 1024:.0f} KB"
    else:
        size_str = "尚無資料"

    return {"type": storage_type, "path": path, "size": size_str}

# 動態設定資料庫路徑
_storage = get_storage_path()
if _storage:
    STORAGE_DIR = Path(_storage)
else:
    STORAGE_DIR = BASE_DIR / "data"  # 暫時，會在 settings 建立
os.makedirs(STORAGE_DIR, exist_ok=True)
DB_PATH = STORAGE_DIR / "awakening.db"

import config as _cfg
_cfg.DB_PATH = str(DB_PATH)

# ========== 自動同步 NotebookLM ==========
def sync_notebooklm():
    """每次資料變動時，自動更新儲存位置的 .md 檔與行動快速查閱版 .html 檔"""
    try:
        storage_path = get_storage_path()
        if not storage_path:
            return
            
        # 1. 產生 NotebookLM .md 檔
        md_path = Path(storage_path) / "覺醒CRM_NotebookLM.md"
        contacts = db.get_all_contacts()
        lines = []
        lines.append(f"# 覺醒行動app - 聯絡人資料\n")
        lines.append(f"自動同步時間：{now_str()}  |  共 {len(contacts)} 位聯絡人\n---\n")

        html_contacts = []

        for c in contacts:
            lines.append(f"## {c['name']}")
            if c.get('source'): lines.append(f"- 來源：{c['source']}")
            if c.get('from_app'): lines.append(f"- 來源 App：{c['from_app']}")
            if c.get('tags'):
                tags = json.loads(c.get('tags', '[]'))
                if tags: lines.append(f"- 標籤：{', '.join(tags)}")
            if c.get('notes'): lines.append(f"- 備註：{c['notes']}")

            profile = db.get_formdh_profile(c['id'])
            if profile:
                lines.append("\n### FORMDH 檔案")
                sections = [
                    ("家庭 (Family)", [("家庭狀況", 'f_family'), ("家庭備註", 'f_family_notes')]),
                    ("工作 (Occupation)", [("職業", 'o_occupation'), ("工作備註", 'o_occupation_notes'), ("工作風格", 'o_work_style')]),
                    ("興趣 (Recreation)", [("興趣", 'r_interests'), ("興趣細節", 'r_interests_detail'), ("嗜好", 'r_hobbies')]),
                    ("金錢觀 (Money)", [("金錢價值觀", 'm_money_values'), ("收入範圍", 'm_income_range'), ("投資", 'm_investment'), ("財務目標", 'm_financial_goals')]),
                    ("夢想 (Dreams)", [("夢想", 'd_dreams'), ("短期目標", 'd_short_term'), ("長期目標", 'd_long_term'), ("動力來源", 'd_motivations')]),
                    ("健康 (Health)", [("健康狀況", 'h_health'), ("健身習慣", 'h_fitness'), ("飲食", 'h_diet'), ("壓力", 'h_stress'), ("健康目標", 'h_goals')]),
                ]
                for section_name, fields in sections:
                    vals = [(label, profile.get(f, '')) for label, f in fields if profile.get(f)]
                    if vals:
                        lines.append(f"\n**{section_name}**")
                        for label, val in vals:
                            lines.append(f"- {label}：{val}")

            interactions = db.get_interactions(c['id'])
            if interactions:
                lines.append(f"\n### 互動記錄（共 {len(interactions)} 次）")
                for i in interactions[:10]:
                    date = i.get('date', '?')
                    tp = i.get('type', '')
                    content = i.get('content', '')[:100]
                    lines.append(f"- {date} [{tp}] {content}")
                if len(interactions) > 10:
                    lines.append(f"- ...另有 {len(interactions) - 10} 筆記錄")

            lines.append("\n---\n")

            # 收集 JSON 資料以產生 HTML 查閱版
            tags_list = json.loads(c.get('tags', '[]')) if c.get('tags') else []
            html_contacts.append({
                "id": c['id'],
                "name": c['name'],
                "source": c.get('source', ''),
                "from_app": c.get('from_app', ''),
                "image_path": c.get('image_path', ''),
                "tags": tags_list,
                "notes": c.get('notes', ''),
                "last_interaction": c.get('last_interaction', '從未'),
                "interaction_count": c.get('interaction_count', 0),
                "profile": profile or {},
                "interactions": interactions or []
            })

        md_content = '\n'.join(lines)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        # 2. 產生行動快速查閱版 .html 檔
        html_path = Path(storage_path) / "覺醒CRM_快速查閱版.html"
        html_content = get_static_html_template(html_contacts, now_str())
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    except Exception as e:
        print(f"同步雲端同步檔案失敗：{e}")

def get_static_html_template(contacts_data, sync_time):
    """回傳包含完整 JSON 資料庫與前端搜尋邏輯的 HTML 模板"""
    contacts_json = json.dumps(contacts_data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>覺醒 CRM 快速查閱版</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body {{
            background-color: #f8fafc;
            color: #1e293b;
            font-family: system-ui, -apple-system, sans-serif;
            padding-bottom: 50px;
        }}
        .navbar {{
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }}
        .search-card {{
            border-radius: 16px;
            border: none;
            box-shadow: 0 4px 20px rgba(0,0,0,0.03);
            margin-bottom: 20px;
        }}
        .contact-card {{
            border-radius: 12px;
            border: none;
            box-shadow: 0 2px 10px rgba(0,0,0,0.02);
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 12px;
        }}
        .contact-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.06);
            border-left: 4px solid #4f46e5;
        }}
        .active-contact {{
            border-left: 4px solid #4f46e5 !important;
            background-color: #f0fdf4 !important;
        }}
        .badge-tag {{
            font-size: 11px;
            border-radius: 6px;
            padding: 3px 6px;
            font-weight: 600;
        }}
        .formdh-card {{
            border-radius: 16px;
            border: none;
            box-shadow: 0 4px 25px rgba(0,0,0,0.04);
            background: white;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .formdh-section {{
            background: #f8fafc;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .formdh-section h5 {{
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 10px;
            color: #1e293b;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .ai-suggestion-box {{
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 12px;
            border-left: 4px solid #4f46e5;
            background: #fafafa;
        }}
        .ai-suggestion-box h6 {{
            font-weight: 700;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 6px;
        }}
        .list-container {{
            max-height: 80vh;
            overflow-y: auto;
            padding-right: 5px;
        }}
        .list-container::-webkit-scrollbar {{
            width: 6px;
        }}
        .list-container::-webkit-scrollbar-track {{
            background: #f1f5f9;
        }}
        .list-container::-webkit-scrollbar-thumb {{
            background: #cbd5e1;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <nav class="navbar navbar-dark py-3">
        <div class="container d-flex justify-content-between align-items-center">
            <span class="navbar-brand mb-0 h1 font-weight-bold">
                <i class="fas fa-heart"></i> 覺醒 CRM 行動查閱版
            </span>
            <span class="text-white-50" style="font-size:12px;">
                最後同步時間：{sync_time}
            </span>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row">
            <!-- 左欄：搜尋與列表 -->
            <div class="col-lg-5 col-md-12">
                <div class="card search-card p-3">
                    <input type="text" id="searchBar" class="form-control" placeholder="搜尋姓名、來源、興趣、標籤..." onkeyup="filterContacts()">
                    <div class="mt-2 d-flex flex-wrap gap-1" id="tagFilterButtons">
                        <!-- 由 JS 動態繪製標籤過濾按鈕 -->
                    </div>
                </div>

                <div class="list-container" id="contactsList">
                    <!-- 由 JS 動態載入聯絡人列表 -->
                </div>
            </div>

            <!-- 右欄：詳細資料與 AI 建議 -->
            <div class="col-lg-7 col-md-12">
                <div id="detailContainer">
                    <div class="text-center py-5 formdh-card text-muted">
                        <i class="fas fa-users-cog" style="font-size: 48px; color: #cbd5e1;"></i>
                        <h5 class="mt-3 font-weight-bold">請選擇聯絡人</h5>
                        <p style="font-size: 13px;">點擊左側列表的聯絡人，即可在此查閱詳細 FORMDH 檔案與 AI 聊天話題建議。</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 行動端詳情彈出視窗 (Modal) -->
    <div class="modal fade" id="detailModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-scrollable modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title font-weight-bold" id="modalTitle">聯絡人詳情</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body" id="modalBody">
                    <!-- 由 JS 動態載入 -->
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const contacts = {contacts_json};
        let activeContactId = null;
        let activeTagFilter = null;
        let detailModal = null;

        document.addEventListener("DOMContentLoaded", () => {{
            detailModal = new bootstrap.Modal(document.getElementById('detailModal'));
            renderTagFilters();
            renderList();
        }});

        // 提取並渲染所有標籤過濾按鈕
        function renderTagFilters() {{
            const tagSet = new Set();
            contacts.forEach(c => {{
                if (c.tags) {{
                    c.tags.forEach(t => tagSet.add(t));
                }}
            }});
            
            const container = document.getElementById("tagFilterButtons");
            let html = '<button class="btn btn-xs btn-outline-secondary py-0 px-2 active-tag" onclick="selectTagFilter(null)" style="font-size:12px;">全部</button>';
            tagSet.forEach(tag => {{
                html += `<button class="btn btn-xs btn-outline-primary py-0 px-2" onclick="selectTagFilter(\'${{tag}}\')" style="font-size:12px;">#${{tag}}</button>`;
            }});
            container.innerHTML = html;
        }}

        function selectTagFilter(tag) {{
            activeTagFilter = tag;
            const buttons = document.querySelectorAll("#tagFilterButtons button");
            buttons.forEach(btn => {{
                if (tag === null && btn.innerText === "全部") {{
                    btn.classList.add("btn-secondary");
                    btn.classList.remove("btn-outline-secondary");
                }} else if (tag !== null && btn.innerText === "#" + tag) {{
                    btn.classList.add("btn-primary");
                    btn.classList.remove("btn-outline-primary");
                }} else {{
                    btn.classList.remove("btn-primary", "btn-secondary");
                    btn.classList.add(btn.innerText === "全部" ? "btn-outline-secondary" : "btn-outline-primary");
                }}
            }});
            filterContacts();
        }}

        // 渲染列表
        function renderList(filteredContacts = contacts) {{
            const container = document.getElementById("contactsList");
            if (filteredContacts.length === 0) {{
                container.innerHTML = '<div class="text-center py-5 text-muted">查無符合的聯絡人</div>';
                return;
            }}
            
            let html = "";
            filteredContacts.forEach(c => {{
                const activeClass = c.id === activeContactId ? 'active-contact' : '';
                let tagsHtml = "";
                if (c.tags) {{
                    c.tags.forEach(t => {{
                        tagsHtml += `<span class="badge bg-light text-primary me-1 border">${{t}}</span>`;
                    }});
                }}
                
                html += `
                    <div class="card contact-card p-3 ${{activeClass}}" onclick="viewContact(\'${{c.id}}\')">
                        <div class="d-flex justify-content-between align-items-center">
                            <h5 class="mb-1 font-weight-bold" style="font-size: 16px;">${{c.name}}</h5>
                            <span class="text-muted" style="font-size: 11px;">上回聯絡: ${{c.last_interaction}}</span>
                        </div>
                        <div style="font-size:12px;color:#666;" class="mb-2">來源: ${{c.source || \'-\'}} | 互動: ${{c.interaction_count}}次</div>
                        <div class="d-flex flex-wrap gap-1">${{tagsHtml}}</div>
                    </div>
                `;
            }});
            container.innerHTML = html;
        }}

        // 搜尋過濾
        function filterContacts() {{
            const query = document.getElementById("searchBar").value.toLowerCase().trim();
            const filtered = contacts.filter(c => {{
                const matchQuery = !query || 
                    c.name.toLowerCase().includes(query) ||
                    (c.source && c.source.toLowerCase().includes(query)) ||
                    (c.notes && c.notes.toLowerCase().includes(query)) ||
                    (c.profile && Object.values(c.profile).some(v => typeof v === \'string\' && v.toLowerCase().includes(query))) ||
                    (c.tags && c.tags.some(t => t.toLowerCase().includes(query)));
                
                const matchTag = !activeTagFilter || (c.tags && c.tags.includes(activeTagFilter));
                
                return matchQuery && matchTag;
            }});
            renderList(filtered);
        }}

        // 查閱聯絡人詳情
        function viewContact(id) {{
            activeContactId = id;
            
            const cards = document.querySelectorAll(".contact-card");
            cards.forEach(c => c.classList.remove("active-contact"));
            
            const contact = contacts.find(c => c.id === id);
            if (!contact) return;
            
            const detailHtml = getDetailHtml(contact);
            
            if (window.innerWidth < 768) {{
                document.getElementById("modalTitle").innerText = contact.name + " 的資料";
                document.getElementById("modalBody").innerHTML = detailHtml;
                detailModal.show();
            }} else {{
                document.getElementById("detailContainer").innerHTML = detailHtml;
                // 加入桌面版高亮效果
                const clickedCard = document.querySelector(`.contact-card[onclick*="${{id}}"]`);
                if (clickedCard) clickedCard.classList.add("active-contact");
            }}
        }}

        // 產生詳情 HTML
        function getDetailHtml(c) {{
            const p = c.profile || {{}};
            
            const sections = [
                {{ title: \'👨‍👩‍👧‍👦 F - 家庭\', key1: \'家庭狀況\', val1: p.f_family, key2: \'備註\', val2: p.f_family_notes, color: \'#e0e7ff\' }},
                {{ title: \'💼 O - 工作\', key1: \'職業\', val1: p.o_occupation, key2: \'型態/狀況\', val2: p.o_work_style || p.o_occupation_notes, color: \'#fef3c7\' }},
                {{ title: \'🎯 R - 興趣\', key1: \'興趣/愛好\', val1: p.r_interests, key2: \'詳細描述\', val2: p.r_interests_detail || p.r_hobbies, color: \'#d1fae5\' }},
                {{ title: \'💰 M - 金錢觀\', key1: \'價值觀\', val1: p.m_money_values, key2: \'財務目標\', val2: p.m_financial_goals, color: \'#fee2e2\' }},
                {{ title: \'🌟 D - 夢想\', key1: \'夢想目標\', val1: p.d_dreams, key2: \'渴望/動機\', val2: p.d_motivations, color: \'#faf5ff\' }},
                {{ title: \'💪 H - 健康\', key1: \'健康狀況\', val1: p.h_health, key2: \'飲食與運動\', val2: p.h_fitness || p.h_diet, color: \'#ecfeff\' }}
            ];
            
            let formdhHtml = "";
            sections.forEach(s => {{
                if (s.val1 || s.val2) {{
                    formdhHtml += `
                        <div class="formdh-section" style="background-color: ${{s.color}}40;">
                            <h5>${{s.title}}</h5>
                            ${{s.val1 ? `<div class="mb-1"><strong>${{s.key1}}：</strong>${{s.val1}}</div>` : \'\'}}
                            ${{s.val2 ? `<div><strong>${{s.key2}}：</strong>${{s.val2}}</div>` : \'\'}}
                        </div>
                    `;
                }}
            }});
            
            if (!formdhHtml) {{
                formdhHtml = \'<div class="text-muted text-center py-3">尚無 FORMDH 檔案記錄</div>\';
            }}
            
            const aiSuggestionsHtml = `
                <div class="formdh-card" style="border-left: 5px solid #4f46e5;">
                    <h5 class="font-weight-bold text-primary mb-3"><i class="fas fa-robot"></i> AI 智慧經營建議</h5>
                    <div class="ai-suggestion-box" style="border-left-color: #4f46e5;">
                        <h6 style="color:#4f46e5;"><i class="fas fa-comment-dots"></i> 聊天建議方向</h6>
                        <p class="mb-0" style="font-size:13px;line-height:1.6;">${{p.ai_chat_suggestions || \'尚無建議，可在 App 中點選「AI 重新分析」產生。\'}}</p>
                    </div>
                    <div class="ai-suggestion-box" style="border-left-color: #10b981;">
                        <h6 style="color:#10b981;"><i class="fas fa-newspaper"></i> 推薦聊天時事與話題</h6>
                        <p class="mb-0" style="font-size:13px;line-height:1.6;">${{p.ai_current_affairs || \'尚無話題推薦。\'}}</p>
                    </div>
                    <div class="ai-suggestion-box" style="border-left-color: #f59e0b;">
                        <h6 style="color:#f59e0b;"><i class="fas fa-question-circle"></i> 缺漏資訊引導問法</h6>
                        <p class="mb-0" style="font-size:13px;line-height:1.6;">${{p.ai_missing_info_suggestions || \'尚無問法建議。\'}}</p>
                    </div>
                </div>
            `;
            
            let interactionsHtml = "";
            if (c.interactions && c.interactions.length > 0) {{
                interactionsHtml += `
                    <div class="formdh-card">
                        <h5 class="font-weight-bold text-dark mb-3"><i class="fas fa-history"></i> 最近的互動記錄</h5>
                        <div class="table-responsive">
                            <table class="table table-sm table-striped" style="font-size:13px;">
                                <thead>
                                    <tr><th>日期</th><th>類型</th><th>管道</th><th>內容</th></tr>
                                </thead>
                                <tbody>
                `;
                
                c.interactions.slice(0, 10).forEach(i => {{
                    interactionsHtml += `
                        <tr>
                            <td>${{i.date}}</td>
                            <td>${{i.type}}</td>
                            <td>${{i.channel || \'-\'}}</td>
                            <td>${{i.content}}</td>
                        </tr>
                    `;
                }});
                
                interactionsHtml += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }}
            
            return `
                <div class="formdh-card">
                    <div class="d-flex justify-content-between align-items-center mb-3 border-bottom pb-3">
                        <div>
                            <h2 class="mb-0 font-weight-bold">${{c.name}}</h2>
                            <p class="text-muted mb-0" style="font-size: 13px;">來源: ${{c.source || \'-\'}} | 備註: ${{c.notes || \'-\'}}</p>
                        </div>
                        <span class="badge bg-primary" style="font-size:12px;padding:6px 12px;">完整度 ${{p.completeness_score || 0}}%</span>
                    </div>
                    
                    <h5 class="font-weight-bold text-dark mb-3"><i class="fas fa-id-card"></i> 檔案明細</h5>
                    ${{formdhHtml}}
                </div>
                
                ${{aiSuggestionsHtml}}
                
                ${{interactionsHtml}}
            `;
        }}
    </script>
</body>
</html>
"""

# ========== Flask ==========
app = Flask(__name__)

# secret_key 固定化：每次重啟使用相同的 key，避免 session 失效
def _load_or_create_secret_key():
    """從 storage_config.json 讀取 secret_key，若沒有則自動生成並寫入，確保重啟後 session 不失效"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("secret_key"):
                return cfg["secret_key"]
            # 自動生成並寫入
            import secrets
            new_key = secrets.token_hex(32)
            cfg["secret_key"] = new_key
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False)
            return new_key
    except Exception as e:
        print(f"⚠️ [secret_key] 讀取/寫入失敗，使用臨時 key: {e}")
    import secrets
    return secrets.token_hex(32)

app.secret_key = _load_or_create_secret_key()

@app.template_filter('fromjson')
def fromjson_filter(s):
    if not s:
        return []
    try:
        return json.loads(s)
    except:
        return []

db = Database()

# ========== 每2小時進度通知排程器 ==========
import threading
import time

def send_two_hourly_progress_notification():
    """發送每2小時進度通知"""
    try:
        today_date = datetime.now().strftime("%Y-%m-%d")
        events = db.get_calendar_events()
        
        # 篩選今日事件
        today_events = [e for e in events if e.get("event_date") == today_date]
        if not today_events:
            # 今日無任何任務，不發送通知
            return
            
        remaining_count = sum(1 for e in today_events if e.get("status") == "pending")
        completed_count = sum(1 for e in today_events if e.get("status") == "completed")
        total_count = len(today_events)
        
        # 如果沒有未完成的任務，就不再發送提醒，避免打擾使用者
        if remaining_count == 0:
            print("⏰ [排程器] 今日任務已全部完成，不發送2小時提醒。")
            return
            
        message = f"🔔 每2小時關心進度提醒\n\n今日聊天計畫進度：\n• 總任務：{total_count} 個\n• 已完成：{completed_count} 個\n• 還差：{remaining_count} 個任務未完成！\n"
        message += "\n💪 還要繼續加油喔！記得在聊天後將任務打勾完成並更新進度。"
            
        print(f"⏰ [排程器] 發送每2小時進度通知:\n{message}")
        
        # 使用 NotificationManager 發送
        from modules.notifications import NotificationManager
        notifier = NotificationManager(db)
        notifier.send_all_notifications(message)
    except Exception as e:
        print(f"❌ 每2小時進度通知發送異常: {e}")

def start_notification_scheduler():
    def scheduler_loop():
        # 等待 10 秒確保 app 已完全啟動
        time.sleep(10)
        print("⏰ 每2小時進度通知排程器已啟動...")
        while True:
            now = datetime.now()
            # 計算到下一個偶數整點的秒數
            next_run = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            if next_run.hour % 2 != 0:
                next_run = next_run + timedelta(hours=1)
            sleep_seconds = (next_run - now).total_seconds()
            if sleep_seconds < 10:
                sleep_seconds = 7200
                
            time.sleep(sleep_seconds)
            send_two_hourly_progress_notification()
            
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

start_notification_scheduler()

# ========== 輔助 ==========
def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

# ========== 全域變數注入 ==========
@app.context_processor
def inject_today_progress():
    try:
        today_date = datetime.now().strftime("%Y-%m-%d")
        events = db.get_calendar_events()
        today_events = []
        for e in events:
            if e.get("event_date") == today_date:
                contact = db.get_contact(e.get("contact_id"))
                if contact:
                    today_events.append(e)
        total = len(today_events)
        completed = sum(1 for e in today_events if e.get("status") == "completed")
        pending = sum(1 for e in today_events if e.get("status") == "pending")
        return {
            "global_today_total": total,
            "global_today_completed": completed,
            "global_today_pending": pending
        }
    except Exception:
        return {
            "global_today_total": 0,
            "global_today_completed": 0,
            "global_today_pending": 0
        }

# ========== 路由 ==========

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/uploads/<path:filename>')
def send_upload(filename):
    from flask import send_from_directory
    return send_from_directory(BASE_DIR / 'uploads', filename)

@app.route('/')
def index():
    if not is_storage_configured():
        return redirect(url_for('settings'))
    return redirect(url_for('calendar_view'))

# --- 儀表板 ---

@app.route('/dashboard')
def dashboard():
    if not is_storage_configured():
        return redirect(url_for('settings'))

    from modules.planner import Planner
    planner = Planner(db)
    planner.auto_schedule_interactions()

    contacts = db.get_all_contacts()
    now = datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")

    new_this_month = sum(1 for c in contacts if c.get("created_at", "") >= month_start)
    overdue_date = (now - timedelta(days=25)).strftime("%Y-%m-%d")
    overdue = [c for c in contacts if not c.get("last_interaction") or c["last_interaction"] < overdue_date]

    all_interactions = db.get_all_interactions()
    month_interactions = [i for i in all_interactions if i.get("date", "") >= month_start]

    completeness_avg = 0
    if contacts:
        total_score = sum(
            db.get_formdh_profile(c["id"]).get("completeness_score", 0)
            for c in contacts
        )
        completeness_avg = total_score // len(contacts)

    from modules.planner import Planner
    planner = Planner(db)
    today_tasks = planner.get_today_tasks()[:8]
    upcoming = planner.get_overdue_contacts()[:5]

    storage = get_storage_info()

    return render_template('dashboard.html',
        total=len(contacts),
        new_this_month=new_this_month,
        month_interactions=len(month_interactions),
        overdue=len(overdue),
        completeness_avg=completeness_avg,
        today_tasks=today_tasks,
        upcoming=upcoming,
        storage=storage
    )

# --- 聯絡人列表 ---

@app.route('/contacts')
def contact_list():
    keyword = request.args.get('keyword', '')
    tag = request.args.get('tag', '')

    if keyword:
        contacts = db.search_contacts(keyword)
    elif tag:
        contacts = db.get_contacts_by_tag(tag)
    else:
        contacts = db.get_all_contacts()

    return render_template('contacts.html', contacts=contacts, keyword=keyword, tag=tag)

@app.route('/contacts/add', methods=['GET', 'POST'])
def add_contact():
    if request.method == 'POST':
        name = request.form.get('name')
        source = request.form.get('source', '')
        from_app = request.form.get('from_app', '')
        category = request.form.get('category', '')
        tags_str = request.form.get('tags', '')
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]

        # 清除可能重複或衝突的舊 A/B/C 標籤
        tags = [t for t in tags if t.strip().upper() not in ['A', 'B', 'C', 'A類', 'B類', 'C類']]

        # 若選擇分類，將分類加入標籤最前方
        if category in ['A', 'B', 'C']:
            tags.insert(0, category)

        # 處理圖片上傳
        image_path = ''
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                import uuid
                ext = os.path.splitext(file.filename)[1]
                filename = f"avatar_{uuid.uuid4().hex[:10]}{ext}"
                filepath = BASE_DIR / "uploads" / filename
                os.makedirs(filepath.parent, exist_ok=True)
                file.save(filepath)
                image_path = filename

        from database.models import Contact
        contact = Contact(name=name, source=source, tags=tags, image_path=image_path, from_app=from_app)

        if db.add_contact(contact):
            flash(f'✅ 已新增：{name}', 'success')
            return redirect(url_for('edit_formdh', contact_id=contact.id))
        else:
            flash('❌ 新增失敗', 'error')

    return render_template('add_contact.html')

@app.route('/contacts/<contact_id>/edit', methods=['GET', 'POST'])
def edit_contact(contact_id):
    contact = db.get_contact(contact_id)
    if not contact:
        flash('找不到聯絡人', 'error')
        return redirect(url_for('contact_list'))

    if request.method == 'POST':
        name = request.form.get('name')
        source = request.form.get('source', '')
        from_app = request.form.get('from_app', '')
        category = request.form.get('category', '')
        tags_str = request.form.get('tags', '')
        notes = request.form.get('notes', '')
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]

        # 清除可能重複或衝突的舊 A/B/C 標籤
        tags = [t for t in tags if t.strip().upper() not in ['A', 'B', 'C', 'A類', 'B類', 'C類']]

        # 若選擇分類，將分類加入標籤最前方
        if category in ['A', 'B', 'C']:
            tags.insert(0, category)

        update_kwargs = {
            "name": name,
            "source": source,
            "from_app": from_app,
            "tags": json.dumps(tags, ensure_ascii=False),
            "notes": notes
        }

        # 處理圖片上傳
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                import uuid
                ext = os.path.splitext(file.filename)[1]
                filename = f"avatar_{uuid.uuid4().hex[:10]}{ext}"
                filepath = BASE_DIR / "uploads" / filename
                os.makedirs(filepath.parent, exist_ok=True)
                file.save(filepath)
                update_kwargs["image_path"] = filename

        db.update_contact(contact_id, **update_kwargs)
        flash('✅ 已更新', 'success')
        return redirect(url_for('view_contact', contact_id=contact_id))

    tags_list = json.loads(contact.get("tags", "[]"))
    # 判斷目前分類
    current_category = ""
    normalized_tags = [t.strip().upper() for t in tags_list]
    if 'A' in normalized_tags or 'A類' in tags_list:
        current_category = "A"
    elif 'B' in normalized_tags or 'B類' in tags_list:
        current_category = "B"
    elif 'C' in normalized_tags or 'C類' in tags_list:
        current_category = "C"

    # 從輸入框的標籤中排除分類標籤
    filtered_tags = [t for t in tags_list if t.strip().upper() not in ['A', 'B', 'C', 'A類', 'B類', 'C類']]
    tags_str = ", ".join(filtered_tags)
    return render_template('edit_contact.html', contact=contact, tags_str=tags_str, current_category=current_category)

@app.route('/contacts/<contact_id>/delete')
def delete_contact(contact_id):
    db.delete_contact(contact_id)
    flash('🗑️ 已刪除', 'success')
    return redirect(url_for('contact_list'))

# --- 聯絡人詳細 + FORMDH ---

@app.route('/contacts/<contact_id>')
def view_contact(contact_id):
    contact = db.get_contact(contact_id)
    if not contact:
        flash('找不到聯絡人', 'error')
        return redirect(url_for('contact_list'))

    profile = db.get_formdh_profile(contact_id)
    interactions = db.get_interactions(contact_id)

    from modules.formdh import FormDHManager
    formdh_mgr = FormDHManager(db)
    missing = formdh_mgr.get_missing_fields(contact_id)

    tags = json.loads(contact.get("tags", "[]"))

    return render_template('contact_detail.html',
        contact=contact, profile=profile,
        interactions=interactions[:20],
        missing_fields=missing[:8],
        tags=tags
    )

@app.route('/contacts/<contact_id>/formdh', methods=['GET', 'POST'])
def edit_formdh(contact_id):
    contact = db.get_contact(contact_id)
    if not contact:
        flash('找不到聯絡人', 'error')
        return redirect(url_for('contact_list'))

    if request.method == 'POST':
        updates = {}
        fields = [
            'f_family', 'f_family_notes',
            'o_occupation', 'o_occupation_notes', 'o_work_style',
            'r_interests', 'r_interests_detail', 'r_hobbies',
            'm_money_values', 'm_income_range', 'm_investment', 'm_financial_goals',
            'd_dreams', 'd_short_term', 'd_long_term', 'd_motivations',
            'h_health', 'h_fitness', 'h_diet', 'h_stress', 'h_goals'
        ]
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                updates[field] = val.strip()

        if updates:
            db.update_formdh_profile(contact_id, **updates)
            flash('✅ FORMDH 檔案已更新', 'success')

        return redirect(url_for('view_contact', contact_id=contact_id))

    profile = db.get_formdh_profile(contact_id)
    return render_template('edit_formdh.html', contact=contact, profile=profile)

@app.route('/contacts/<contact_id>/interact', methods=['POST'])
def add_interaction(contact_id):
    contact = db.get_contact(contact_id)
    if not contact:
        flash('找不到聯絡人', 'error')
        return redirect(url_for('contact_list'))

    from database.models import Interaction
    interaction = Interaction(
        contact_id=contact_id,
        type=request.form.get('type', 'chat'),
        date=request.form.get('date', today_str()),
        content=request.form.get('content', ''),
        notes='',
        channel=request.form.get('channel', '')
    )

    if db.add_interaction(interaction):
        flash('✅ 互動記錄已儲存', 'success')
    else:
        flash('❌ 記錄失敗', 'error')

    return redirect(url_for('view_contact', contact_id=contact_id))

# --- 規劃 ---

@app.route('/plan')
def plan_view():
    from modules.planner import Planner
    planner = Planner(db)
    planner.auto_schedule_interactions()
    
    import json
    contacts = db.get_all_contacts()
    list_a = []
    list_b = []
    list_c = []
    for c in contacts:
        try:
            tags = json.loads(c.get("tags", "[]"))
            normalized_tags = [t.strip().upper() for t in tags]
            if 'A' in normalized_tags or 'A類' in tags:
                list_a.append(c)
            elif 'B' in normalized_tags or 'B類' in tags:
                list_b.append(c)
            elif 'C' in normalized_tags or 'C類' in tags:
                list_c.append(c)
        except Exception as e:
            print(f"Error parsing tags for contact {c.get('name')}: {e}")
            
    return render_template('plan.html', list_a=list_a, list_b=list_b, list_c=list_c)

@app.route('/today')
def today_view():
    from modules.planner import Planner
    planner = Planner(db)
    planner.auto_schedule_interactions()
    tasks = planner.get_today_tasks()
    overdue = planner.get_overdue_contacts()
    
    # 取得今日排定的行事曆任務
    today_date = datetime.now().strftime("%Y-%m-%d")
    events = db.get_calendar_events()
    today_events = []
    for e in events:
        if e.get("event_date") == today_date:
            contact = db.get_contact(e["contact_id"])
            if not contact:
                continue
            today_events.append({
                "id": e["id"],
                "contact_id": e["contact_id"],
                "contact_name": contact["name"],
                "title": e["title"],
                "description": e["description"],
                "event_time": e["event_time"],
                "status": e["status"]
            })
            
    today_total_count = len(today_events)
    today_completed_count = sum(1 for e in today_events if e["status"] == "completed")
    today_pending_count = sum(1 for e in today_events if e["status"] == "pending")
    
    return render_template(
        'today.html', 
        tasks=tasks, 
        overdue=overdue,
        today_events=today_events,
        today_total_count=today_total_count,
        today_completed_count=today_completed_count,
        today_pending_count=today_pending_count
    )

@app.route('/plan/auto_schedule')
def auto_schedule():
    from modules.planner import Planner
    planner = Planner(db)
    
    contacts = db.get_all_contacts()
    if not contacts:
        flash('ℹ️ 目前無聯絡人資料，請先新增聯絡人或透過「AI 文字建檔」建立檔案。', 'info')
        return redirect(url_for('plan_view'))
        
    count = planner.auto_schedule_interactions()
    if count > 0:
        flash(f'✅ 已自動隨機平均分配聯絡人，並建立 {count} 個關心事件！', 'success')
    else:
        flash('ℹ️ 未能建立任何新的關心事件。', 'info')
        
    return redirect(url_for('plan_view'))

# --- 行事曆 ---

@app.route('/calendar')
def calendar_view():
    if not is_storage_configured():
        return redirect(url_for('settings'))

    from modules.planner import Planner
    planner = Planner(db)
    planner.auto_schedule_interactions()

    events = db.get_calendar_events()
    contacts = db.get_all_contacts()
    
    events_list = []
    for e in events:
        contact = db.get_contact(e["contact_id"])
        if not contact:
            continue
        events_list.append({
            "id": e["id"],
            "contact_id": e["contact_id"],
            "contact_name": contact["name"],
            "title": e["title"],
            "description": e["description"],
            "event_date": e["event_date"],
            "event_time": e["event_time"],
            "event_type": e["event_type"],
            "status": e["status"]
        })
        
    events_json_str = json.dumps(events_list, ensure_ascii=False)
    
    # 統計資訊
    now = datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    total_contacts = len(contacts)
    month_new = sum(1 for c in contacts if c.get("created_at", "") >= month_start)
    
    today_date = now.strftime("%Y-%m-%d")
    
    # 統計今日進度與待辦 (排除已刪除聯絡人)
    today_events_valid = []
    today_chats_count = 0
    for e in events:
        if e.get("event_date") == today_date:
            if db.get_contact(e.get("contact_id")):
                today_events_valid.append(e)
                if e.get("status") == "pending":
                    today_chats_count += 1

    today_total_count = len(today_events_valid)
    today_completed_count = sum(1 for e in today_events_valid if e.get("status") == "completed")
    today_pending_count = sum(1 for e in today_events_valid if e.get("status") == "pending")

    return render_template(
        'calendar.html', 
        events_json=events_json_str, 
        contacts=contacts,
        total_contacts=total_contacts,
        month_new=month_new,
        today_chats_count=today_chats_count,
        today_str=today_date,
        today_total_count=today_total_count,
        today_completed_count=today_completed_count,
        today_pending_count=today_pending_count
    )

@app.route('/calendar/complete/<event_id>')
def complete_event(event_id):
    db.update_calendar_event(event_id, status="completed")
    flash('✅ 已標記為完成', 'success')
    return redirect(url_for('calendar_view'))

@app.route('/calendar/complete_with_notes/<event_id>', methods=['POST'])
def complete_event_with_notes(event_id):
    chat_progress = request.form.get('chat_progress', '').strip()
    
    # 讀取行事曆事件
    events = db.get_calendar_events(include_cancelled=True)
    event = next((e for e in events if str(e["id"]) == str(event_id)), None)
    if not event:
        flash('❌ 找不到該聊天計畫', 'error')
        return redirect(request.referrer or url_for('calendar_view'))
        
    # 1. 更新事件狀態為已完成
    db.update_calendar_event(event_id, status="completed")
    
    # 2. 如果有輸入進度，更新至聯絡人備註與新增互動記錄
    contact = db.get_contact(event["contact_id"])
    if contact:
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # 建立互動記錄
        from database.models import Interaction
        interaction_content = chat_progress if chat_progress else f"完成排程聊天計畫: {event.get('title', '')}"
        interaction = Interaction(
            contact_id=event["contact_id"],
            type='chat',
            date=current_date,
            content=interaction_content,
            notes='由行事曆任務完成自動同步',
            channel='見面'
        )
        db.add_interaction(interaction)
        
        # 追加進度到新人的備註 (notes) 中
        if chat_progress:
            old_notes = contact.get("notes") or ""
            new_note_entry = f"\n[{current_date} 聊天進度] {chat_progress}"
            updated_notes = old_notes + new_note_entry if old_notes else new_note_entry.strip()
            db.update_contact(
                event["contact_id"],
                name=contact["name"],
                source=contact.get("source", ""),
                tags=contact.get("tags", "[]"),
                notes=updated_notes
            )
            flash(f'✅ 已標記完成，聊天進度已更新至 {contact["name"]} 的備註！', 'success')
        else:
            flash(f'✅ 已標記 {contact["name"]} 的聊天任務為完成！', 'success')
            
        # 3. 自動同步 NotebookLM
        sync_notebooklm()
    else:
        flash('✅ 任務已標記為完成', 'success')
        
    return redirect(request.referrer or url_for('calendar_view'))

@app.route('/calendar/cancel/<event_id>')
def cancel_event(event_id):
    db.update_calendar_event(event_id, status="cancelled")
    
    # 同步更新：取消後立即重新規劃，以遞補空缺
    from modules.planner import Planner
    planner = Planner(db)
    planner.auto_schedule_interactions()
    
    flash('🗑️ 已取消，已自動重新規劃遞補日程！', 'success')
    return redirect(url_for('calendar_view'))

# --- 智能更新 ---

@app.route('/smart_update', methods=['POST'])
def smart_update():
    """自然語言輸入，自動更新聯絡人資料"""
    text = request.form.get('text', '').strip()
    if not text:
        return jsonify({"status": "error", "msg": "請輸入內容"})

    # 簡單解析：找聯絡人 + 欄位
    contacts = db.get_all_contacts()
    matched_contact = None
    for c in contacts:
        if c['name'] in text:
            matched_contact = c
            break

    if not matched_contact:
        return jsonify({"status": "error", "msg": "找不到聯絡人，請在輸入中包含姓名"})

    # 解析要更新的欄位
    updates = {}
    profile_updates = {}

    # 工作相關
    if any(kw in text for kw in ['職業', '工作', '上班', '公司', '擔任', '當上']):
        for kw in ['職業', '工作', '上班', '公司']:
            if kw in text:
                idx = text.find(kw)
                # 提取關鍵字後的內容
                rest = text[idx+len(kw):].strip()
                rest = rest.split('，')[0].split('。')[0].split('、')[0][:50]
                if rest:
                    profile_updates['o_occupation'] = rest
                break

    # 家庭相關
    if any(kw in text for kw in ['女兒', '兒子', '小孩', '孩子', '家庭', '家人']):
        profile_updates['f_family_notes'] = text

    # 興趣相關
    if any(kw in text for kw in ['喜歡', '興趣', '嗜好', '愛', '熱愛', '爬山', '運動', '旅遊']):
        profile_updates['r_interests'] = text

    # 更新資料庫
    if profile_updates:
        db.update_formdh_profile(matched_contact['id'], **profile_updates)

    # 如果有提到互動，新增互動記錄
    if any(kw in text for kw in ['說', '告訴', '提到', '聊', '講']):
        from database.models import Interaction
        interaction = Interaction(
            contact_id=matched_contact['id'],
            type='chat',
            date=today_str(),
            content=text[:200],
            notes='',
            channel='智能更新'
        )
        db.add_interaction(interaction)

    # 自動同步到 NotebookLM
    sync_notebooklm()

    return jsonify({
        "status": "ok",
        "msg": f"✅ 已更新 {matched_contact['name']} 的資料",
        "contact_id": matched_contact['id']
    })

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """上傳圖片（名片/截圖），OCR 後自動建立或更新聯絡人"""
    if 'image' not in request.files:
        return jsonify({"status": "error", "msg": "請上傳圖片"})

    file = request.files['image']
    if file.filename == '':
        return jsonify({"status": "error", "msg": "請選擇圖片"})

    # 儲存圖片
    filename = f"ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = BASE_DIR / "uploads" / filename
    os.makedirs(filepath.parent, exist_ok=True)
    file.save(filepath)

    # 嘗試 OCR（需要 tesseract）
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, lang='chi_tra+eng')
    except:
        # 如果沒有 tesseract，回傳圖片已上傳
        return jsonify({
            "status": "ok",
            "msg": "圖片已上傳，請手動輸入內容",
            "image_path": str(filepath)
        })

    # 解析 OCR 結果，嘗試擷取姓名/公司/電話
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    name = ''
    company = ''
    phone = ''
    for line in lines:
        if not name and len(line) <= 6 and any('\u4e00' <= c <= '\u9fff' for c in line):
            name = line
        if '公司' in line or '有限公司' in line or '股份' in line:
            company = line
        if any(c.isdigit() for c in line) and ('-' in line or len(line) >= 8):
            phone = line

    # 建立或更新聯絡人
    if name:
        existing = db.search_contacts(name)
        if existing:
            contact_id = existing[0]['id']
        else:
            from database.models import Contact
            contact = Contact(name=name, source='名片OCR', tags=[])
            db.add_contact(contact)
            contact_id = contact.id

        if company:
            db.update_contact(contact_id, source=f"公司：{company}")

        sync_notebooklm()
        return jsonify({
            "status": "ok",
            "msg": f"✅ 已從名片建立/更新：{name}",
            "contact_id": contact_id,
            "ocr_text": text[:500]
        })
    else:
        return jsonify({
            "status": "ok",
            "msg": "OCR 完成，但未擷取到姓名，請手動輸入",
            "ocr_text": text[:500]
        })

# --- 設定 ---

@app.route('/settings')
def settings():
    storage = get_storage_info()
    storage_configured = is_storage_configured()
    
    # 讀取 API Keys
    gemini_api_key = ""
    openrouter_api_key = ""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                gemini_api_key = cfg.get("gemini_api_key", "")
                openrouter_api_key = cfg.get("openrouter_api_key", "")
        except:
            pass
    
    # 自動取得電腦的區域網路 IP 與 Tailscale IP
    import socket
    local_ip = "127.0.0.1"
    tailscale_ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        pass

    try:
        # 尋找 100.x.x.x 開頭的 Tailscale IP
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip.startswith("100."):
                tailscale_ip = ip
                break
    except:
        pass
        
    # 讀取 LINE Notify 設定
    line_notify_token = db.get_setting("line_notify_token", "")
    enable_line_notify = db.get_setting("enable_line_notify", "false") == "true"
    
    # 讀取 ntfy 設定
    ntfy_topic = db.get_setting("ntfy_topic", "")
    enable_ntfy = db.get_setting("enable_ntfy", "false") == "true"
        
    return render_template('settings.html', 
                           storage=storage, 
                           storage_configured=storage_configured, 
                           local_ip=local_ip,
                           tailscale_ip=tailscale_ip,
                           gemini_api_key=gemini_api_key,
                           openrouter_api_key=openrouter_api_key,
                           line_notify_token=line_notify_token,
                           enable_line_notify=enable_line_notify,
                           ntfy_topic=ntfy_topic,
                           enable_ntfy=enable_ntfy)

@app.route('/settings/keys', methods=['POST'])
def set_keys():
    gemini_key = request.form.get('gemini_api_key', '').strip()
    openrouter_key = request.form.get('openrouter_api_key', '').strip()
    
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except:
            pass
            
    cfg["gemini_api_key"] = gemini_key
    cfg["openrouter_api_key"] = openrouter_key
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)
        
    flash('✅ API 金鑰已儲存', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/line_notify', methods=['POST'])
def set_line_notify():
    token = request.form.get('line_notify_token', '').strip()
    enable = request.form.get('enable_line_notify')
    
    db.set_setting('line_notify_token', token)
    db.set_setting('enable_line_notify', 'true' if enable else 'false')
    
    flash('✅ LINE Notify 通知設定已儲存', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/line_notify/test', methods=['POST'])
def test_line_notify():
    from modules.notifications import NotificationManager
    
    token = request.json.get('line_notify_token', '').strip() if (request.is_json and request.json) else request.form.get('line_notify_token', '').strip()
    
    if not token:
        token = db.get_setting('line_notify_token')
        
    if not token:
        return jsonify({"success": False, "message": "請先輸入 LINE Notify Token"})
        
    notifier = NotificationManager(db)
    msg = f"🔔 覺醒行動app 手機提示測試\n\n時間：{datetime.now().strftime('%Y/%m/%d %H:%M')}\n狀態：手機提示與通知管道正常！\n\n當有今日待辦、逾期未聯繫客戶、或排程任務時，系統將會透過此管道主動推播訊息至您的手機。"
    success = notifier.send_line_notify(msg, token=token)
    
    if success:
        return jsonify({"success": True, "message": "測試通知已發送，請檢查手機 LINE！"})
    else:
        return jsonify({"success": False, "message": "發送失敗，請確認 Token 是否正確且有效"})

@app.route('/settings/ntfy', methods=['POST'])
def set_ntfy():
    topic = request.form.get('ntfy_topic', '').strip()
    enable = request.form.get('enable_ntfy')
    
    db.set_setting('ntfy_topic', topic)
    db.set_setting('enable_ntfy', 'true' if enable else 'false')
    
    flash('✅ ntfy 通知設定已儲存', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/ntfy/test', methods=['POST'])
def test_ntfy():
    from modules.notifications import NotificationManager
    
    topic = request.json.get('ntfy_topic', '').strip() if (request.is_json and request.json) else request.form.get('ntfy_topic', '').strip()
    
    if not topic:
        topic = db.get_setting('ntfy_topic')
        
    if not topic:
        return jsonify({"success": False, "message": "請先輸入 ntfy Topic"})
        
    notifier = NotificationManager(db)
    msg = f"🔔 覺醒行動app 手機提示測試\n\n時間：{datetime.now().strftime('%Y/%m/%d %H:%M')}\n狀態：手機提示與 ntfy 通知管道正常！\n\n當有今日待辦、逾期未聯繫客戶、或未完成任務時，系統將會透過此管道主動推播訊息至您的手機。"
    success = notifier.send_ntfy(msg, topic=topic)
    
    if success:
        return jsonify({"success": True, "message": f"測試通知已發送，請檢查手機 ntfy App 中的 [{topic}] 主題！"})
    else:
        return jsonify({"success": False, "message": "發送失敗，請確認網路連線與主題名稱是否正確"})

# --- AI 文字智慧建檔 ---

@app.route('/ai_text_import')
def ai_text_import():
    if not is_storage_configured():
        return redirect(url_for('settings'))
    contacts = db.get_all_contacts()
    return render_template('ai_text_import.html', contacts=contacts)

@app.route('/contacts/ai_import', methods=['POST'])
def contacts_ai_import():
    contact_id = request.form.get('contact_id')
    new_contact_name = request.form.get('new_contact_name', '').strip()
    raw_text = request.form.get('raw_text', '').strip()
    
    if not raw_text:
        flash('❌ 請提供對話或資料內容', 'error')
        return redirect(url_for('ai_text_import'))
        
    # 呼叫 AI 分析模組
    from modules.ai_analyst import analyze_contact_info
    
    # 讀取 API Key (可使用 storage_config.json 裡的)
    gemini_key = ""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                gemini_key = cfg.get("gemini_api_key", "")
        except:
            pass
            
    parsed_data = analyze_contact_info(text=raw_text, api_key=gemini_key)
    
    if parsed_data.get("status") == "error":
        flash(f"❌ AI 分析失敗：{parsed_data.get('msg')}", 'error')
        contacts = db.get_all_contacts()
        return render_template('ai_text_import.html', 
                               contacts=contacts,
                               contact_id=contact_id,
                               new_contact_name=new_contact_name,
                               raw_text=raw_text)
        
    # 1. 決定聯絡人
    if contact_id == 'new':
        name = new_contact_name or parsed_data.get('name')
        if not name or name == "提取的姓名":
            name = "全新 AI 朋友"
            
        from database.models import Contact
        tags = parsed_data.get('tags', [])
        contact = Contact(
            name=name,
            source=parsed_data.get('source') or 'AI 智慧建檔',
            tags=tags
        )
        if not db.add_contact(contact):
            flash('❌ 新增聯絡人失敗', 'error')
            contacts = db.get_all_contacts()
            return render_template('ai_text_import.html', 
                                   contacts=contacts,
                                   contact_id=contact_id,
                                   new_contact_name=new_contact_name,
                                   raw_text=raw_text)
        contact_id = contact.id
        flash(f'✅ 已成功建立全新新人聯絡人：{name}', 'success')
    else:
        contact = db.get_contact(contact_id)
        if not contact:
            flash('❌ 找不到指定的聯絡人', 'error')
            contacts = db.get_all_contacts()
            return render_template('ai_text_import.html', 
                                   contacts=contacts,
                                   contact_id=contact_id,
                                   new_contact_name=new_contact_name,
                                   raw_text=raw_text)
        flash(f'✅ 已成功更新聯絡人：{contact["name"]} 的 FORMDH 資訊', 'success')
        
    # 2. 更新 FORMDH 欄位
    fields = [
        'f_family', 'f_family_notes',
        'o_occupation', 'o_occupation_notes', 'o_work_style',
        'r_interests', 'r_interests_detail', 'r_hobbies',
        'm_money_values', 'm_income_range', 'm_investment', 'm_financial_goals',
        'd_dreams', 'd_short_term', 'd_long_term', 'd_motivations',
        'h_health', 'h_fitness', 'h_diet', 'h_stress', 'h_goals',
        'ai_chat_suggestions', 'ai_current_affairs', 'ai_missing_info_suggestions'
    ]
    updates = {}
    for f in fields:
        # 只在 AI 有提取出有效資訊時寫入，避免把原本已有的資料覆蓋為空
        val = parsed_data.get(f, '').strip()
        if val and val not in ["家庭狀況", "家庭狀況備註", "職業", "工作狀況備註", "工作型態", "興趣愛好", "興趣詳細描述", "業餘活動與嗜好", "金錢觀", "收入區間", "投資理財態度", "財務目標", "夢想目標", "短期夢想", "長期夢想", "動機與渴望", "健康狀況", "健身與運動習慣", "飲食與作息", "壓力來源", "健康目標", "AI 聊天與關係建立建議內容", "推薦聊天時事與話題", "目前缺少資訊的引導問話建議"]:
            updates[f] = val
            
    if updates:
        db.update_formdh_profile(contact_id, **updates)
        
    # 3. 新增一筆互動記錄
    from database.models import Interaction
    interaction = Interaction(
        contact_id=contact_id,
        type='chat',
        date=datetime.now().strftime("%Y-%m-%d"),
        content=f"透過 AI 文字分析自動建檔，輸入內容長度 {len(raw_text)} 字。",
        notes='由 AI 文字建檔功能自動生成',
        channel='系統'
    )
    db.add_interaction(interaction)
    
    # 4. 同步雲端及 NotebookLM
    sync_notebooklm()
    
    return redirect(url_for('view_contact', contact_id=contact_id))

@app.route('/calendar/add_event', methods=['POST'])
def add_calendar_event_custom():
    contact_id = request.form.get('contact_id')
    event_date = request.form.get('event_date')
    event_time = request.form.get('event_time', '12:00')
    title = request.form.get('title', '關心聊天')
    event_type = request.form.get('event_type', 'reminder')
    
    if not contact_id or not event_date:
        flash('❌ 聯絡人與日期為必填欄位', 'error')
        return redirect(url_for('calendar_view'))
        
    from database.models import CalendarEvent
    event = CalendarEvent(
        contact_id=contact_id,
        title=title,
        description='手動新增計劃',
        event_date=event_date,
        event_time=event_time,
        event_type=event_type,
        status='pending'
    )
    
    if db.add_calendar_event(event):
        flash('✅ 已排定聊天日程', 'success')
    else:
        flash('❌ 排定失敗', 'error')
        
    return redirect(url_for('calendar_view'))



@app.route('/settings/storage', methods=['POST'])
def set_storage():
    path = request.form.get('storage_path', '').strip()
    if not path:
        flash('❌ 請填寫路徑', 'error')
        return redirect(url_for('settings'))

    if os.path.exists(path):
        save_storage_path(path)
        flash('✅ 儲存路徑已設定！請重新啟動 App', 'success')
    else:
        try:
            os.makedirs(path, exist_ok=True)
            save_storage_path(path)
            flash('✅ 資料夾已建立並設為儲存路徑！請重新啟動 App', 'success')
        except Exception as e:
            flash(f'❌ 無法建立資料夾：{e}', 'error')

    return redirect(url_for('settings'))

@app.route('/settings/export_notebooklm')
def export_notebooklm():
    """匯出 NotebookLM Source：結構化 Markdown"""
    contacts = db.get_all_contacts()
    lines = []
    lines.append("# 覺醒行動app - 聯絡人資料\n")
    lines.append(f"匯出時間：{now_str()}  |  共 {len(contacts)} 位聯絡人\n---")

    for c in contacts:
        lines.append(f"\n## {c['name']}")
        if c.get('source'): lines.append(f"- 來源：{c['source']}")
        if c.get('tags'): 
            tags = json.loads(c.get('tags', '[]'))
            if tags: lines.append(f"- 標籤：{', '.join(tags)}")
        if c.get('notes'): lines.append(f"- 備註：{c['notes']}")

        # FORMDH
        profile = db.get_formdh_profile(c['id'])
        if profile:
            lines.append("\n### FORMDH 檔案")
            sections = [
                ("家庭 (Family)", [
                    ("家庭狀況", 'f_family'), ("家庭備註", 'f_family_notes')]),
                ("工作 (Occupation)", [
                    ("職業", 'o_occupation'), ("工作備註", 'o_occupation_notes'), ("工作風格", 'o_work_style')]),
                ("興趣 (Recreation)", [
                    ("興趣", 'r_interests'), ("興趣細節", 'r_interests_detail'), ("嗜好", 'r_hobbies')]),
                ("金錢觀 (Money)", [
                    ("金錢價值觀", 'm_money_values'), ("收入範圍", 'm_income_range'), ("投資", 'm_investment'), ("財務目標", 'm_financial_goals')]),
                ("夢想 (Dreams)", [
                    ("夢想", 'd_dreams'), ("短期目標", 'd_short_term'), ("長期目標", 'd_long_term'), ("動力來源", 'd_motivations')]),
                ("健康 (Health)", [
                    ("健康狀況", 'h_health'), ("健身習慣", 'h_fitness'), ("飲食", 'h_diet'), ("壓力", 'h_stress'), ("健康目標", 'h_goals')]),
            ]
            for section_name, fields in sections:
                vals = [(label, profile.get(f, '')) for label, f in fields if profile.get(f)]
                if vals:
                    lines.append(f"\n**{section_name}**")
                    for label, val in vals:
                        lines.append(f"- {label}：{val}")

        # 互動記錄
        interactions = db.get_interactions(c['id'])
        if interactions:
            lines.append(f"\n### 互動記錄（共 {len(interactions)} 次）")
            for i in interactions[:15]:
                date = i.get('date', '?')
                tp = i.get('type', '')
                ch = i.get('channel', '')
                content = i.get('content', '')
                line = f"- {date} [{tp}"
                if ch: line += f"/{ch}"
                line += f"] {content}"
                lines.append(line)
            if len(interactions) > 15:
                lines.append(f"- ...另有 {len(interactions) - 15} 筆記錄")

        lines.append("\n---")

    md = '\n'.join(lines)
    from flask import make_response
    resp = make_response(md)
    resp.headers['Content-Type'] = 'text/markdown; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename=覺醒CRM_NotebookLM_{today_str()}.md'
    return resp

@app.route('/settings/export')
def export_data():
    contacts = db.get_all_contacts()
    data = []
    for c in contacts:
        profile = db.get_formdh_profile(c["id"])
        interactions = db.get_interactions(c["id"])
        data.append({"contact": c, "formdh": profile, "interactions": interactions})

    response = jsonify(data)
    response.headers['Content-Disposition'] = f'attachment; filename=awakening_backup_{today_str()}.json'
    return response

# ========== 啟動 ==========
def kill_process_on_port(port):
    import subprocess
    import time
    import os
    try:
        output = subprocess.check_output(f'netstat -ano | findstr LISTENING | findstr ":{port}"', shell=True).decode('cp950', errors='ignore')
        current_pid = os.getpid()
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                pid = int(parts[-1])
                if pid != current_pid:
                    print(f"  ⚡ 發現 Port {port} 已被 PID {pid} 佔用，正在關閉舊的執行檔...")
                    subprocess.call(f"taskkill /F /PID {pid}", shell=True)
                    time.sleep(1)
    except Exception:
        pass

def ensure_firewall_rule(port=5000):
    """確保 Windows 防火牆允許指定 port 的入站流量，若規則不存在則自動新增"""
    import subprocess
    try:
        rule_name = f"覺醒CRM Port {port}"
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name={rule_name}'],
            capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        if '找不到符合指定條件的規則' in result.stdout or result.returncode != 0:
            print(f"  🔧 防火牆規則不存在，嘗試自動新增 Port {port} 規則...")
            # 嘗試以系統管理員權限新增
            add_result = subprocess.run(
                ['powershell', '-Command',
                 f'Start-Process netsh -ArgumentList \'advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port}\' -Verb RunAs -Wait'],
                capture_output=True, text=True, timeout=30
            )
            if add_result.returncode == 0:
                print(f"  ✅ 防火牆規則已新增：允許 Port {port} 入站")
            else:
                print(f"  ⚠️  防火牆規則新增失敗（可能需要手動以管理員身份執行）")
        else:
            print(f"  ✅ 防火牆規則已存在：Port {port} 入站允許")
    except Exception as e:
        print(f"  ⚠️  防火牆檢查異常: {e}")

def test_remote_access(port=5000):
    """測試遠端連線是否可正常使用，並顯示本機 IP 清單"""
    import socket
    import subprocess
    import time

    print()
    print("  🔍 正在測試遠端連線...")

    # 取得所有本機 IP
    local_ips = []
    try:
        result = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='cp950', errors='ignore')
        for line in result.stdout.splitlines():
            line = line.strip()
            if 'IPv4' in line and ('位址' in line or 'Address' in line):
                parts = line.split(':')
                if len(parts) >= 2:
                    ip = parts[-1].strip()
                    if ip and not ip.startswith('127.'):
                        local_ips.append(ip)
    except Exception:
        pass

    # 等待 Flask 啟動再測試（在子執行緒中做）
    def _do_test():
        time.sleep(3)  # 等待 Flask 完全啟動
        print()
        print("  ========== 遠端連線測試結果 ==========")

        # 本機測試
        try:
            s = socket.socket()
            s.settimeout(3)
            result = s.connect_ex(('127.0.0.1', port))
            s.close()
            if result == 0:
                print(f"  ✅ 本機連線正常：http://127.0.0.1:{port}")
            else:
                print(f"  ❌ 本機連線失敗 (code {result})")
        except Exception as e:
            print(f"  ❌ 本機連線測試異常：{e}")

        # 區域網路 IP 測試
        if local_ips:
            for ip in local_ips:
                try:
                    s = socket.socket()
                    s.settimeout(3)
                    result = s.connect_ex((ip, port))
                    s.close()
                    if result == 0:
                        print(f"  ✅ 區域網路連線正常：http://{ip}:{port}")
                    else:
                        print(f"  ⚠️  區域網路 {ip}:{port} 無法連線 (可能是防火牆問題)")
                except Exception as e:
                    print(f"  ⚠️  {ip} 測試異常：{e}")
        else:
            print("  ⚠️  無法取得本機 IP，請手動確認")

        print("  ==========================================")
        print()

    t = threading.Thread(target=_do_test, daemon=True)
    t.start()

if __name__ == '__main__':
    ensure_firewall_rule(5000)
    kill_process_on_port(5000)
    storage = get_storage_info()
    print("=" * 50)
    print("  覺醒行動app（公開版）")
    print("=" * 50)
    print()
    if is_storage_configured():
        print(f"  📁 儲存位置：{storage['type']}")
        print(f"  💾 資料庫大小：{storage['size']}")
    else:
        print("  ⚠️  尚未設定儲存位置（第一次使用請到設定頁選擇）")
    print()
    print("  本機：http://127.0.0.1:5000")
    print("  區域網路：http://你的IP:5000")
    print()
    print("  可直接開啟使用，無需帳號密碼")
    print("  設定 → 儲存位置 → 改成 OneDrive/iCloud/Google Drive 資料夾")
    print("=" * 50)

    test_remote_access(5000)
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000')
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
