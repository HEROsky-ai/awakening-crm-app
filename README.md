# 覺醒行動app - 使用說明

## 簡介

這是一個專為覺醒直銷商設計的 CRM 系統，幫助你系統化管理客戶關係，透過 FORMDH 框架建立深度客戶檔案，並自動規劃互動時機。

## FORMDH 是什麼？

FORMDH 是一套個人資訊分類框架：

- **F**amily（家庭）- 家庭狀況、配偶、小孩等
- **O**ccupation（工作）- 職業、工作型態、收入等
- **R**ecreation（興趣）- 愛好、活動、休閒等
- **M**oney（金錢觀）- 財務態度、投資、理財目標等
- **D**reams（夢想）- 人生目標、短期/長期夢想等
- **H**ealth（健康）- 健康狀況、運動、飲食等

## 安裝

```bash
cd "C:\Users\1120804\Desktop\覺醒行動app"
pip install -r requirements.txt
```

## 快速開始

### 1. 新增聯絡人
```bash
python main.py add "王小明" --source IG --tag 新人
```

### 2. 查看所有聯絡人
```bash
python main.py list
```

### 3. 填寫 FORMDH 檔案
```bash
# 單一欄位更新
python main.py formdh <id> --f-family "已婚，2個小孩"

# 多個欄位一次更新
python main.py formdh <id> \
  --o-job "業務經理" \
  --o-style "全職工作" \
  --r-interests "健身、閱讀、投資" \
  --d-dreams "實現財富自由"
```

### 4. 記錄互動
```bash
python main.py interact <id> --type chat --content "聊了覺醒事業機會" --channel IG
```

### 5. 產生互動規劃
```bash
python main.py plan
```

### 6. 查看今日待辦
```bash
python main.py today
```

### 7. 查看統計
```bash
python main.py stats
```

## 指令總覽

| 指令 | 說明 |
|------|------|
| `add "姓名" --source IG` | 新增聯絡人 |
| `list` | 列出所有聯絡人 |
| `list --tag 新人` | 按標籤篩選 |
| `profile <id>` | 查看 FORMDH 檔案 |
| `edit <id> --name 新名字` | 編輯基本資料 |
| `formdh <id> --f-family "..."` | 編輯 FORMDH |
| `interact <id> --type chat -c "..."` | 記錄互動 |
| `plan` | 產生本月規劃 |
| `today` | 今日待辦 |
| `overdue` | 逾期名單 |
| `stats` | 統計資料 |
| `calendar list` | 行事曆事件 |
| `calendar export` | 匯出 CSV |
| `delete <id>` | 刪除聯絡人 |

## 自動規劃邏輯

系統會根據以下因素計算優先級：

1. **未互動天數** - 越久沒聯繫優先級越高
2. **標籤** - 「高潛力」「新人」有額外加成
3. **檔案完整度** - 檔案越完整越了解客戶

當優先級達到「高」時，系統會自動在行事曆建立關心事件。

## LINE Notify 設定

1. 到 [LINE Notify](https://notify-bot.line.me/) 取得 Personal Access Token
2. 在 `config.py` 中設定 `LINE_NOTIFY_TOKEN = "你的Token"`
3. 啟用 `enable_line_notify = True`

## Google Calendar 同步

1. 在 Google Cloud Console 建立專案
2. 啟用 Google Calendar API
3. 下載 OAuth 憑證 JSON 檔案
4. 命名為 `google_credentials.json` 放在 `data/` 資料夾
5. 首次執行 `python main.py calendar sync` 會引導認證

## 資料存放

所有資料預設存在：
- 資料庫：`data/awakening.db`（SQLite）
- 匯出：`data/exports/`

## 注意事項

- 請定期備份 `data/` 資料夾
- 刪除聯絡人會連帶刪除其 FORMDH 檔案和互動記錄
- FORMDH 完整度百分比是參考值，越高代表越了解該客戶
