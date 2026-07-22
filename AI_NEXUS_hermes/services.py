"""
AI_NEXUS_hermes 的核心：把 hermes 需要的 config.yaml / SOUL.md / mcp_servers 寫進
$PROFILES_BASE_DIR/<agent_id>/，跟 hermes-agent/services.py::ensure_hermes_profile_exists
是同一套已驗證格式，差別只有兩個：

1. 不呼叫 `hermes profile create` CLI。今晚實測驗證過：全新的 HERMES_HOME 目錄，只要
   手動放好 config.yaml + SOUL.md，`hermes mcp list/test` 跟 `hermes chat` 都能正常運作
   （不需要事先跑過 CLI 的 profile create）。這條路本來就沒被 hermes-agent/services.py
   拿來檢查結果（非 clone-from 分支連 returncode 都沒檢查），現在直接省略，行為不變、
   少一個「CLI 假報 already exists」的已知風險來源。
2. 不做 Docker 容器建立/管理——那是「別人的 orchestrator」的責任，這支服務只保證
   輪到它負責的檔案（config.yaml/mcp_servers/SOUL.md/phison_mcp_bridge.py）內容正確，
   容器怎麼起、volume 怎麼掛，交給外部系統。

────────────────────────────────────────────────────────────────────
📍 你想改東西的話，去哪裡改（給不熟這支程式碼的人看的地圖）：
  - config.yaml 的模型設定（provider/base_url/預設模型）      → 下面 _write_isolated_config() 裡的 model_config
  - config.yaml 的記憶體/approvals/terminal/tools 開關        → 下面 _write_isolated_config() 裡的 config_data
  - SOUL.md 的人設/行為規則（例如「必須先呼叫工具」那條）      → 下面 DEFAULT_SYSTEM_PROMPT 常數 或 extended_soul_prompt
  - 新使用者預設的通用助理人設文字                            → 下面 DEFAULT_SYSTEM_PROMPT 常數
  - MCP 伺服器母版清單（新增/修改哪些工具可以用）              → mcp.json（同資料夾）
  - 哪個 MCP 對這個 agent 是常駐/選配                          → mcp_services.py::set_agent_mcp_selection
  - AINexus token / 模型 API key 怎麼填入                     → main.py::agent_chat_stream 呼叫這支檔案時傳的參數
────────────────────────────────────────────────────────────────────
"""
import os
import re
import json
import yaml
import shutil
import asyncio
from pathlib import Path
from datetime import datetime

from config import logger, PROFILES_BASE_DIR, DATA_ROOT, PHISON_LLM_KEY
import mcp_services
import approval_settings

BRIDGE_SCRIPT_NAME = "phison_mcp_bridge.py"

# 📍 改這裡：新使用者、或請求沒帶 system_prompt 時，套用的預設人設文字。
DEFAULT_SYSTEM_PROMPT = "你是一位專業的 AI 助理，能夠協助使用者處理各種任務。"


def _sync_load_session(mapping_path: str, room_id: str) -> str | None:
    if not os.path.exists(mapping_path):
        return None
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = data.get(str(room_id))
        if val is None or str(val).strip() == "None":
            return None
        return str(val)
    except Exception:
        return None


def _sync_save_session(mapping_path: str, room_id: str, native_id: str):
    mapping = {}
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        except Exception:
            mapping = {}
    mapping[str(room_id)] = str(native_id)
    os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4)


async def load_native_session_id(agent_dir: str, room_id: str) -> str | None:
    return await asyncio.to_thread(_sync_load_session, os.path.join(agent_dir, "session_mapping.json"), room_id)


async def save_native_session_id(agent_dir: str, room_id: str, native_id: str):
    await asyncio.to_thread(_sync_save_session, os.path.join(agent_dir, "session_mapping.json"), room_id, native_id)


