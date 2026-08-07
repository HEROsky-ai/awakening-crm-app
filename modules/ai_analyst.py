# -*- coding: utf-8 -*-
"""
modules/ai_analyst.py - AI 智慧分析與建檔模組 (支援 OpenRouter 備用通道)
"""

import json
import base64
import requests
from typing import Optional, Dict
from pathlib import Path

def load_keys_from_config():
    """從 storage_config.json 讀取所有 API Keys"""
    # 專案根目錄
    base_dir = Path(__file__).parent.parent.absolute()
    config_file = base_dir / "storage_config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return (
                    cfg.get("gemini_api_key"),
                    cfg.get("openrouter_api_key"),
                    cfg.get("zai_api_key")
                )
        except:
            pass
    return None, None, None

def compress_image_bytes(image_bytes: bytes, max_size: int = 1200, quality: int = 75) -> list:
    """
    將上傳的圖片進行尺寸調整與壓縮，顯著減少上傳時間、API 負載與 Token 消耗。
    針對高寬比大於 2.2 的超長截圖，自動進行垂直切片（Overlap 150px）以確保字體清晰度，杜絕 OCR 模糊。
    回傳 [(compressed_bytes, mime_type), ...] 元組清單。
    """
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        
        # 處理 RGBA 轉換為 RGB 以利輸出 JPEG
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGB')
            
        width, height = img.size
        
        # 判斷是否為超長截圖
        if height > width * 2.2:
            print(f"【超長截圖偵測】尺寸 {width}x{height}，長寬比為 {height/width:.2f}。啟動垂直切片以確保 OCR 精度...")
            slices = []
            slice_height = int(width * 1.5)
            overlap = 150
            
            start_y = 0
            while start_y < height:
                end_y = start_y + slice_height
                if end_y > height:
                    end_y = height
                    # 避免切出非常窄的邊角料
                    if end_y - start_y < 200 and len(slices) > 0:
                        break
                        
                box = (0, start_y, width, end_y)
                slice_img = img.crop(box)
                
                # 調整寬度為最大 1000px，高度隨之等比縮小，確保字跡大且好認
                target_w = 1000
                if width > target_w:
                    target_h = int(slice_img.height * target_w / slice_img.width)
                    slice_img = slice_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                    
                out_io = io.BytesIO()
                slice_img.save(out_io, format="JPEG", quality=quality)
                slices.append((out_io.getvalue(), "image/jpeg"))
                
                print(f"  - 產生切片區間: Y={start_y} 到 Y={end_y}，儲存大小 {len(out_io.getvalue())} bytes")
                if end_y >= height:
                    break
                start_y = end_y - overlap
            return slices
        else:
            # 普通圖片的壓縮邏輯
            if max(width, height) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
            out_io = io.BytesIO()
            img.save(out_io, format="JPEG", quality=quality)
            compressed = out_io.getvalue()
            print(f"【AI 分析預處理】普通圖片壓縮成功：尺寸 {width}x{height} -> 縮小尺寸為 {img.width}x{img.height} ({len(compressed)} bytes)")
            return [(compressed, "image/jpeg")]
    except Exception as e:
        print(f"【AI 分析預處理】圖片壓縮與切片異常 (將使用原圖)：{e}")
        return [(image_bytes, "image/jpeg")]

