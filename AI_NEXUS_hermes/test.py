"""
AI_NEXUS Hermes 測試客戶端 —— 模擬「別人的前端/後端」怎麼呼叫這個服務。

流程完全對應正式架構的兩段式呼叫：
  1. 一開始呼叫一次 /api/session/ensure（入口），拿到這個使用者專屬的 chat_endpoint。
  2. 之後每一輪對話都直接打那個 chat_endpoint，不再呼叫 ensure。

執行方式：
    python test.py
"""
import json
import re
import requests

ENTRY_URL = "http://localhost:8643"       # 入口服務（跑 docker compose 那個）
USER_ID = "demo001"                       # 模擬登入拿到的使用者 ID
ROOM_ID = "room_default"

# 純顯示用，把串流裡的內部標記轉成人看得懂的一行摘要，不影響正文輸出
_MARKER_PATTERN = re.compile(r"__(ACP_THOUGHT|ACP_TOOL|ACP_PLAN|ACP_USAGE|APPROVAL_REQUIRED)__:(\{.*?\})\n?", re.DOTALL)


def ensure_session() -> dict:
    print(f"[1/2] 呼叫 {ENTRY_URL}/api/session/ensure ...")
    resp = requests.post(
        f"{ENTRY_URL}/api/session/ensure",
        json={"user_id": USER_ID},
        timeout=60,  # 第一次可能要真的建容器，給久一點
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"      status={data['status']}  agent_id={data['agent_id']}")
    print(f"      chat_endpoint (容器內部位址，只有同網路的容器連得到) = {data['chat_endpoint']}")

    # 這支腳本是從「host」執行（不是從 docker 網路裡面），連不到 chat_endpoint 那個
    # 容器內部主機名稱——所以優先用 swagger_url 換算出來的、真的對外開放的 host port。
    # 如果你的「前後端」是跑在同一個 docker network 裡（正式部署常見的做法），
    # 直接用 chat_endpoint 就好，不需要這個轉換。
    if data.get("swagger_url"):
        host_port = data["swagger_url"].rsplit(":", 1)[1].split("/")[0]
        data["_reachable_chat_endpoint"] = f"http://localhost:{host_port}/api/agent/chat/stream"
        print(f"      swagger_url   = {data['swagger_url']}  ← 也可以直接開瀏覽器測")
    else:
        data["_reachable_chat_endpoint"] = data["chat_endpoint"]
        print("      ⚠️ 沒有 swagger_url（PUBLISH_CHILD_PORTS 沒開），這支腳本要跟服務跑在同個 docker network 裡才連得到")
    return data


def send_message(chat_endpoint: str, message: str) -> None:
    # 帶 user_id（不用自己組 agent_id 字串）——服務會自動換算成跟 ensure 時
    # 一致的 f"user_{user_id}"，這就是模擬「前端只需要記住 user_id」的呼叫方式。
    resp = requests.post(
        chat_endpoint,
        json={"user_id": USER_ID, "room_id": ROOM_ID, "message": message},
        stream=True,
        timeout=300,
    )
    if resp.status_code != 200:
        print(f"❌ HTTP {resp.status_code}: {resp.text}")
        return

    buffer = ""
    for chunk in resp.iter_content(chunk_size=256, decode_unicode=True):
        if not chunk:
            continue
        buffer += chunk
        # 標記一定是完整一段才處理，避免切在標記中間
        while True:
            m = _MARKER_PATTERN.search(buffer)
            if not m:
                break
            before = buffer[: m.start()]
            if before:
                print(before, end="", flush=True)
            kind = m.group(1)
            try:
                body = json.loads(m.group(2))
            except json.JSONDecodeError:
                body = {}
            if kind == "ACP_TOOL" and body.get("title"):
                print(f"\n  🔧 [工具] {body.get('title')} ({body.get('status')})\n", flush=True)
            buffer = buffer[m.end():]
    if buffer:
        print(buffer, end="", flush=True)
    print()


def main():
    print("=" * 60)
    print("AI_NEXUS Hermes 測試客戶端")
    print("=" * 60)

    session = ensure_session()
    chat_endpoint = session["_reachable_chat_endpoint"]

    print("\n[2/2] 開始互動式聊天（輸入 exit 離開）")
    print("-" * 60)
    while True:
        try:
            message = input("你: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not message:
            continue
        if message.lower() in ("exit", "quit"):
            break
        print("Hermes: ", end="", flush=True)
        send_message(chat_endpoint, message)


if __name__ == "__main__":
    main()