def _ensure_bridge_script_deployed():
    """
    確保 phison_mcp_bridge.py 存在於 $DATA_ROOT（跟 mcp_servers 母版裡
    "args": ["/opt/data/phison_mcp_bridge.py"] 這個固定路徑對應），
    每個 agent 容器都掛同一個 /opt/data，不用逐一複製到各 agent 目錄。
    """
    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), BRIDGE_SCRIPT_NAME)
    dest = os.path.join(DATA_ROOT, BRIDGE_SCRIPT_NAME)
    if not os.path.exists(source):
        return
    if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(source):
        return
    os.makedirs(DATA_ROOT, exist_ok=True)
    shutil.copy2(source, dest)
    logger.info(f"📦 部署 {BRIDGE_SCRIPT_NAME} -> {dest}")


async def set_phison_token(agent_id: str, token: str) -> None:
    """
    每輪聊天都可以帶新的 AINexus token 進來覆寫（見 main.py::agent_chat_stream）——
    token 是使用者自己登入 AINexus 拿到的、會過期/浮動的東西，不是建立時設一次就
    不變的東西。實際寫入 $HERMES_HOME/.env，跟商店卡片手動填憑證是同一支函式、
    同一個檔案，只是這裡是聊天請求自動幫你填，不用先跑 selection/credentials 兩支端點。
    """
    await asyncio.to_thread(mcp_services.set_agent_mcp_credentials, agent_id, "phison-ainexus", {"PHISON_TOKEN": token})


def _copy_bridge_script_to_agent(agent_dir: str):
    """
    複製 phison_mcp_bridge.py 到指定的 agent 目錄。
    這是為了遠端模式需要上傳所有檔案到 Orchestrator。
    """
    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), BRIDGE_SCRIPT_NAME)
    if not os.path.exists(source):
        logger.warning(f"⚠️ {BRIDGE_SCRIPT_NAME} 不存在: {source}")
        return
    
    dest = os.path.join(agent_dir, BRIDGE_SCRIPT_NAME)
    if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(source):
        return  # 已經是最新版本
    
    shutil.copy2(source, dest)
    logger.info(f"📦 複製 {BRIDGE_SCRIPT_NAME} -> {dest}")