def analyze_contact_info(
    text: Optional[str] = None, 
    image_bytes: Optional[bytes] = None, 
    mime_type: Optional[str] = None, 
    images: Optional[list] = None,
    api_key: Optional[str] = None
) -> Dict:
    """
    分析輸入內容並提取聯絡人與 FORMDH 資訊，生成聊天與時事建議。
    優先使用 native Gemini API；若失敗或無金鑰，自動切換至 OpenRouter API 作為備用通道。
    """
    # 載入所有金鑰
    config_gemini, config_openrouter, config_zai = load_keys_from_config()
    
    # 確定使用的 Gemini 金鑰
    gemini_key = api_key or config_gemini

    # 組合所有輸入圖片
    input_images = []
    if images:
        input_images.extend(images)
    elif image_bytes and mime_type:
        input_images.append((image_bytes, mime_type))

    # 進行圖片預處理（壓縮與超長截圖切片）
    processed_images = []
    for img_bytes, m_type in input_images:
        slices = compress_image_bytes(img_bytes)
        processed_images.extend(slices)

    # 限制圖片/切片總數最多 30 張，防超時與 payload 太大
    processed_images = processed_images[:30]

    # 建立 Prompt
    prompt = """
您是一位專為覺醒直銷商設計的 CRM 智慧助理。
請仔細分析所提供的內容（可能是名片、多張對話截圖/切片、新人自介或一段關於新人的筆記），並以繁體中文完成以下任務：

1. 提取或推測新人的基本資訊（姓名、來源、建議標籤）。如果無法在內容中找到姓名，請用一個形容詞加新朋友命名（如「健身新朋友」、「讀書會女生」或直接「新朋友」）。
2. 將提取的個人背景分類整理到 FORMDH 架構中。如果某些欄位在內容中未提及，請保留空字串 ""：
   - F_family（家庭狀況，如配偶、小孩、家庭成員等）
   - F_family_notes（家庭狀況備註：【重要】若有提及「居住地/住在哪裡」、「星座」或「生日/出生日期」等個人資訊，請務必整合至此欄，格式如：「住：台北大安區｜星座：天秤座｜生日：10/15」。若多個項目都有提及則全部列入，若都沒提及則留空）
   - O_occupation（職業、職稱、工作狀況與工作型態）
   - R_interests（興趣愛好，多個請用逗號或頓號分隔，且可以寫詳細的描述）
   - M_money_values（金錢觀，如消費習慣、理財目標、投資態度）
   - D_dreams（夢想目標，如人生願景、短期/長期夢想、動力來源）
   - H_health（健康狀況，如運動習慣、飲食習慣、睡眠與壓力狀況、健康目標）
3. 生成針對此新人的 AI 聊天與關心建議（全部用繁體中文書寫）：

   【ai_chat_suggestions】
   請根據已知資訊，提供 3 個具體、有溫度的聊天切入點，每個切入點要包含：
   - 先用已知的生活/興趣話題輕鬆開場
   - 再自然地帶入一個可以深化了解對方的問題
   例如：「他喜歡爬山，可以先說『最近天氣涼了，你還有在爬山嗎？』，然後順帶問『你們都幾個人一起去？家人也會一起嗎？』來了解他的家庭互動。」
   請列出 3 個這樣的「開場話題→延伸問題」組合，親切自然、不要像推銷。

   【ai_current_affairs】
   根據對方的興趣、職業或生活背景，推薦 2-3 個最近可以主動傳給對方的時事話題或生活資訊，說明「為何對他有用」以及「怎麼帶入的一句話」，例如：「他喜歡跑步，最近有篇報導說清晨跑步對心肺很好，可以傳給他並說：『看到這篇想到你，不知道你都幾點去跑？』讓對話自然延續。」

   【ai_missing_info_suggestions】
   根據 FORMDH 六個維度（家庭/職業/興趣/金錢觀/夢想/健康），找出目前資料最缺乏的 2-3 個方向，並為每個缺少的維度設計「迂迴引導策略」：
   - 步驟一：先聊一個和該維度相關的輕鬆話題（不要直接問）
   - 步驟二：對方回應後，自然帶出能了解該維度的問題
   例如：「目前缺少他的金錢觀資訊，可以先聊：『最近物價好像都漲了，你有感嗎？』，他回應後再說：『對，我最近也在研究怎麼存錢，你平常有在理財嗎？』這樣就能自然挖掘他的金錢觀，而不是直接問。」
   請針對 2-3 個缺少的維度各設計一套「兩步引導話術」。

請嚴格遵循以下 JSON 格式輸出，不要包含額外的說明，也不要用 ```json ... ``` 標記包裹，直接回傳純 JSON 字串：
{
  "name": "提取的姓名",
  "source": "提取或建議的來源（例如：名片、IG、LINE、轉介紹、讀書會等）",
  "tags": ["建議的標籤1", "建議的標籤2"],
  "f_family": "家庭狀況",
  "f_family_notes": "家庭備註（含住所、星座、生日等個人資訊，格式如：住：台北大安區｜星座：天秤座｜生日：10/15）",
  "o_occupation": "職業",
  "o_occupation_notes": "工作狀況備註",
  "o_work_style": "工作型態",
  "r_interests": "興趣愛好",
  "r_interests_detail": "興趣詳細描述",
  "r_hobbies": "業餘活動與嗜好",
  "m_money_values": "金錢觀",
  "m_income_range": "收入區間",
  "m_investment": "投資理財態度",
  "m_financial_goals": "財務目標",
  "d_dreams": "夢想目標",
  "d_short_term": "短期夢想",
  "d_long_term": "長期夢想",
  "d_motivations": "動機與渴望",
  "h_health": "健康狀況",
  "h_fitness": "健身與運動習慣",
  "h_diet": "飲食與作息",
  "h_stress": "壓力來源",
  "h_goals": "健康目標",
  "ai_chat_suggestions": "3個具體聊天切入點（開場話題→延伸問題的組合）",
  "ai_current_affairs": "2-3個時事或資訊推薦（含如何帶入的一句話）",
  "ai_missing_info_suggestions": "針對缺少維度的兩步迂迴引導話術（每個維度含步驟一與步驟二）"
}
"""

    text_content = f"{prompt}\n\n【分析內容】:\n"
    if text:
        text_content += f"{text}\n"
    if processed_images:
        text_content += f"（請一併對上傳的 {len(processed_images)} 張圖片進行 OCR 辨識與內容提取分析，若為長圖切片請合併上下文解讀）\n"

    # ==========================================
    # 通道 1: 嘗試原生的 Google Gemini API
    # ==========================================
    gemini_err = None
    openrouter_err = None

    if gemini_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        headers = {"Content-Type": "application/json"}
        
        parts = []
        for img_bytes, m_type in processed_images:
            try:
                base64_data = base64.b64encode(img_bytes).decode("utf-8")
                parts.append({
                    "inlineData": {
                        "mimeType": m_type,
                        "data": base64_data
                    }
                })
            except Exception as e:
                print(f"原生 Gemini 圖片編碼失敗: {e}")
                
        parts.append({"text": text_content})
        
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        
        import time
        max_retries = 2
        for attempt in range(max_retries):
            try:
                print(f"嘗試呼叫原生 Google Gemini API (gemini-2.5-flash，第 {attempt + 1} 次)...")
                response = requests.post(url, headers=headers, json=payload, timeout=40)
                if response.status_code == 200:
                    result_json = response.json()
                    text_response = None
                    try:
                        if "candidates" in result_json:
                            text_response = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                        elif "contents" in result_json:
                            text_response = result_json["contents"][0]["parts"][0]["text"].strip()
                        else:
                            gemini_err = f"原生 Gemini 回傳格式中找不到 candidates 或 contents: {json.dumps(result_json)}"
                            print(gemini_err)
                    except Exception as ex:
                        gemini_err = f"解析原生 Gemini 回傳欄位出錯: {str(ex)}，回傳內容: {json.dumps(result_json)}"
                        print(gemini_err)

                    if text_response:
                        parsed = clean_and_parse_json(text_response)
                        if parsed:
                            parsed["status"] = "ok"
                            parsed["ai_provider"] = "Google Gemini (Native)"
                            return parsed
                        else:
                            gemini_err = "原生 Gemini 回傳內容非有效 JSON 格式"
                else:
                    gemini_err = f"原生 Gemini HTTP {response.status_code}: {response.text[:100]}"
                    print(f"原生 Gemini API 請求失敗: {gemini_err}")
            except Exception as e:
                gemini_err = f"原生 Gemini 異常: {str(e)}"
                print(f"呼叫原生 Gemini 異常: {gemini_err}")
                
            if attempt < max_retries - 1:
                if 'response' in locals() and response.status_code in [400, 401, 403, 404]:
                    break
                print("原生 Gemini 請求失敗，將於 2 秒後自動重試...")
                time.sleep(2)

    # ==========================================
    # 通道 2: 備用通道 - OpenRouter API (Gemini 2.5 Flash)
    # ==========================================
    if config_openrouter:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config_openrouter}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "Awakening CRM App"
        }
        
        # 組合 OpenAI/OpenRouter 相容的 multimodal 訊息格式
        content_parts = [{"type": "text", "text": text_content}]
        
        for img_bytes, m_type in processed_images:
            try:
                base64_data = base64.b64encode(img_bytes).decode("utf-8")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{m_type};base64,{base64_data}"
                    }
                })
            except Exception as e:
                print(f"OpenRouter 圖片編碼失敗: {e}")
                
        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [
                {
                    "role": "user",
                    "content": content_parts
                }
            ],
            "max_tokens": 1800,
            "response_format": {"type": "json_object"}
        }
        
        import time
        max_retries = 2
        for attempt in range(max_retries):
            try:
                print(f"原生 Gemini 失敗或金鑰缺失，嘗試呼叫 OpenRouter API (google/gemini-2.5-flash，第 {attempt + 1} 次)...")
                response = requests.post(url, headers=headers, json=payload, timeout=50)
                if response.status_code == 200:
                    result_json = response.json()
                    text_response = result_json["choices"][0]["message"]["content"].strip()
                    parsed = clean_and_parse_json(text_response)
                    if parsed:
                        parsed["status"] = "ok"
                        parsed["ai_provider"] = "Google Gemini (via OpenRouter)"
                        return parsed
                    else:
                        openrouter_err = "OpenRouter 回傳內容非有效 JSON 格式"
                else:
                    openrouter_err = f"OpenRouter HTTP {response.status_code}: {response.text[:100]}"
                    print(f"OpenRouter API 請求失敗: {openrouter_err}")
            except Exception as e:
                openrouter_err = f"呼叫 OpenRouter 異常: {str(e)}"
                print(openrouter_err)
                
            if attempt < max_retries - 1:
                if 'response' in locals() and response.status_code in [400, 401, 403, 404]:
                    break
                print("OpenRouter 請求失敗，將於 2 秒後自動重試...")
                time.sleep(2)

    # ==========================================
    # 金鑰缺失或全部失敗的錯誤處理
    # ==========================================
    if not gemini_key and not config_openrouter:
        return {
            "status": "error", 
            "msg": "未設定 Gemini 或 OpenRouter API Key。請前往『設定』頁面設定。"
        }
        
    err_details = []
    if gemini_err:
        err_details.append(gemini_err)
    if openrouter_err:
        err_details.append(openrouter_err)
        
    error_msg = "AI 分析服務目前無法連線，請檢查 API Key 或網路狀況。"
    if err_details:
        error_msg += " 詳細錯誤：" + "；".join(err_details)
        
    return {
        "status": "error", 
        "msg": error_msg
    }

def clean_and_parse_json(text: str) -> Optional[Dict]:
    """清洗並解析 API 回傳的 JSON 字串"""
    try:
        text_clean = text.strip()
        if text_clean.startswith("```json"):
            text_clean = text_clean[7:]
        if text_clean.endswith("```"):
            text_clean = text_clean[:-3]
        text_clean = text_clean.strip()
        return json.loads(text_clean)
    except Exception as e:
        print(f"JSON 清洗與解析失敗: {e}. 原始內容: {text}")
        return None
