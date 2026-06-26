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
    """每次資料變動時，自動更新儲存位置的 .md 檔"""
    try:
        storage_path = get_storage_path()
        if not storage_path:
            return
        md_path = Path(storage_path) / "覺醒CRM_NotebookLM.md"
        contacts = db.get_all_contacts()
        lines = []
        lines.append(f"# 覺醒行動app - 聯絡人資料\n")
        lines.append(f"自動同步時間：{now_str()}  |  共 {len(contacts)} 位聯絡人\n---\n")

        for c in contacts:
            lines.append(f"## {c['name']}")
            if c.get('source'): lines.append(f"- 來源：{c['source']}")
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

        md_content = '\n'.join(lines)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
    except Exception as e:
        print(f"同步 NotebookLM 失敗：{e}")

# ========== Flask ==========
app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

db = Database()

# ========== 輔助 ==========
def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

# ========== 路由 ==========

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def index():
    if not is_storage_configured():
        return redirect(url_for('settings'))
    return redirect(url_for('dashboard'))

# --- 儀表板 ---

@app.route('/dashboard')
def dashboard():
    if not is_storage_configured():
        return redirect(url_for('settings'))

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
        tags_str = request.form.get('tags', '')
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]

        from database.models import Contact
        contact = Contact(name=name, source=source, tags=tags)

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
        tags_str = request.form.get('tags', '')
        notes = request.form.get('notes', '')
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]

        db.update_contact(contact_id, name=name, source=source,
                         tags=json.dumps(tags, ensure_ascii=False), notes=notes)
        flash('✅ 已更新', 'success')
        return redirect(url_for('view_contact', contact_id=contact_id))

    tags_str = ", ".join(json.loads(contact.get("tags", "[]")))
    return render_template('edit_contact.html', contact=contact, tags_str=tags_str)

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
            if val:
                updates[field] = val

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
    plan = planner.generate_monthly_plan()
    return render_template('plan.html', plan=plan)

@app.route('/today')
def today_view():
    from modules.planner import Planner
    planner = Planner(db)
    tasks = planner.get_today_tasks()
    overdue = planner.get_overdue_contacts()
    return render_template('today.html', tasks=tasks, overdue=overdue)

@app.route('/plan/auto_schedule')
def auto_schedule():
    from modules.planner import Planner
    planner = Planner(db)
    count = planner.auto_schedule_interactions()
    flash(f'✅ 已自動建立 {count} 個關心事件', 'success')
    return redirect(url_for('plan_view'))

# --- 行事曆 ---

@app.route('/calendar')
def calendar_view():
    events = db.get_calendar_events()
    from collections import defaultdict
    months = defaultdict(list)
    for e in events:
        month_key = e["event_date"][:7]
        contact = db.get_contact(e["contact_id"])
        e["contact_name"] = contact["name"] if contact else "未知"
        months[month_key].append(e)

    return render_template('calendar.html', months=dict(months))

@app.route('/calendar/complete/<event_id>')
def complete_event(event_id):
    db.update_calendar_event(event_id, status="completed")
    flash('✅ 已標記為完成', 'success')
    return redirect(url_for('calendar_view'))

@app.route('/calendar/cancel/<event_id>')
def cancel_event(event_id):
    db.update_calendar_event(event_id, status="cancelled")
    flash('🗑️ 已取消', 'success')
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
    return render_template('settings.html', storage=storage, storage_configured=storage_configured)

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
if __name__ == '__main__':
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

    import webbrowser
    webbrowser.open('http://127.0.0.1:5000')
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
