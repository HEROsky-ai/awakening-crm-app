# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

"""
覺醒行動app - 主程式入口
用法：
    python main.py add "姓名" --source IG
    python main.py list
    python main.py profile <id>
    python main.py interact <id> --type chat --content "聊了什麼"
    python main.py plan
    python main.py today
"""

import sys
import argparse
from datetime import datetime, timedelta

import config
from database import Database, Contact, FormDHProfile, Interaction, CalendarEvent
from modules.contacts import ContactManager
from modules.formdh import FormDHManager
from modules.planner import Planner
from modules.calendar import CalendarManager


def print_header():
    print("=" * 50)
    print("       覺醒行動app - CRM管理系統")
    print("=" * 50)
    print()


def cmd_add(db, args):
    """新增聯絡人"""
    contact = Contact(name=args.name, source=args.source or "")
    if args.tag:
        contact.tags = args.tag if isinstance(args.tag, list) else [args.tag]
    
    if db.add_contact(contact):
        print(f"✅ 已新增聯絡人：{contact.name} (ID: {contact.id})")
        if args.interactive:
            cmd_profile(db, args.parse_args(["profile", contact.id]))
    else:
        print("❌ 新增失敗")


def cmd_list(db, args):
    """列出聯絡人"""
    if args.keyword:
        contacts = db.search_contacts(args.keyword)
        print(f"🔍 搜尋「{args.keyword}」結果：")
    elif args.tag:
        all_contacts = db.get_all_contacts()
        import json
        contacts = [c for c in all_contacts if args.tag[0] in json.loads(c.get("tags", "[]"))]
        print(f"🏷️  標籤「{args.tag[0]}」篩選：")
    else:
        contacts = db.get_all_contacts()
        print("📋 所有聯絡人：")
    
    if not contacts:
        print("   （尚無聯絡人）")
        return
    
    print()
    print(f"  {'ID':<10} {'姓名':<15} {'來源':<10} {'標籤':<15} {'未互動天數':<10} {'互動次數':<8}")
    print("  " + "-" * 70)
    
    for c in contacts:
        import json
        tags = json.loads(c.get("tags", "[]"))
        tags_str = ",".join(tags[:2]) if tags else "-"
        last_int = c.get("last_interaction") or "從未"
        days_ago = "從未" if last_int == "從未" else f"{(datetime.now() - datetime.strptime(last_int, '%Y-%m-%d')).days}天"
        print(f"  {c['id']:<10} {c['name']:<15} {c.get('source', '-'):<10} {tags_str:<15} {days_ago:<10} {c.get('interaction_count', 0):<8}")
    print()
    print(f"  共 {len(contacts)} 位聯絡人")


