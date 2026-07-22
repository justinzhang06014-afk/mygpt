import os
import logging
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ai-nexus-hermes")

# 這台服務假設 /opt/data 是「其他人」的 orchestrator 掛進來的共用 volume（跟
# hermes-agent/docs/01_orchestrator_split_plan.md 的假設一致：先維持 shared volume，
# 不需要另外做 CRUD API）。這支服務只負責把正確內容寫進去，不建立/管理容器本身。
PROFILES_BASE_DIR = os.getenv("PROFILES_BASE_DIR", "/opt/data/profiles")
DATA_ROOT = os.getenv("DATA_ROOT", "/opt/data")

PHISON_LLM_KEY = os.getenv("PHISON_API_KEY", "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249")
TARGET_BASE_URL = os.getenv("LLM_BASE_URL", "https://ainexus.phison.com/api/external/v1")
TARGET_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3.6-35B-A3B-FP8")


class ChatRequest(BaseModel):
    message: str = Field(..., description="使用者輸入")
    # 🆕 讓前端每次點選的模型都能生效：config.yaml 本來就每輪對話都會重寫一次
    # （hermes CLI 是每輪 spawn 一次全新 subprocess，重讀 config.yaml），所以模型
    # 選擇不需要、也不應該綁在容器建立/profile 建立當下，才能做到「這輪選這個模型
    # 就這輪生效」，不用重建容器或重啟任何東西。留空就照 LLM_MODEL 環境變數的預設值。
    
    # 📍 對接的後端不用自己組合/記住 agent_id 字串——直接帶你自己的 user_id 進來，
    # 這裡會自動換算成 /api/session/ensure 建立時同一套規則（f"user_{user_id}"）。
    # agent_id 保留給「未來 multi-agent」用：不傳 user_id、只傳自訂 agent_id 時才生效。
    user_id: str | None = Field(None, description="呼叫 /api/session/ensure 時用的同一個 user_id，帶這個就不用管 agent_id")
    # agent_id/room_id 先給預設值方便 Swagger 快速測試；正式串接時對接的後端一定要
    # 自己指定真的值，不能一直用這個預設值（不然所有使用者會共用同一個 profile/房間）。
    agent_id: str = Field("agent_default", description="Agent ID，有傳 user_id 就會被覆寫，只有 multi-agent 情境才需要自己指定")
    room_id: str = Field("room_default", description="聊天房間 ID（對應 hermes 原生 session，同一個房間才會 resume 上下文）")
    # 之前這裡是必填，但每一輪都要求重複打同一段 system_prompt 很煩——大部分情況下
    # 這個值在 prepare/第一輪之後根本不會變。改成選填，沒傳就沿用系統預設的通用助理人設；
    # 真的要換人設，傳新的值進來就會覆寫（因為 SOUL.md 本來就每輪都重寫一次）。
    system_prompt: str | None = Field(None, description="Agent 的系統提示詞 (SOUL)，留空用系統預設的通用助理人設")
    model: str | None = Field(None, description="這一輪對話要用的模型（前端下拉選單傳入，留空用預設）")
    # 🆕 這個模型端點自己的 API key，如果每個使用者要用自己的 Phison key（不是全系統
    # 共用同一把），從這裡每輪帶進來覆寫，比存在檔案裡更符合「token 是浮動的」這件事——
    # 跟 phison_token 是同樣的道理，只是這個是模型端點的 key，那個是 AINexus 專家路由的 key。
    llm_api_key: str | None = Field(None, description="這個使用者自己的模型 API key，留空用系統預設共用 key")
    # 🆕 AINexus 動態專家路由（query_phison_expert）要用的 bearer token。這是使用者自己
    # 登入 AINexus 拿到的、會過期/浮動的東西，所以設計成「每輪都可以帶」而不是只在
    # ensure/建立時設定一次——沒帶就沿用上一次設定過、還存在 .env 裡的值。
    phison_token: str | None = Field(None, description="AINexus bearer token，浮動/會過期，建議每輪都帶最新的")

    def effective_agent_id(self) -> str:
        """user_id 存在就照 /api/session/ensure 同一套規則換算，忽略 agent_id 欄位。"""
        if self.user_id:
            return f"user_{self.user_id}"
        return self.agent_id

    # Swagger 上「Try it out」預設帶出這組範例，不用自己從零填——model/llm_api_key/
    # phison_token 留空不填也完全沒問題（有系統預設值/沿用上次設定），這裡示範帶入
    # 只是讓你知道欄位長怎樣。
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "demo001",
                "agent_id": "agent_default",
                "room_id": "room_default",
                "system_prompt": "你是一位專業的 AI 助理，能夠協助使用者處理各種任務。",
                "message": "你好，請自我介紹一下",
                "model": None,
                "llm_api_key": None,
                "phison_token": None,
            }
        }
    }
