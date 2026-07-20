import os
import httpx
import asyncio

# 讀取你的環境變數設定
HERMES_CORE_URL = os.getenv("HERMES_CORE_URL", "http://hermes-core:8642/v1/chat/completions")
API_SERVER_KEY = os.getenv("API_SERVER_KEY", "my-local-test-token")

headers = {
    "Authorization": f"Bearer {API_SERVER_KEY}",
    "Content-Type": "application/json"
}

async def send_to_hermes(agent_name: str, room_id: str, message: str):
    """將模擬數據發送至真實的 Hermes Core 驗證路由與記憶"""
    
    # 建立符合 Hermes 規範的 Body 與 Header
    # 透過 model 指定 Profile，透過 X-Hermes-Session-Id 指定 Room
    custom_headers = {
        **headers,
        "X-Hermes-Session-Id": room_id  # 告訴 Hermes 這是哪一個對話房
    }
    
    payload = {
        "model": agent_name,  # 'AgentA' 或 'AgentB' (必須是系統中存在的 profile)
        "messages": [
            {"role": "user", "content": message}
        ],
        "stream": False
    }

    print(f"\n🚀 [發送中] -> Agent: {agent_name} | Room: {room_id}")
    print(f"   使用者說: {message}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(HERMES_CORE_URL, json=payload, headers=custom_headers)
            
            if response.status_code != 200:
                print(f"   ❌ 發生錯誤 (HTTP {response.status_code}): {response.text}")
                return
                
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            print(f"   🤖 Hermes 回應:\n   {reply.strip()}")
            
    except httpx.RequestError as exc:
        print(f"   ❌ 連線失敗，請確保 Hermes Core 正在執行中。錯誤: {exc}")

async def main():
    print("==================================================")
    print("👉 開始依序發送模擬測試數據至真實 Hermes Core 驗證...")
    print(f"   目標網址: {HERMES_CORE_URL}")
    print("==================================================")

    # --------------------------------------------------
    # 【階段一：測試 AgentA (Jason 股票分析師) 與 Room 隔離】
    # --------------------------------------------------
    # 測試 1-1: 在 roomA 建立台積電的上下文記憶
    await send_to_hermes(
        agent_name="AgentA", 
        room_id="roomA", 
        message="嗨摟你是股票分析師Jason 請用150字說明一下2330"
    )
    await asyncio.sleep(300) # 稍作停頓，給系統處理記憶落庫

    await send_to_hermes(
        agent_name="AgentA", 
        room_id="roomA", 
        message="那你幫我分析一下財報 大概250字"
    )
    await asyncio.sleep(300)

    # 測試 1-2: 換到 roomB，測試跨 Session Recall 是否能抓到 roomA 關於台積電的記憶
    await send_to_hermes(
        agent_name="AgentA", 
        room_id="roomB", 
        message="嗨 你知道我最近關注了甚麼嗎"
    )
    await asyncio.sleep(300)

    # 測試 1-3: 在 roomC 詢問寵物，因為 AgentA 沒有寵物相關記憶，預期回答不知道
    await send_to_hermes(
        agent_name="AgentA", 
        room_id="roomC", 
        message="嗨 你知道我最近關注了甚麼寵物嗎"
    )
    await asyncio.sleep(300)


    # --------------------------------------------------
    # 【階段二：測試 AgentB (小美 寵物溝通師) 是否完全隔絕】
    # --------------------------------------------------
    # 測試 2-1: 在 roomC 初始化 AgentB 的寵物知識
    await send_to_hermes(
        agent_name="AgentB", 
        room_id="roomC", 
        message="你現在是寵物溝通師 小美 請用150字介紹一下博美"
    )
    await asyncio.sleep(300)

    # 測試 2-2: 在 roomD 測試 AgentB 的跨 Session 記憶（能抓到博美，但絕對不能抓到 AgentA 的台積電）
    await send_to_hermes(
        agent_name="AgentB", 
        room_id="roomD", 
        message="嗨瞜 你說說我最近關注了甚麼"
    )
    await asyncio.sleep(300)

    # 測試 2-3: 在 roomD 問股票，驗證 AgentB 視角內完全沒有 AgentA 的股票資訊
    await send_to_hermes(
        agent_name="AgentB", 
        room_id="roomD", 
        message="嗨瞜 你知道我買哪支股票嗎"
    )

    print("\n==================================================")
    print("🎉 測試數據發送完畢！請檢查上方終端機中真實的 Hermes 回應是否符合隔離預期。")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