def cmd_profile(db, args):
    """查看/編輯 FORMDH 檔案"""
    contact = db.get_contact(args.contact_id)
    if not contact:
        print(f"❌ 找不到聯絡人：{args.contact_id}")
        return
    
    profile = db.get_formdh_profile(args.contact_id)
    
    print(f"\n👤 {contact['name']} - FORMDH 檔案")
    print("=" * 50)
    
    if not profile:
        print("（尚無 FORMDH 檔案）")
        return
    
    score = profile.get("completeness_score", 0)
    print(f"📊 完整度：{score}%")
    print()
    
    # F - 家庭
    print("【F - 家庭 Family】")
    print(f"  家庭狀況：{profile.get('f_family', '-')}")
    print(f"  備註：{profile.get('f_family_notes', '-')}")
    print()
    
    # O - 工作
    print("【O - 工作 Occupation】")
    print(f"  職業：{profile.get('o_occupation', '-')}")
    print(f"  工作狀況：{profile.get('o_occupation_notes', '-')}")
    print(f"  工作型態：{profile.get('o_work_style', '-')}")
    print()
    
    # R - 興趣
    print("【R - 興趣 Recreation】")
    print(f"  興趣愛好：{profile.get('r_interests', '-')}")
    print(f"  詳細描述：{profile.get('r_interests_detail', '-')}")
    print(f"  業餘活動：{profile.get('r_hobbies', '-')}")
    print()
    
    # M - 金錢觀
    print("【M - 金錢觀 Money】")
    print(f"  金錢觀：{profile.get('m_money_values', '-')}")
    print(f"  收入區間：{profile.get('m_income_range', '-')}")
    print(f"  投資態度：{profile.get('m_investment', '-')}")
    print(f"  財務目標：{profile.get('m_financial_goals', '-')}")
    print()
    
    # D - 夢想
    print("【D - 夢想 Dreams】")
    print(f"  夢想目標：{profile.get('d_dreams', '-')}")
    print(f"  短期夢想：{profile.get('d_short_term', '-')}")
    print(f"  長期夢想：{profile.get('d_long_term', '-')}")
    print(f"  動機渴望：{profile.get('d_motivations', '-')}")
    print()
    
    # H - 健康
    print("【H - 健康 Health】")
    print(f"  健康狀況：{profile.get('h_health', '-')}")
    print(f"  運動習慣：{profile.get('h_fitness', '-')}")
    print(f"  飲食習慣：{profile.get('h_diet', '-')}")
    print(f"  壓力來源：{profile.get('h_stress', '-')}")
    print(f"  健康目標：{profile.get('h_goals', '-')}")
    print()
    
    # 互動記錄
    interactions = db.get_interactions(args.contact_id)
    print(f"📝 互動記錄（共 {len(interactions)} 筆）：")
    for i, intr in enumerate(interactions[:5], 1):
        print(f"  {i}. [{intr['date']}] {intr['type']} - {intr['content'][:30]}...")
    if len(interactions) > 5:
        print(f"  ...還有 {len(interactions) - 5} 筆")


def cmd_edit(db, args):
    """編輯聯絡人基本資料"""
    contact = db.get_contact(args.contact_id)
    if not contact:
        print(f"❌ 找不到聯絡人：{args.contact_id}")
        return
    
    if args.name:
        db.update_contact(args.contact_id, name=args.name)
    if args.source:
        db.update_contact(args.contact_id, source=args.source)
    if args.tag:
        import json
        db.update_contact(args.contact_id, tags=json.dumps(args.tag, ensure_ascii=False))
    if args.notes:
        db.update_contact(args.contact_id, notes=args.notes)
    
    print(f"✅ 已更新聯絡人")


def cmd_formdh_edit(db, args):
    """編輯 FORMDH 檔案"""
    contact = db.get_contact(args.contact_id)
    if not contact:
        print(f"❌ 找不到聯絡人：{args.contact_id}")
        return
    
    profile = db.get_formdh_profile(args.contact_id)
    if not profile:
        print(f"❌ 找不到 FORMDH 檔案")
        return
    
    # 更新提供的欄位
    updates = {}
    if args.f_family is not None:
        updates["f_family"] = args.f_family
    if args.f_notes is not None:
        updates["f_family_notes"] = args.f_notes
    if args.o_job is not None:
        updates["o_occupation"] = args.o_job
    if args.o_notes is not None:
        updates["o_occupation_notes"] = args.o_notes
    if args.o_style is not None:
        updates["o_work_style"] = args.o_style
    if args.r_interests is not None:
        updates["r_interests"] = args.r_interests
    if args.r_detail is not None:
        updates["r_interests_detail"] = args.r_detail
    if args.r_hobbies is not None:
        updates["r_hobbies"] = args.r_hobbies
    if args.m_values is not None:
        updates["m_money_values"] = args.m_values
    if args.m_income is not None:
        updates["m_income_range"] = args.m_income
    if args.m_invest is not None:
        updates["m_investment"] = args.m_invest
    if args.m_goals is not None:
        updates["m_financial_goals"] = args.m_goals
    if args.d_dreams is not None:
        updates["d_dreams"] = args.d_dreams
    if args.d_short is not None:
        updates["d_short_term"] = args.d_short
    if args.d_long is not None:
        updates["d_long_term"] = args.d_long
    if args.d_motive is not None:
        updates["d_motivations"] = args.d_motive
    if args.h_health is not None:
        updates["h_health"] = args.h_health
    if args.h_fitness is not None:
        updates["h_fitness"] = args.h_fitness
    if args.h_diet is not None:
        updates["h_diet"] = args.h_diet
    if args.h_stress is not None:
        updates["h_stress"] = args.h_stress
    if args.h_goals is not None:
        updates["h_goals"] = args.h_goals
    
    if updates:
        db.update_formdh_profile(args.contact_id, **updates)
        print(f"✅ 已更新 FORMDH 檔案")
    else:
        print("⚠️ 未提供任何更新欄位")


