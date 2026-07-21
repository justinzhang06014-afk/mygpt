"""
AI_NEXUS Hermes Test Client

模擬使用者建立 hermes 聊天請求並接收訊息
"""
import requests
import json
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# =============================================
# 設定
# =============================================

# 目前本地端測試（取消註解使用本地端）
BASE_URL = "http://localhost:8643"

# 未來部署的主機（取消註解使用部署環境）
# BASE_URL = "http://192.168.41.173:5080"

# API 端點
CHAT_ENDPOINT = f"{BASE_URL}/api/agent/chat/stream"

# 測試 Agent 設定
TEST_AGENT_ID = None  # 將在 main 函數中設定
TEST_ROOM_ID = None   # 將在 main 函數中設定
TEST_SYSTEM_PROMPT = "你是一位專業的 AI 助理，能夠協助使用者處理各種任務。"

# 日誌設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hermes_test_client")

# =============================================
# 聊天請求模型
# =============================================

class ChatRequest:
    def __init__(
        self,
        agent_id: str,
        room_id: str,
        system_prompt: str,
        message: str
    ):
        self.agent_id = agent_id
        self.room_id = room_id
        self.system_prompt = system_prompt
        self.message = message
    
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "room_id": self.room_id,
            "system_prompt": self.system_prompt,
            "message": self.message
        }

# =============================================
# HTTP 客戶端
# =============================================

