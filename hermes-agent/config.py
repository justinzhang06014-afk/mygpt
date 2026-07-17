import os
import logging
from pydantic import BaseModel, Field

# 初始化高防禦性企業級日誌系統
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("hermes-proxy")

# 全域配置路徑鎖定
GLOBAL_HERMES_DIR = os.path.expanduser("~/.hermes")
PROFILES_BASE_DIR = os.getenv("PROFILES_BASE_DIR", os.path.expanduser("~/.hermes/profiles"))

# 🔐 管理員後台最低限度防護：固定 token，測試用途，不做帳密系統
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-admin-token")

# 憑證安全防線與內網模型端點
PHISON_LLM_KEY = os.getenv("PHISON_API_KEY", "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249")
PHISON_EMBED_KEY = "AINX-64E91FF7CA1DAB07FE6F8537C5D2DBD396B4BAC1B89C8F3EA1EBC33B2B3ACCEA"
TARGET_BASE_URL = "https://ainexus.phison.com/api/external/v1"
TARGET_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3.6-35B-A3B-FP8")

class ChatRequest(BaseModel):
    agent_id: str = Field(..., description="唯一的 Agent ID (對應官方 Profile 名稱)")
    room_id: str = Field(..., description="聊天房間 ID (對應官方 Session ID)")
    system_prompt: str = Field(..., description="Agent 的系統提示詞 (SOUL)")
    message: str = Field(..., description="用戶輸入的原始訊息")