def cmd_interact(db, args):
    """記錄互動"""
    contact = db.get_contact(args.contact_id)
    if not contact:
        print(f"❌ 找不到聯絡人：{args.contact_id}")
        return
    
    interaction = Interaction(
        contact_id=args.contact_id,
        type=args.type,
        date=args.date or datetime.now().strftime("%Y-%m-%d"),
        content=args.content or "",
        notes=args.notes or "",
        channel=args.channel or ""
    )
    
    if db.add_interaction(interaction):
        print(f"✅ 已記錄互動：{contact['name']} - [{interaction.type}] {interaction.content[:30]}")
    else:
        print("❌ 記錄失敗")


def cmd_plan(db, args):
    """產生互動規劃"""
    planner = Planner(db)
    plan = planner.generate_monthly_plan()
    
    print("\n📅 本月互動規劃")
    print("=" * 50)
    
    if not plan:
        print("（無需規劃）")
        return
    
    print(f"\n🎯 優先聯繫名單（需在月底前完成）：\n")
    print(f"  {'優先級':<8} {'姓名':<15} {'未互動':<10} {'上次互動':<12} {'原因'}")
    print("  " + "-" * 65)
    
    for item in plan:
        contact = item["contact"]
        priority = item["priority"]
        reason = item["reason"]
        days = item["days_since"]
        last = contact.get("last_interaction", "從未")
        
        priority_icon = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
        print(f"  {priority_icon}{priority:<6} {contact['name']:<15} {days:<10} {last:<12} {reason}")
    
    print(f"\n  共 {len(plan)} 人需要關注")


def cmd_today(db, args):
    """今日待辦"""
    planner = Planner(db)
    today_tasks = planner.get_today_tasks()
    
    print("\n📋 今日待辦")
    print("=" * 50)
    
    if not today_tasks:
        print("（今日無待辦）✅")
        return
    
    print(f"\n🔔 今日應關心：\n")
    for i, task in enumerate(today_tasks, 1):
        print(f"  {i}. {task['name']}")
        print(f"     原因：{task['reason']}")
        print(f"     建議：{task['suggestion']}")
        print()


def cmd_overdue(db, args):
    """逾期未聯繫名單"""
    planner = Planner(db)
    overdue = planner.get_overdue_contacts()
    
    print("\n⚠️ 逾期未聯繫名單（超過25天）")
    print("=" * 50)
    
    if not overdue:
        print("（無逾期）✅")
        return
    
    print(f"\n共 {len(overdue)} 人：\n")
    for c in overdue:
        days = (datetime.now() - datetime.strptime(c["last_interaction"], "%Y-%m-%d")).days
        print(f"  🔴 {c['name']} - 已 {days} 天未聯繫")


def cmd_stats(db, args):
    """統計資料"""
    stats = db.get_stats()
    
    print("\n📊 統計資料")
    print("=" * 50)
    print(f"\n  👥 總聯絡人：{stats['total_contacts']} 人")
    print(f"  🆕 本月新人：{stats['new_this_month']} 人")
    print(f"  💬 本月互動：{stats['interactions_this_month']} 次")
    print(f"  ⚠️  逾期未聯繫：{stats['overdue_count']} 人")
    print()