async def ensure_hermes_profile_exists(
    agent_id: str,
    system_prompt: str | None = None,
    model: str | None = None,
    llm_api_key: str | None = None,
) -> str:
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    os.makedirs(agent_dir, exist_ok=True)
    await asyncio.to_thread(_ensure_bridge_script_deployed)
    await asyncio.to_thread(_copy_bridge_script_to_agent, agent_dir)

    def _write_isolated_config():
        agent_approvals = approval_settings.get_agent_approval_settings(agent_id)

        # 📍 改這裡：模型 provider/base_url/預設模型。llm_api_key 是「這個使用者自己的
        # key」，每輪請求可以帶（見 config.py::ChatRequest.llm_api_key），沒帶就退回
        # 系統共用的 PHISON_LLM_KEY/LLM_API_KEY 環境變數。
        if os.getenv("LLM_PROVIDER") == "native":
            model_config = {
                "provider": os.getenv("LLM_NATIVE_PROVIDER", "auto"),
                "default": model or os.getenv("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001"),
            }
        else:
            model_config = {
                "provider": "custom",
                "base_url": os.getenv("LLM_BASE_URL", "https://ainexus.phison.com/api/external/v1"),
                "api_key": llm_api_key or os.getenv("LLM_API_KEY", PHISON_LLM_KEY),
                "default": model or os.getenv("LLM_MODEL", "Qwen/Qwen3.6-35B-A3B-FP8"),
            }

        config_data = {
            "model": model_config,
            "memory": {
                "memory_enabled": True,
                "user_profile_enabled": True,
                "nudge_interval": 10,
                "write_approval": agent_approvals["memory_write_approval"],
                "provider": "",
            },
            "approvals": {"mode": agent_approvals["mode"]},
            "terminal": {
                "backend": "local",
                "cwd": "/workspace",
                "timeout": 180,
                "persistent_shell": True,
            },
            "tools": {
                "enabled": [
                    "file_read", "file_write", "file_edit", "patch_code_file",
                    "view_code_item", "grep_search", "bash",
                ]
            },
            "skills": {"write_approval": agent_approvals["skills_write_approval"]},
            "context": {"enabled": True},
        }

        # mcp_servers_block = mcp_services.build_hermes_mcp_servers_block(agent_id)
        # if mcp_servers_block:
        #     config_data["mcp_servers"] = mcp_servers_block

        # with open(os.path.join(agent_dir, "config.yaml"), "w", encoding="utf-8") as f:
        #     yaml.safe_dump(config_data, f, default_flow_style=False)
        #0722修改
        # 原本獲取動態區塊的程式碼保留
        mcp_servers_block = mcp_services.build_hermes_mcp_servers_block(agent_id) or {}

        # 🚀 根據 _env_var_name 的實作邏輯，精確對接變數名稱
        mcp_servers_block["phison-ainexus-router"] = {
            "command": "python3",
            "args": ["/opt/data/phison_mcp_bridge.py"],
            "enabled": True,
            "env": {
                "PHISON_TOKEN": "${MCP_PHISON_AINEXUS_PHISON_TOKEN}"
            }
        }

        config_data["mcp_servers"] = mcp_servers_block

        with open(os.path.join(agent_dir, "config.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f, default_flow_style=False)


    await asyncio.to_thread(_write_isolated_config)

    soul_path = os.path.join(agent_dir, "SOUL.md")
    # system_prompt 沒帶（None）而且 SOUL.md 已經存在，就不要用預設值蓋掉之前設定過的
    # 人設——只有「真的傳新值」或「這個 agent 從沒寫過 SOUL.md」才會（重）寫入。
    if system_prompt is None and os.path.exists(soul_path):
        return agent_dir

    # 📍 改這裡：新使用者的人設 + 下面這段「強制規則」（4. 是今晚為了讓 hermes 更願意
    # 主動呼叫 query_phison_expert 加的，效果因模型而異，見 README「已知缺口」）。
    extended_soul_prompt = f"""{system_prompt or DEFAULT_SYSTEM_PROMPT}
=====================================================================
【🧠 記憶體自主運行與大腦統整沉澱最高核心條款】
1. 自主記憶捕捉：你在後台擁有全自動的長期記憶大腦（MEMORY.md）。安靜執行，不要向用戶宣告「我已經記下來了」。
2. 記憶定期沉澱與濃縮：保持 MEMORY.md 內的事實條目不超過 15-20 條。一旦超過，刪除過期雜訊，只留下沉澱後的金字塔精華。
3. 你每次開始對話前都會先讀取你自己的memory.md
=====================================================================
【🎯 Phison AINexus 專家流程最高核心條款】
4. 【強制規則，不可跳過】只要使用者問題牽涉公司內部流程、系統操作、出勤、會議室等
   內部資訊，你「必須」在回覆前先依照以下流程處理：
   
   步驟1：先呼叫 get_recommended_experts 工具（把使用者的原話當 query 傳進去）
   - 如果回傳「No relevant experts found for this query」→ 表示沒有專家需求，直接回答使用者問題
   - 如果回傳具體專家清單 → 繼續步驟2
   
   步驟2：根據步驟1回傳的專家清單，選擇最合適的專家 ID，呼叫 get_expert_response 工具
   - 不准用反問時間範圍/系統名稱/帳密等細節取代呼叫工具，因為工具本身就會處理這些細節
   - 呼叫完看到工具回傳結果之後，才可以視情況再追問使用者
=====================================================================
【🚫 其他限制】
5. 不准跳過專家流程：不要嘗試猜測或主動回答牽涉公司內部資訊的問題，一定要先通過專家確認
6. 工具回傳就是答案：專家回傳的結果可以直接呈現給使用者，不要過度修改或重寫
=====================================================================
"""
    await asyncio.to_thread(lambda: Path(soul_path).write_text(extended_soul_prompt, encoding="utf-8"))
    return agent_dir
