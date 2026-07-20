import os
import json
import requests

# 1. 讀取環境變數（若無則套用預設值）
# 提示：請確保 URL 端點與您的 main.py / AgentChatRequest 實際路由相符
HERMES_CORE_URL = os.getenv("HERMES_CORE_URL", "http://hermes-core:8642/v1/chat/completions")
API_SERVER_KEY = os.getenv("API_SERVER_KEY", "my-local-test-token")

# 2. 封裝傳遞的 Headers (加入 Bearer Token 驗證)
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_SERVER_KEY}"
}

# 3. 根據 AgentChatRequest 規格定義測試資料
payload = {
    "agent_id": "test_hermes_agent_001",
    "room_id": "room_999",
    "system_prompt": "你是一個名叫 Hermes 的進階 AI 助理，請用繁體中文回答。",
    "message": "嘿！請告訴我你的名字，並說明 1+1 等於多少？"
}

try:
    print(f"📡 正在發送測試請求給 Hermes 中控服務...")
    print(f"🔗 目標端點: {HERMES_CORE_URL}")
    
    # 發送 POST 請求
    response = requests.post(HERMES_CORE_URL, json=payload, headers=headers, timeout=30)
    
    print(f" 狀態碼: {response.status_code}")
    
    # 4. 處理回應結果
    if response.status_code == 200:
        result = response.json()
        print("\n🤖 【Hermes 實際回覆】:")
        
        # 安全地讀取回覆，避免因為欄位名稱不同（例如 reply 或 content）而拋出異常
        reply_content = result.get("reply") or result.get("content")
        
        if reply_content:
            print(reply_content)
            print("\n✅ 證明成功：API 路由正確，且已成功穿透並取得 AI 回覆！")
        else:
            print("⚠️ 警告：連線成功且狀態碼為 200，但回覆中找不到 'reply' 或 'content' 欄位。")
            print("完整的 JSON 回應結構如下：")
            print(json.dumps(result, indent=4, ensure_ascii=False))
            
    else:
        print(f"❌ 失敗：服務有反應，但格式或內部出錯。")
        print(f"📄 回應內容: {response.text}")
        
except requests.exceptions.Timeout:
    print("❌ 連線失敗：請求逾時 (Timeout)，Hermes 服務可能運算過久或卡住。")
except requests.exceptions.ConnectionError:
    print("❌ 連線完全失敗：無法建立連線。請檢查 Docker 容器是否啟動、網路是否暢通，以及埠口(Port)是否正確。")
except Exception as e:
    print(f"❌ 發生非預期的錯誤: {e}")