def cmd_calendar(db, args):
    """行事曆操作"""
    cal_mgr = CalendarManager(db)
    
    if args.calendar_action == "list":
        events = db.get_calendar_events(
            start_date=args.start,
            end_date=args.end
        )
        
        print("\n📅 行事曆事件")
        print("=" * 50)
        
        if not events:
            print("（無事件）")
            return
        
        for e in events:
            status_icon = "✅" if e["status"] == "completed" else "❌" if e["status"] == "cancelled" else "⏳"
            contact = db.get_contact(e["contact_id"])
            name = contact["name"] if contact else "未知"
            print(f"\n  {status_icon} {e['event_date']} {e['event_time']}")
            print(f"     {e['title']} - {name}")
            print(f"     類型：{e['event_type']}")
        
        print(f"\n  共 {len(events)} 個事件")
    
    elif args.calendar_action == "sync":
        print("📱 同步 Google Calendar...")
        result = cal_mgr.sync_to_google()
        if result:
            print("✅ 同步成功")
        else:
            print("❌ 同步失敗（請先設定 Google API 憑證）")
    
    elif args.calendar_action == "export":
        filepath = cal_mgr.export_to_csv(args.export_path)
        print(f"✅ 已匯出至：{filepath}")


def cmd_notify(db, args):
    """通知測試"""
    from modules.notifications import NotificationManager
    
    notif_mgr = NotificationManager(db)
    
    if args.notify_action == "test":
        result = notif_mgr.send_test()
        if result:
            print("✅ 測試通知已發送")
        else:
            print("❌ 通知發送失敗")
    
    elif args.notify_action == "daily":
        notif_mgr.send_daily_reminder()