class HermesChatClient:
    """Hermes 聊天客戶端"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.chat_endpoint = f"{base_url}/api/agent/chat/stream"
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })
    
    def send_chat_request(self, request: ChatRequest) -> int:
        """
        發送聊天請求
        
        Args:
            request: ChatRequest 物件
        
        Returns:
            HTTP 狀態碼
        """
        try:
            logger.info("\n" + "=" * 60)
            logger.info("發送聊天請求")
            logger.info("=" * 60)
            logger.info(f"Agent ID: {request.agent_id}")
            logger.info(f"Room ID: {request.room_id}")
            logger.info(f"Message: {request.message}")
            logger.info("-" * 60)
            
            response = self.session.post(
                self.chat_endpoint,
                json=request.to_dict(),
                stream=True,
                timeout=300
            )
            
            logger.info(f"HTTP 狀態碼: {response.status_code}")
            
            return response.status_code
        
        except requests.exceptions.Timeout:
            logger.error("請求超時")
            return -1
        except requests.exceptions.ConnectionError:
            logger.error("連線失敗，請確認 hermes 服務是否啟動")
            return -2
        except Exception as e:
            logger.error(f"請求失敗: {str(e)}")
            return -3
    
    def stream_response(self, request: ChatRequest):
        """
        串流接收聊天回應
        
        Args:
            request: ChatRequest 物件
        
        Yields:
            回應片段
        """
        try:
            response = self.session.post(
                self.chat_endpoint,
                json=request.to_dict(),
                stream=True,
                timeout=300
            )
            
            if response.status_code != 200:
                yield f"❌ HTTP 錯誤: {response.status_code}\n"
                yield f"錯誤訊息: {response.text}\n"
                return
            
            logger.info("開始接收串流回應...")
            logger.info("-" * 60)
            
            # 累積的回應
            full_response = ""
            thought_buffer = []
            tool_buffer = []
            skill_suggested = None
            
            for chunk in response.iter_content(chunk_size=512, decode_unicode=True):
                if not chunk:
                    continue
                
                # 輸出原始內容（除錯用）
                # logger.debug(f"原始 chunk: {repr(chunk)}")
                
                # 解析特殊標記
                if "__ACP_THOUGHT__:" in chunk:
                    parts = chunk.split("__ACP_THOUGHT__:")
                    for part in parts[1:]:
                        try:
                            thought_data = json.loads(part.strip())
                            thought_text = thought_data.get("text", "")
                            thought_buffer.append(thought_text)
                        except json.JSONDecodeError:
                            pass
                    continue
                
                if "__ACP_TOOL__:" in chunk:
                    parts = chunk.split("__ACP_TOOL__:")
                    for part in parts[1:]:
                        try:
                            tool_data = json.loads(part.strip())
                            tool_buffer.append(tool_data)
                        except json.JSONDecodeError:
                            pass
                    continue
                
                if "__SKILL_SUGGESTED__:" in chunk:
                    parts = chunk.split("__SKILL_SUGGESTED__:")
                    for part in parts[1:]:
                        try:
                            skill_suggested = json.loads(part.strip())
                        except json.JSONDecodeError:
                            pass
                    continue
                
                # 一般文字內容
                if not any(marker in chunk for marker in [
                    "__ACP_THOUGHT__:", "__ACP_TOOL__:", "__SKILL_SUGGESTED__:",
                    "__APPROVAL_REQUIRED__:"
                ]):
                    full_response += chunk
                    print(chunk, end="", flush=True)
            
            print()  # 換行
            
            # 顯示思考過程
            if thought_buffer:
                logger.info("\n🧠 思考過程:")
                for thought in thought_buffer:
                    logger.info(f"  - {thought}")
            
            # 顯示工具呼叫
            if tool_buffer:
                logger.info(f"\n🔧 工具呼叫 ({len(tool_buffer)} 次):")
                for i, tool in enumerate(tool_buffer, 1):
                    title = tool.get("title", "Unknown")
                    kind = tool.get("kind", "Unknown")
                    status = tool.get("status", "Unknown")
                    logger.info(f"  {i}. [{status}] {title} ({kind})")
            
            # 顯示技能建議
            if skill_suggested:
                logger.info(f"\n💡 技能建議:")
                logger.info(f"  名稱: {skill_suggested.get('name', 'Unknown')}")
                logger.info(f"  說明: {skill_suggested.get('description', '')}")
                logger.info(f"  識別碼: {skill_suggested.get('identifier', '')}")
            
            logger.info("-" * 60)
            logger.info("✅ 串流回應接收完成")
            
            return full_response
        
        except requests.exceptions.Timeout:
            yield "❌ 串流接收超時\n"
        except requests.exceptions.ConnectionError:
            yield "❌ 連線中斷\n"
        except Exception as e:
            logger.error(f"串流接收錯誤: {str(e)}")
            yield f"❌ 發生錯誤: {str(e)}\n"
    
    def chat(self, message: str, agent_id: str, room_id: str, system_prompt: str) -> str:
        """
        簡化的聊天介面
        
        Args:
            message: 使用者訊息
            agent_id: Agent ID
            room_id: 房間 ID
            system_prompt: 系統提示詞
        
        Returns:
            完整回應
        """
        request = ChatRequest(agent_id, room_id, system_prompt, message)
        
        try:
            full_response = ""
            for chunk in self.stream_response(request):
                if not chunk.startswith("__") and not chunk.startswith("❌"):
                    full_response += chunk
            
            return full_response
        except Exception as e:
            logger.error(f"聊天失敗: {str(e)}")
            return ""

# =============================================
# 測試案例
# =============================================

def test_basic_chat(client: HermesChatClient, agent_id: str, room_id: str, system_prompt: str):
    """測試基本對話"""
    logger.info("\n" + "=" * 60)
    logger.info("測試案例: 基本對話")
    logger.info("=" * 60)
    
    messages = [
        "你好，請自我介紹一下。",
        "請幫我用 Python 寫一個 Hello World 程式。",
        "再見！"
    ]
    
    for msg in messages:
        full_response = client.chat(
            message=msg,
            agent_id=agent_id,
            room_id=room_id,
            system_prompt=system_prompt
        )
        
        logger.info(f"\n📝 完整回應長度: {len(full_response)} 字元")
        
        # 等待一下再發送下一個訊息
        time.sleep(2)

def test_mcp_tools(client: HermesChatClient, agent_id: str, room_id: str, system_prompt: str):
    """測試 MCP 工具使用"""
    logger.info("\n" + "=" * 60)
    logger.info("測試案例: MCP 工具使用")
    logger.info("=" * 60)
    
    messages = [
        "請幫我搜尋今天的網路新聞。",
        "請幫我產生一張美麗的風景圖片。",
    ]
    
    for msg in messages:
        full_response = client.chat(
            message=msg,
            agent_id=agent_id,
            room_id=room_id,
            system_prompt=system_prompt
        )
        
        logger.info(f"\n📝 完整回應長度: {len(full_response)} 字元")
        time.sleep(3)

def test_memory_functionality(client: HermesChatClient, agent_id: str, room_id: str, system_prompt: str):
    """測試記憶功能"""
    logger.info("\n" + "=" * 60)
    logger.info("測試案例: 記憶功能")
    logger.info("=" * 60)
    
    messages = [
        "我的名字是張三，我喜歡寫程式。",
        "請問我喜歡做什麼？",
    ]
    
    for msg in messages:
        full_response = client.chat(
            message=msg,
            agent_id=agent_id,
            room_id=room_id,
            system_prompt=system_prompt
        )
        
        logger.info(f"\n📝 完整回應長度: {len(full_response)} 字元")
        time.sleep(3)

# =============================================
# 互動式聊天
# =============================================

def interactive_chat(client: HermesChatClient, agent_id: str, room_id: str, system_prompt: str):
    """互動式聊天介面"""
    logger.info("\n" + "=" * 60)
    logger.info("互動式聊天模式")
    logger.info("=" * 60)
    logger.info("輸入 'exit' 或 'quit' 離開")
    logger.info("-" * 60)
    
    while True:
        try:
            user_input = input(f"\n[C:{room_id}] > ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ('exit', 'quit'):
                logger.info("結束聊天")
                break
            
            full_response = client.chat(
                message=user_input,
                agent_id=agent_id,
                room_id=room_id,
                system_prompt=system_prompt
            )
            
            logger.info(f"回應長度: {len(full_response)} 字元")
        
        except KeyboardInterrupt:
            logger.info("\n收到中斷訊號，結束聊天")
            break
        except Exception as e:
            logger.error(f"發生錯誤: {str(e)}")

# =============================================
# 主程式
# =============================================

def main():
    """主函數"""
    logger.info("=" * 60)
    logger.info("AI_NEXUS Hermes Test Client")
    logger.info("=" * 60)
    logger.info(f"連接到: {BASE_URL}")
    logger.info(f"聊天端點: {CHAT_ENDPOINT}")
    
    # 建立客戶端
    client = HermesChatClient(BASE_URL)
    
    # 測試 Agent 設定
    agent_id = "agent_test_001"
    room_id = "room_test_001"
    system_prompt = "你是一位專業的 AI 助理，能夠協助使用者處理各種任務。"
    
    logger.info(f"\n測試 Agent ID: {agent_id}")
    logger.info(f"測試 Room ID: {room_id}")
    logger.info(f"系統提示詞: {system_prompt}")
    
    # 檢查連線
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        logger.info(f"\n✅ 連線成功: {response.status_code}")
    except Exception as e:
        logger.error(f"\n❌ 無法連接到 {BASE_URL}: {str(e)}")
        logger.error("請確認 hermes 容器是否已啟動")
        return
    
    # 選擇測試模式
    print("\n請選擇測試模式:")
    print("1. 基本對話測試")
    print("2. MCP 工具測試")
    print("3. 記憶功能測試")
    print("4. 互動式聊天")
    print("0. 退出")
    
    choice = input("\n請輸入選項 (0-4): ").strip()
    
    if choice == "1":
        test_basic_chat(client, agent_id, room_id, system_prompt)
    elif choice == "2":
        test_mcp_tools(client, agent_id, room_id, system_prompt)
    elif choice == "3":
        test_memory_functionality(client, agent_id, room_id, system_prompt)
    elif choice == "4":
        interactive_chat(client, agent_id, room_id, system_prompt)
    elif choice == "0":
        logger.info("退出程式")
        return
    else:
        logger.warning("無效選項，執行基本對話測試")
        test_basic_chat(client, agent_id, room_id, system_prompt)
    
    logger.info("\n" + "=" * 60)
    logger.info("測試完成")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()