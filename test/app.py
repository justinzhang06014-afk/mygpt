import os
import time
import requests

print("⏳ 正在等待官方 Hermes Agent 核心安全初始化（預留 15 秒）...")
time.sleep(15)

URL = "http://hermes-core:8642/v1/chat/completions"
headers = {
    "Authorization": "Bearer my-local-test-token",
    "Content-Type": "application/json"
}
payload = {
    "model": "hermes-agent",
    "messages": [{"role": "user", "content": "你好，請用繁體中文回答：獨立環境 8642 對齊通電成功了嗎？"}]
}

for i in range(5):
    try:
        print(f"📡 正在發送測試請求給官方 Hermes 核心 (第 {i+1}/5 次，允許思考 60 秒)...")
        response = requests.post(URL, json=payload, headers=headers, timeout=60)
        
        print(f"📡 網路狀態碼: {response.status_code}")
        result = response.json()
        
        if response.status_code == 200 and 'choices' in result:
            print("\n🎨 【您的自製 UI 成功拿到回覆】:")
            # 🔥 關鍵修正點：加上 [0] 取出 choices 的第一筆資料
            print(result['choices'][0]['message']['content'])
            print("\n✅ 獨立測試終極大圓滿成功！")
            break
        else:
            print(f"❌ 核心回應異常，內容: {result}")
    except Exception as e:
        print(f"❌ 連線超時或拒絕（核心還在與群聯網關握手中），4 秒後重試... 錯誤原因: {e}")
    time.sleep(4)