def main():
    parser = argparse.ArgumentParser(
        description="覺醒行動app - CRM管理系統",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="可用指令")
    
    # add - 新增聯絡人
    add_parser = subparsers.add_parser("add", help="新增聯絡人")
    add_parser.add_argument("name", help="聯絡人姓名")
    add_parser.add_argument("--source", "-s", help="來源（IG/LINE/活動/轉介紹）")
    add_parser.add_argument("--tag", "-t", nargs="+", help="標籤")
    add_parser.add_argument("--interactive", "-i", action="store_true", help="互動式填寫 FORMDH")
    
    # list - 列出聯絡人
    list_parser = subparsers.add_parser("list", help="列出聯絡人")
    list_parser.add_argument("--keyword", "-k", help="關鍵字搜尋")
    list_parser.add_argument("--tag", "-t", help="按標籤篩選")
    
    # profile - 查看 FORMDH 檔案
    profile_parser = subparsers.add_parser("profile", help="查看 FORMDH 檔案")
    profile_parser.add_argument("contact_id", help="聯絡人 ID")
    
    # edit - 編輯聯絡人
    edit_parser = subparsers.add_parser("edit", help="編輯聯絡人")
    edit_parser.add_argument("contact_id", help="聯絡人 ID")
    edit_parser.add_argument("--name", "-n", help="姓名")
    edit_parser.add_argument("--source", "-s", help="來源")
    edit_parser.add_argument("--tag", "-t", nargs="+", help="標籤")
    edit_parser.add_argument("--notes", help="備註")
    
    # formdh - 編輯 FORMDH 檔案
    formdh_parser = subparsers.add_parser("formdh", help="編輯 FORMDH 檔案")
    formdh_parser.add_argument("contact_id", help="聯絡人 ID")
    # F
    formdh_parser.add_argument("--f-family", help="家庭狀況")
    formdh_parser.add_argument("--f-notes", help="家庭備註")
    # O
    formdh_parser.add_argument("--o-job", help="職業")
    formdh_parser.add_argument("--o-notes", help="工作狀況")
    formdh_parser.add_argument("--o-style", help="工作型態")
    # R
    formdh_parser.add_argument("--r-interests", help="興趣愛好")
    formdh_parser.add_argument("--r-detail", help="興趣詳細")
    formdh_parser.add_argument("--r-hobbies", help="業餘活動")
    # M
    formdh_parser.add_argument("--m-values", help="金錢觀")
    formdh_parser.add_argument("--m-income", help="收入區間")
    formdh_parser.add_argument("--m-invest", help="投資態度")
    formdh_parser.add_argument("--m-goals", help="財務目標")
    # D
    formdh_parser.add_argument("--d-dreams", help="夢想目標")
    formdh_parser.add_argument("--d-short", help="短期夢想")
    formdh_parser.add_argument("--d-long", help="長期夢想")
    formdh_parser.add_argument("--d-motive", help="動機渴望")
    # H
    formdh_parser.add_argument("--h-health", help="健康狀況")
    formdh_parser.add_argument("--h-fitness", help="運動習慣")
    formdh_parser.add_argument("--h-diet", help="飲食習慣")
    formdh_parser.add_argument("--h-stress", help="壓力來源")
    formdh_parser.add_argument("--h-goals", help="健康目標")
    
    # interact - 記錄互動
    interact_parser = subparsers.add_parser("interact", help="記錄互動")
    interact_parser.add_argument("contact_id", help="聯絡人 ID")
    interact_parser.add_argument("--type", "-t", required=True, 
                               choices=["chat", "care", "share", "invite", "followup"],
                               help="互動類型")
    interact_parser.add_argument("--content", "-c", help="互動內容")
    interact_parser.add_argument("--notes", "-n", help="備註")
    interact_parser.add_argument("--channel", help="管道（IG/LINE/電話/見面）")
    interact_parser.add_argument("--date", "-d", help="日期（YYYY-MM-DD）")
    
    # plan - 互動規劃
    subparsers.add_parser("plan", help="產生本月互動規劃")
    
    # today - 今日待辦
    subparsers.add_parser("today", help="今日待辦")
    
    # overdue - 逾期名單
    subparsers.add_parser("overdue", help="逾期未聯繫名單")
    
    # stats - 統計
    subparsers.add_parser("stats", help="統計資料")
    
    # calendar - 行事曆
    cal_parser = subparsers.add_parser("calendar", help="行事曆操作")
    cal_parser.add_argument("calendar_action", choices=["list", "sync", "export"], 
                          help="行事曆動作")
    cal_parser.add_argument("--start", help="開始日期（YYYY-MM-DD）")
    cal_parser.add_argument("--end", help="結束日期（YYYY-MM-DD）")
    cal_parser.add_argument("--export-path", default=None, help="匯出路徑")
    
    # notify - 通知
    notif_parser = subparsers.add_parser("notify", help="通知操作")
    notif_parser.add_argument("notify_action", choices=["test", "daily"], 
                             help="通知動作")
    
    # delete - 刪除
    del_parser = subparsers.add_parser("delete", help="刪除聯絡人")
    del_parser.add_argument("contact_id", help="聯絡人 ID")
    
    args = parser.parse_args()
    
    if not args.command:
        print_header()
        print("使用說明：")
        print("  python main.py add \"姓名\" --source IG          # 新增聯絡人")
        print("  python main.py list                            # 列出所有")
        print("  python main.py profile <id>                   # 查看檔案")
        print("  python main.py edit <id> --name 新名字         # 編輯")
        print("  python main.py formdh <id> --f-family \"已婚\"   # 編輯 FORMDH")
        print("  python main.py interact <id> --type chat -c \"內容\"  # 記錄互動")
        print("  python main.py plan                            # 互動規劃")
        print("  python main.py today                          # 今日待辦")
        print("  python main.py overdue                        # 逾期名單")
        print("  python main.py stats                          # 統計資料")
        print("  python main.py calendar list                   # 行事曆")
        print()
        print("  python main.py delete <id>                    # 刪除")
        print()
        return
    
    # 初始化資料庫
    db = Database()
    
    # 執行指令
    if args.command == "add":
        cmd_add(db, args)
    elif args.command == "list":
        cmd_list(db, args)
    elif args.command == "profile":
        cmd_profile(db, args)
    elif args.command == "edit":
        cmd_edit(db, args)
    elif args.command == "formdh":
        cmd_formdh_edit(db, args)
    elif args.command == "interact":
        cmd_interact(db, args)
    elif args.command == "plan":
        cmd_plan(db, args)
    elif args.command == "today":
        cmd_today(db, args)
    elif args.command == "overdue":
        cmd_overdue(db, args)
    elif args.command == "stats":
        cmd_stats(db, args)
    elif args.command == "calendar":
        cmd_calendar(db, args)
    elif args.command == "notify":
        cmd_notify(db, args)
    elif args.command == "delete":
        if db.delete_contact(args.contact_id):
            print(f"✅ 已刪除聯絡人")
        else:
            print("❌ 刪除失敗")


if __name__ == "__main__":
    main()
