import os
import re
import asyncio
import json
import tarfile
import zipfile
import tempfile
import uuid
import shutil
from fastapi import FastAPI, HTTPException, status, UploadFile, File, Form, Header
from fastapi.responses import StreamingResponse, FileResponse, PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
from config import logger, ChatRequest, PROFILES_BASE_DIR, ADMIN_TOKEN
from services import (
    ensure_hermes_profile_exists,
    load_native_session_id,
    save_native_session_id,
)
# 💡 乾淨引入全新獨立的記憶體管理大腦
import memory_manager
# 🚀 每位使用者專屬 Hermes Runtime 容器的建立與管理
import runtime_manager
# 🔌 MCP 商店：母版目錄 + 每個 agent 自己的 mcp.json 讀寫
import mcp_services
import approval_settings
import skills_catalog
# 🆕 0716：ACP（Agent Client Protocol）結構化事件整合，取代舊版文字流猜測法
import acp_client

app = FastAPI(title="Hermes Native Multi-Agent Proxy", version="4.2.0")
# 🛡️ 【資安防禦全局元件】全域記憶體控制鎖與進程對照表
room_locks = {}

# =====================================================================
# 🗑️ 0716 移除：舊版逐行讀 `hermes chat` 終端機文字、用正則表達式硬猜雜訊/
# DANGEROUS COMMAND 提示的那一整組 _NOISE_LINE_PATTERNS / _is_noise_line /
# _TERMINAL_FAILURE_PATTERNS 等機制。改用 `hermes acp` 結構化事件協定
# （見 acp_client.py）之後，這些「用文字猜結構」的程式碼完全不需要了——
# 不是留著沒用到，是真的用不到了，故意整段刪除。
# =====================================================================

# =====================================================================
# 🧭 Skill 關鍵字推薦：實測確認過 hermes CLI 本身完全沒有在對話中主動建議安裝
# 技能的機制，這裡是我們自己疊加的一層。設計原則：
# 1. 只用簡單關鍵字比對決定「要不要去問一次真正的 hermes skills search」，
#    不是每輪對話都呼叫 CLI，避免拖慢正常聊天。
# 2. 真正有沒有這個技能、identifier 長怎樣，一律用 hermes 自己的搜尋結果為準，
#    絕不自己編造 identifier。
# =====================================================================
_SKILL_KEYWORD_QUERIES = {
    "股票": "股票", "stock": "stock", "股價": "股票", "股市": "股票",
    "天氣": "天氣", "weather": "weather", "氣溫": "天氣",
    "翻譯": "翻譯", "translate": "翻譯",
    "匯率": "匯率", "exchange rate": "匯率",
}


def _detect_skill_keyword_query(text: str) -> str | None:
    lowered = text.lower()
    for keyword, query in _SKILL_KEYWORD_QUERIES.items():
        if keyword.lower() in lowered:
            return query
    return None


def _is_skill_installed(agent_dir: str, identifier: str) -> bool:
    """檢查這個 Agent 的 skills/ 資料夾底下，是不是已經裝過對應的技能了"""
    skills_dir = os.path.join(agent_dir, "skills")
    if not os.path.isdir(skills_dir):
        return False
    short_name = identifier.rsplit("/", 1)[-1].lower()
    try:
        installed = {entry.lower() for entry in os.listdir(skills_dir)}
    except OSError:
        return False
    return short_name in installed


def _build_full_skill_identifier(source: str, identifier: str) -> str:
    """
    🛡️【已實測核對】hermes skills search --json 回傳的 identifier 欄位，
    對 clawhub 來源只是短名字（如 "quincy-weather"），直接拿去 install 會因為撞名而失敗
    （"Multiple skills named 'weather' found"）；一定要補上 source 前綴才能精準安裝。
    但像 skills-sh 這種來源，identifier 欄位本身就已經是完整路徑
    （如 "skills-sh/steipete/clawdis/weather"），這時候不能再疊加一次前綴。
    🛡️【實測發現】source 欄位跟 identifier 裡實際嵌入的前綴字串不一定完全一致
    （曾出現 source="skills.sh"、identifier 卻以 "skills-sh/" 開頭），直接比對前綴字串
    會誤判成「還沒加前綴」而重複疊加。改成用「identifier 裡有沒有斜線」判斷是否已經是
    完整路徑更穩健：只有真正的「裸名字」（沒有斜線）才需要補 source 前綴。
    """
    if "/" in identifier:
        return identifier
    return f"{source}/{identifier}"


async def _find_marketplace_suggestion(agent_dir: str, agent_id: str, query: str, env: dict) -> dict | None:
    """呼叫真正的 hermes skills search，找出目前這個 Agent 還沒裝過的第一個相關技能"""
    proc = await asyncio.create_subprocess_exec(
        "hermes", "skills", "search", query, "--json", "--limit", "5",
        env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    try:
        results = json.loads(stdout.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return None

    for item in results:
        source = item.get("source", "")
        raw_identifier = item.get("identifier", "")
        if not raw_identifier:
            continue
        full_identifier = _build_full_skill_identifier(source, raw_identifier)
        if _is_skill_installed(agent_dir, full_identifier):
            continue  # 已經裝過同一個技能了，不用再推薦
        return {
            "identifier": full_identifier,
            "name": item.get("name") or raw_identifier,
            "description": item.get("description") or "",
        }
    return None

# 🗑️ 0716 移除：舊版 active_processes（物理綁定子進程+approve_event 的登記簿）。
# ACP 模式下卡住等待核准的狀態改存在 acp_client.pending_permission_requests，
# 是 request/response 正式往返，不再需要自己管理子進程物件跟 stdin 字元注入。

# 宣告記憶體操作用的 Pydantic 資料模型
class MemoryImportPayload(BaseModel):
    texts: list[str] = Field(..., description="手動強制灌輸或批次匯入的純文字記憶列表")

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Hermes Multi-Agent Proxy 模組化完全體已成功啟動。")
    import monitor
    monitor.start_monitor_task()


@app.get("/api/monitor/stats", status_code=status.HTTP_200_OK)
async def get_monitor_stats():
    """讀取背景監控迴圈寫出的即時 + 5 分鐘平均資源用量快照"""
    import monitor
    if not os.path.exists(monitor.STATS_OUTPUT_PATH):
        return {"status": "pending", "message": "監控資料尚未產生第一筆採樣，請稍候再查詢"}
    with open(monitor.STATS_OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class EnsureRuntimePayload(BaseModel):
    user_id: str = Field(..., description="需要確保 Hermes Runtime 存在的使用者 ID")


# =====================================================================
# 🚀 Runtime Provisioner 入口：backend 在使用者第一次聊天前呼叫，
# 確保該使用者有一個專屬的 Hermes Runtime 容器在跑，回傳其內部網址。
# =====================================================================
@app.post("/api/runtime/ensure", status_code=status.HTTP_200_OK)
async def ensure_runtime(payload: EnsureRuntimePayload):
    try:
        base_url = await asyncio.to_thread(runtime_manager.ensure_user_runtime, payload.user_id)
        return {"status": "success", "user_id": payload.user_id, "base_url": base_url}
    except Exception as e:
        logger.error(f"[Runtime Provisioner] 為使用者 {payload.user_id} 建立 Runtime 失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"建立使用者專屬 Runtime 失敗: {str(e)}")

# 全域並發鎖，確保多房間、多使用者在同時對同一隻 Agent 執行刪除、匯入或 Fork 時，磁碟 I/O 不會發生 Race Condition
memory_io_lock = asyncio.Lock()


# 💬 核心路由一：純文字對話串流 (100% 還原相容原本做法)
# =====================================================================
# 🔀 軌道一核心：聊天串流（內建 AI 自主判定鎖定、暗號發射與 30 秒超時自癒）
# =====================================================================
def _translate_acp_event_to_sse(event) -> str | None:
    """
    🆕 0716 新增：把 acp_client.run_acp_turn() 吐出來的結構化事件轉成 SSE 標記。
    純文字直接串流（打字機效果跟以前一樣），其餘一律包成 JSON 標記讓前端照結構渲染，
    不再需要任何正則表達式去猜終端機文字的意思。
    """
    if isinstance(event, dict):
        if event.get("__acp_permission_request__"):
            options = event["options"]
            tool_call = event["tool_call"]
            body = {
                "options": [{"option_id": o.optionId, "name": o.name, "kind": o.kind} for o in options],
                "title": getattr(tool_call, "title", None),
                "raw_input": getattr(tool_call, "raw_input", None),
            }
            return f"\n__APPROVAL_REQUIRED__:{json.dumps(body, ensure_ascii=False)}\n"
        return None  # __acp_turn_complete__ 等內部事件由呼叫端另外處理，不送給前端

    type_name = type(event).__name__
    if type_name == "AgentMessageChunk":
        return getattr(event.content, "text", "") or ""
    if type_name == "AgentThoughtChunk":
        text = getattr(event.content, "text", "") or ""
        return f"\n__ACP_THOUGHT__:{json.dumps({'text': text}, ensure_ascii=False)}\n"
    if type_name in ("ToolCallStart", "ToolCallProgress"):
        body = {
            "tool_call_id": getattr(event, "tool_call_id", None),
            "title": getattr(event, "title", None),
            "kind": getattr(event, "kind", None),
            "status": getattr(event, "status", None),
        }
        return f"\n__ACP_TOOL__:{json.dumps(body, ensure_ascii=False)}\n"
    if type_name == "AgentPlanUpdate":
        entries = getattr(event, "entries", None) or []
        body = {"entries": [{"content": getattr(e, "content", ""), "status": getattr(e, "status", "")} for e in entries]}
        return f"\n__ACP_PLAN__:{json.dumps(body, ensure_ascii=False)}\n"
    if type_name == "UsageUpdate":
        body = {"used": getattr(event, "used", None), "size": getattr(event, "size", None)}
        return f"\n__ACP_USAGE__:{json.dumps(body, ensure_ascii=False)}\n"
    return None  # 不認得的事件型別一律放行不擋（跟舊版「不確定的行一律放行」同一個設計原則）


@app.post("/api/agent/chat/stream")
async def agent_chat_stream(payload: ChatRequest):
    """
    🆕 0716 全面改用 `hermes acp` 結構化事件協定（跟 VS Code/Zed/JetBrains 外掛同一套
    機制），取代舊版 `hermes chat -q` + 逐行讀文字 + 正則表達式硬猜 DANGEROUS COMMAND
    字串、塞 stdin 字元模擬按鍵的做法。核准請求現在是正式的 request_permission
    request/response（見 acp_client.py），選項由 hermes 自己決定要給幾種
    （實測會給 allow_once/allow_session/allow_always/reject_once/reject_always
    五種，比舊版只做得出 2 選 1 多更多），我們只負責轉發，不猜、不硬寫死。
    已用本機 Ollama 實測驗證過整條路徑，包含一次真正的核准往返。
    """
    agent_dir = await ensure_hermes_profile_exists(payload.agent_id, payload.system_prompt)

    current_env = os.environ.copy()
    current_env.update({
        "HERMES_HOME": agent_dir, "PYTHONUNBUFFERED": "1",
        "HERMES_MEMORY_PLUGIN_PATH": "built-in", "HERMES_BUILTIN_PLUGIN_FORCE": "true", "HERMES_MEMORY_PROVIDER": "built-in",
        "OPENAI_API_KEY": os.getenv("PHISON_API_KEY", "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249"),
        "HERMES_API_KEY": os.getenv("PHISON_API_KEY", "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249"),
        "OPENAI_BASE_URL": "https://ainexus.phison.com/api/external/v1",
        "HERMES_BASE_URL": "https://ainexus.phison.com/api/external/v1",
        "HERMES_MODEL_BASE_URL": "https://ainexus.phison.com/api/external/v1",
        "HINDSIGHT_API_KEY": "AINX-64E91FF7CA1DAB07FE6F8537C5D2DBD396B4BAC1B89C8F3EA1EBC33B2B3ACCEA",
        "HINDSIGHT_LLM_API_KEY": "AINX-64E91FF7CA1DAB07FE6F8537C5D2DBD396B4BAC1B89C8F3EA1EBC33B2B3ACCEA",
        # 🧪 0716：LLM_PROVIDER=native 測試模式用，讓 hermes 原生 provider（例如 anthropic）
        # 讀到金鑰；沒設定 ANTHROPIC_API_KEY 就不會加這個 key，不影響正式路徑
        **({"ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"]} if os.getenv("ANTHROPIC_API_KEY") else {}),
    })
    # 🗑️ 0716 移除：TERMINAL_ENV=ssh / TERMINAL_SSH_HOST 等環境變數（跟 services.py 的
    # terminal.backend 是兩條獨立、會互相打架的路徑，這裡的環境變數這一路很可能才是實際
    # 生效的那個，一起移除，跟 config.yaml 的 terminal.backend=local 保持一致，
    # 徹底不再讓 hermes 嘗試連 SSH）

    room_str = str(payload.room_id).strip()

    if room_str not in room_locks:
        room_locks[room_str] = asyncio.Lock()

    # 讀取歷史 Session 狀態（跟舊版共用同一份 session_mapping.json，ACP 的 session_id
    # 格式剛好也是字串 id，不需要另外設計儲存格式）
    raw_session = await load_native_session_id(agent_dir, room_str)
    resume_session_id = None
    if raw_session:
        cleaned = raw_session.replace("[", "").replace("]", "").replace("'", "").replace('"', "").strip()
        if cleaned and cleaned.lower() != "none":
            resume_session_id = cleaned

    if not resume_session_id and room_locks[room_str].locked():
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Hermes 正在思考中，請稍候。")

    async def acp_stream_generator():
        async with room_locks[room_str]:
            try:
                async for event in acp_client.run_acp_turn(agent_dir, room_str, payload.message, current_env, resume_session_id):
                    if isinstance(event, dict) and event.get("__acp_turn_complete__"):
                        await save_native_session_id(agent_dir, room_str, event["session_id"])
                        continue
                    sse_chunk = _translate_acp_event_to_sse(event)
                    if sse_chunk:
                        print(sse_chunk, end="", flush=True)
                        yield sse_chunk

                # 🧭 Skill 關鍵字推薦：只在使用者這句話命中關鍵字時，才去問一次真正的 hermes skills search
                skill_query = _detect_skill_keyword_query(payload.message)
                if skill_query:
                    try:
                        suggestion = await _find_marketplace_suggestion(agent_dir, payload.agent_id, skill_query, current_env)
                        if suggestion:
                            yield f"\n__SKILL_SUGGESTED__:{json.dumps(suggestion, ensure_ascii=False)}\n"
                    except Exception as e:
                        logger.error(f"[Skill 推薦] 查詢 Marketplace 失敗，略過本輪推薦: {str(e)}")

            except Exception as e:
                logger.error(f"❌ ACP 串流進程發生異常: {str(e)}")
                yield f"\n⚠️ 系統暫時無法連線到 AI 模型，請稍後再試一次。\n"

    return StreamingResponse(acp_stream_generator(), media_type="text/plain")


# =====================================================================
# 🚀 第三部分：雙軌制記憶（Memory/User）動態路由與 Agent 跨體細胞分裂複製核心
# =====================================================================

import asyncio
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Body, status

# 確保引用到您前段已註冊的變數與引入的模組
# global active_processes
# import memory_manager

logger = logging.getLogger("fastapi_agent")

# 全域異步鎖，防止多房間/多前端並行重寫同一個檔案導致 Race Condition 損壞
memory_io_lock = asyncio.Lock()


# ---------------------------------------------------------------------
# Pydantic 核心 DTO 模型宣告
# ---------------------------------------------------------------------
class MemoryImportPayload(BaseModel):
    file_type: str = Field(..., description="指定要灌輸的檔案軌道：'memory' 或 'user'")
    texts: list[str] = Field(..., description="手動強制灌輸或批次匯入的純文字列表")

class AgentForkPayload(BaseModel):
    source_agent_id: str = Field(..., description="被複製的源頭 Agent ID")
    copy_memory: bool = Field(True, description="是否複製繼承 memory.md")
    copy_user: bool = Field(True, description="是否複製繼承 user.md")


# ---------------------------------------------------------------------
# 0. 【拉取全平台可用 Agent 清單】
# ---------------------------------------------------------------------
@app.get("/api/agents/available-list", status_code=status.HTTP_200_OK)
async def get_available_agents_list():
    """
    供前端 Vue 渲染下拉選單，查看目前有哪些現存的 Agent 可以選取並做繼承
    """
    agents = await asyncio.to_thread(memory_manager.get_all_available_agents)
    return {"status": "success", "agents": agents}


# ---------------------------------------------------------------------
# 1. 【逆向注入解封印網關】
# ---------------------------------------------------------------------
@app.post("/api/agent/approve-write", status_code=status.HTTP_200_OK)
async def approve_agent_write(
    room_id: str = Body(..., embed=True),
    option_id: str = Body(..., embed=True),
):
    """
    🆕 0716 改版：人機審查解封印網關。前端彈窗現在傳的是使用者選的 option_id
    （對應 __APPROVAL_REQUIRED__ 事件裡真正由 hermes 提供的選項清單，實測常見值
    是 allow_once/allow_session/allow_always/reject_once/reject_always），
    不再是單純的 true/false——這是 ACP 的 request_permission 正式回應機制，
    不是我們自己土法煉鋼湊出來的。
    """
    logger.info(f"[解封印網關] 收到房間 {room_id} 的審查結果: {option_id}")
    try:
        found = acp_client.submit_permission_decision(room_id, option_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not found:
        raise HTTPException(status_code=404, detail="找不到對應房間的待核准請求，可能已超時自癒")
    return {"status": "success", "message": "已成功解除封印並注入訊號"}


# ---------------------------------------------------------------------
# 2. 【雙軌讀取大禮包 (不寫死) - 🔒 升級空檔案安全防禦降級版】
# ---------------------------------------------------------------------
import os  # 🧠 確保您的檔案頂部有 import os

import os

@app.get("/api/agent/{agent_id}/memories/{file_type}", status_code=status.HTTP_200_OK)
async def get_agent_templated_memories(agent_id: str, file_type: str):
    """
    動態動態讀取：由 URL 的 agent_id 與 file_type 決定調閱哪一個獨立 Agent 的檔案
    """
    if file_type.lower() not in ["memory", "user"]:
        raise HTTPException(status_code=400, detail="file_type 必須為 'memory' 或 'user'")
        
    logger.info(f"[雙軌讀取] 調閱 Agent: {agent_id} 的 {file_type}.md 結構化資料")
    
    # 🎯 1. 定義 Docker 容器內對應的掛載根目錄
    base_dir = "/opt/data" 
    
    # 🎯 2. 🧬 拒絕寫死！利用變數動態拼接出：/opt/data/profiles/agent_xxxx/USER.md
    # 🐛 0716 修正：hermes 實際寫出來的檔名是大寫（MEMORY.md / USER.md），這裡原本組小寫
    # 檔名做存在性檢查，在 Linux（大小寫敏感）上會永遠判定「檔案不存在」，導致一律回傳空大腦。
    target_file_path = os.path.join(base_dir, "profiles", agent_id, "memories", f"{file_type.upper()}.md")
    
    logger.info(f"[實體路徑檢查] 正在檢查獨立路徑: {target_file_path}")
    
    # 🎯 3. 物理攔截：如果該 Agent 的這個檔案還沒建立，安全降級
    if not os.path.exists(target_file_path):
        logger.warning(f"⚠️ [冷啟動自癒] 找不到獨立路徑: {target_file_path}，自動配平回傳乾淨空大腦結構。")
        return {
            "meta": {
                "brain_saturation_percentage": 0
            },
            "memories": []
        }
    
    # 🎯 4. 檔案存在，安全放行進入解析器
    async with memory_io_lock:
        try:
            package = await asyncio.to_thread(
                memory_manager.parse_physical_file_to_json, 
                agent_id, 
                file_type
            )
            return package
        except Exception as e:
            logger.error(f"[雙軌讀取] 失敗: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))




# ---------------------------------------------------------------------
# 3. 【手動點擊刪除特定記憶 (雙軌不寫死)】
# ---------------------------------------------------------------------
@app.delete("/api/agent/{agent_id}/memories/{file_type}/{fact_id}", status_code=status.HTTP_200_OK)
async def delete_agent_specific_fact(agent_id: str, file_type: str, fact_id: str):
    """
    當使用者在右側面板卡片點擊 🗑️ 時觸發。
    動態判定並刪除 user.md 或 memory.md 內部的指定事實，就地刷新回傳。
    """
    if file_type.lower() not in ["memory", "user"]:
        raise HTTPException(status_code=400, detail="file_type 必須為 'memory' 或 'user'")
        
    logger.info(f"[手動刪除] 觸發雙軌刪除 -> Agent: {agent_id}, 檔案: {file_type}, FactID: {fact_id}")
    
    async with memory_io_lock:
        try:
            # 1. 讀取指定軌道最新的結構化 JSON
            current_package = await asyncio.to_thread(
                memory_manager.parse_physical_file_to_json, agent_id, file_type
            )
            memories_list = current_package.get("memories", [])
            
            # 2. 尋找並過濾，萃取其餘留下來的項目為純文字清單
            remaining_texts = []
            found = False
            for item in memories_list:
                if str(item.get("id")) == str(fact_id):
                    found = True
                    continue # 排除目標項目
                if "text" in item:
                    remaining_texts.append(item["text"])
            
            if not found:
                return current_package # 找不到免重寫，防禦性直接返回
            
            # 3. 呼叫雙軌落盤，壓回實體硬碟
            await asyncio.to_thread(
                memory_manager.write_json_memories_back_to_md,
                agent_id,
                file_type,
                remaining_texts
            )
            
            # 4. 就地刷新
            refreshed = await asyncio.to_thread(
                memory_manager.parse_physical_file_to_json, agent_id, file_type
            )
            return refreshed
            
        except Exception as e:
            logger.error(f"[手動刪除] 發生異常: {str(e)}")
            raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")


# ---------------------------------------------------------------------
# 4. 【手動強制灌輸與大量匯入 (不寫死，透過 Body 指定軌道)】
# ---------------------------------------------------------------------
@app.post("/api/agent/{agent_id}/memories/import", status_code=status.HTTP_200_OK)
async def import_agent_bulk_data(agent_id: str, payload: MemoryImportPayload):
    """
    使用者手動輸入「🧠 記住這句話」或批次匯入文字檔。
    由 payload.file_type 決定寫進 user.md 還是 memory.md，自動去重後刷新。
    """
    file_type = payload.file_type
    incoming_texts = payload.texts
    
    if file_type.lower() not in ["memory", "user"]:
        raise HTTPException(status_code=400, detail="Body 的 file_type 必須為 'memory' 或 'user'")
    if not incoming_texts:
        raise HTTPException(status_code=400, detail="匯入的純文字清單不能為空")
        
    logger.info(f"[大量匯入] 注入 Agent: {agent_id}, 軌道: {file_type}, 數量: {len(incoming_texts)}")
    
    async with memory_io_lock:
        try:
            # 1. 獲取現存資料以便比對
            current_package = await asyncio.to_thread(
                memory_manager.parse_physical_file_to_json, agent_id, file_type
            )
            existing_memories = current_package.get("memories", [])
            existing_texts_set = {item.get("text", "").strip() for item in existing_memories}
            
            final_text_list = [item.get("text") for item in existing_memories if "text" in item]
            
            # 2. 去重清洗
            has_changes = False
            for text in incoming_texts:
                cleaned = text.strip()
                if cleaned and (cleaned not in existing_texts_set) and (cleaned not in final_text_list):
                    final_text_list.append(cleaned)
                    has_changes = True
                    
            if not has_changes:
                return current_package # 沒有新內容，直接回傳
            
            # 3. 呼叫雙軌落盤
            await asyncio.to_thread(
                memory_manager.write_json_memories_back_to_md,
                agent_id,
                file_type,
                final_text_list
            )
            
            # 4. 重新加載，讓 memory_manager 的關鍵字自動分類紅利就地刷新
            refreshed = await asyncio.to_thread(
                memory_manager.parse_physical_file_to_json, agent_id, file_type
            )
            return refreshed
            
        except Exception as e:
            logger.error(f"[大量匯入] 失敗: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------
# 5. 【細胞分裂：一鍵繼承快照、脫鉤各自發展】
# ---------------------------------------------------------------------
@app.post("/api/agent/{agent_id}/inherit-fork", status_code=status.HTTP_200_OK)
async def inherit_fork_agent_snapshot(agent_id: str, payload: AgentForkPayload):
    """
    【細胞融合最高核心】
    前端已修正傳入標準 UUID (如 agent_a26dcad41262)。
    此處直接進行硬碟路徑盤點，並執行 C 自己與 A/B 記憶的聯集合併、自動去重複。
    """
    source_id = payload.source_agent_id
    logger.info(f"[細胞融合] 目標: {agent_id} 正在融合繼承 源頭: {source_id} 的快照")
    
    if source_id == agent_id:
        raise HTTPException(status_code=400, detail="源頭 Agent 與目標 Agent 不能相同")
        
    async with memory_io_lock:
        try:
            # 盤點目前這台機器硬碟裡所有可用的 Agent 清單
            available_agents = await asyncio.to_thread(memory_manager.get_all_available_agents)
            
            # 🛡️ 嚴格比對前端傳入的 UUID 是否在硬碟名單中
            if source_id not in available_agents:
                logger.error(f"❌ [融合失敗] 找不到源頭 UUID '{source_id}'。目前硬碟實際存在: {available_agents}")
                raise HTTPException(status_code=404, detail=f"找不到源頭 Agent: '{source_id}'")
            
            report = {"status": "success", "forked_tracks": []}
            
            # 🛡️ 軌道一：繼承 facts 專業知識（融合且不洗掉 C 自己）
            if payload.copy_memory:
                # 1. 讀取「源頭 Agent」的記憶文字
                src_memory_pkg = await asyncio.to_thread(
                    memory_manager.parse_physical_file_to_json, source_id, "memory"
                )
                src_memory_texts = [item.get("text") for item in src_memory_pkg.get("memories", []) if "text" in item]
                
                # 2. 讀取「目標 Agent (C自己)」目前的舊記憶文字
                target_memory_texts = []
                if agent_id in available_agents:
                    tgt_memory_pkg = await asyncio.to_thread(
                        memory_manager.parse_physical_file_to_json, agent_id, "memory"
                    )
                    target_memory_texts = [item.get("text") for item in tgt_memory_pkg.get("memories", []) if "text" in item]
                
                # 3. 🧠【聯集合併與去重複】
                combined_memory_texts = list(dict.fromkeys(target_memory_texts + src_memory_texts))
                
                # 4. 將這份完美的「融合大清單」寫回 C 的硬碟
                await asyncio.to_thread(
                    memory_manager.write_json_memories_back_to_md,
                    agent_id, "memory", combined_memory_texts
                )
                report["forked_tracks"].append("memory.md")
                
            # 🚀 軌道二：繼承用戶偏好（融合且不洗掉 C 自己）
            if payload.copy_user:
                # 1. 讀取「源頭 Agent」的用戶偏好文字
                src_user_pkg = await asyncio.to_thread(
                    memory_manager.parse_physical_file_to_json, source_id, "user"
                )
                src_user_texts = [item.get("text") for item in src_user_pkg.get("memories", []) if "text" in item]
                
                # 2. 讀取「目標 Agent (C自己)」目前的舊偏好文字
                target_user_texts = []
                if agent_id in available_agents:
                    tgt_user_pkg = await asyncio.to_thread(
                        memory_manager.parse_physical_file_to_json, agent_id, "user"
                    )
                    target_user_texts = [item.get("text") for item in tgt_user_pkg.get("memories", []) if "text" in item]
                
                # 3. 🧠【聯集合併與去重複】
                combined_user_texts = list(dict.fromkeys(target_user_texts + src_user_texts))
                
                # 4. 寫回 C 的硬碟
                await asyncio.to_thread(
                    memory_manager.write_json_memories_back_to_md,
                    agent_id, "user", combined_user_texts
                )
                report["forked_tracks"].append("user.md")
                
            logger.info(f"[細胞融合] Agent {agent_id} 快照繼承與重複資料刪除融合成功。")
            return report

        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"[細胞融合] 嚴重失敗: {str(e)}")
            raise HTTPException(status_code=500, detail=f"細胞分裂快照合併失敗: {str(e)}")


# =====================================================================
# 🚀 第四部分：真 Clone / Export-Import / 安全掃描（全部走 hermes 原生指令）
# =====================================================================

STATIC_UPLOAD_DIR = "/app/static/uploads"
os.makedirs(STATIC_UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


def _agent_env(agent_id: str) -> dict:
    """HERMES_HOME 指向該 Agent 既有的路徑；適用於 show/export/skills/security 這類「讀取既有 profile」的操作。"""
    env = os.environ.copy()
    env["HERMES_HOME"] = os.path.join(PROFILES_BASE_DIR, agent_id)
    return env


class AgentCloneFromPayload(BaseModel):
    system_prompt: str = Field(..., description="新 Agent 自己的系統提示詞(SOUL)")
    source_system_prompt: str | None = Field(None, description="來源 Agent 自己真正的系統提示詞，來源從未對話過需要臨時補初始化時使用")


# ---------------------------------------------------------------------
# 6. 【真 Clone】走 hermes profile create --clone-from --clone-all
# ---------------------------------------------------------------------
@app.post("/api/agent/{agent_id}/clone-from/{source_agent_id}", status_code=status.HTTP_200_OK)
async def clone_agent_from_source(agent_id: str, source_agent_id: str, payload: AgentCloneFromPayload):
    """
    用 hermes 原生指令複製出一個全新 Agent(config、SOUL、skills、memories 全部繼承來源)，
    不再像舊版 inherit-fork 只合併兩份 .md 檔案文字。
    """
    if agent_id == source_agent_id:
        raise HTTPException(status_code=400, detail="新 Agent 與來源 Agent 不能相同")

    try:
        agent_dir = await ensure_hermes_profile_exists(
            agent_id, payload.system_prompt, clone_from=source_agent_id,
            source_system_prompt=payload.source_system_prompt,
        )
        return {"status": "success", "agent_id": agent_id, "source_agent_id": source_agent_id, "agent_dir": agent_dir}
    except RuntimeError as e:
        logger.error(f"[真Clone] 失敗: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[真Clone] 未預期錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"複製失敗: {str(e)}")


# ---------------------------------------------------------------------
# 7. 【匯出 Agent】三種格式：hermes 原生 tar.gz／轉封裝 zip／Skill 標準 markdown
# ---------------------------------------------------------------------
async def _export_agent_as_skill(agent_id: str, agent_dir: str) -> PlainTextResponse:
    soul_path = os.path.join(agent_dir, "SOUL.md")
    soul_text = ""
    if os.path.exists(soul_path):
        with open(soul_path, "r", encoding="utf-8") as f:
            soul_text = f.read().strip()

    memory_pkg = await asyncio.to_thread(memory_manager.parse_physical_file_to_json, agent_id, "memory")
    user_pkg = await asyncio.to_thread(memory_manager.parse_physical_file_to_json, agent_id, "user")
    memory_lines = [f"- {item['text']}" for item in memory_pkg.get("memories", []) if item.get("text")]
    user_lines = [f"- {item['text']}" for item in user_pkg.get("memories", []) if item.get("text")]

    description = (soul_text.splitlines()[0] if soul_text else f"由 {agent_id} 匯出的技能包").strip()[:200]

    skill_md = f"""---
name: {agent_id}
description: {description}
---

# {agent_id} 技能包

## 人格與系統提示詞 (SOUL)

{soul_text or "(尚無自訂 SOUL.md)"}

## 專業知識重點 (memory.md)

{chr(10).join(memory_lines) or "(尚無記憶)"}

## 用戶偏好重點 (user.md)

{chr(10).join(user_lines) or "(尚無記錄)"}
"""
    return PlainTextResponse(skill_md, media_type="text/markdown", headers={
        "Content-Disposition": f'attachment; filename="{agent_id}_SKILL.md"'
    })


@app.get("/api/agent/{agent_id}/export")
async def export_agent(agent_id: str, format: str = "hermes"):
    fmt = format.lower()
    if fmt not in ("hermes", "zip", "skill"):
        raise HTTPException(status_code=400, detail="format 必須為 hermes、zip 或 skill")

    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    if not os.path.isdir(agent_dir):
        raise HTTPException(status_code=404, detail=f"找不到 Agent: {agent_id}")

    if fmt == "skill":
        return await _export_agent_as_skill(agent_id, agent_dir)

    # hermes / zip 都先走原生 `hermes profile export` 產生 tar.gz
    with tempfile.TemporaryDirectory() as tmp_dir:
        tar_path = os.path.join(tmp_dir, f"{agent_id}.tar.gz")
        proc = await asyncio.create_subprocess_exec(
            "hermes", "profile", "export", agent_id, "-o", tar_path,
            env=_agent_env(agent_id),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not os.path.exists(tar_path):
            raise HTTPException(status_code=500, detail=f"hermes profile export 失敗: {stderr.decode('utf-8', errors='ignore').strip()}")

        if fmt == "hermes":
            final_path = os.path.join(tempfile.gettempdir(), f"{agent_id}_{uuid.uuid4().hex[:8]}.tar.gz")
            shutil.copy(tar_path, final_path)
            return FileResponse(
                final_path, filename=f"{agent_id}.tar.gz", media_type="application/gzip",
                background=BackgroundTask(os.remove, final_path)
            )

        # fmt == "zip"：這層轉封裝是我們外加的方便格式，hermes 本身只出 tar.gz
        extract_dir = os.path.join(tmp_dir, "extract")
        os.makedirs(extract_dir, exist_ok=True)
        with tarfile.open(tar_path, "r:gz") as tf:
            tf.extractall(extract_dir)

        final_zip = os.path.join(tempfile.gettempdir(), f"{agent_id}_{uuid.uuid4().hex[:8]}.zip")
        with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(extract_dir):
                for fname in files:
                    full_path = os.path.join(root, fname)
                    zf.write(full_path, os.path.relpath(full_path, extract_dir))
        return FileResponse(
            final_zip, filename=f"{agent_id}.zip", media_type="application/zip",
            background=BackgroundTask(os.remove, final_zip)
        )


# ---------------------------------------------------------------------
# 8. 【匯入技能】上傳一份 SKILL.md，透過 hermes skills install <URL> 安裝
# ---------------------------------------------------------------------
@app.post("/api/agent/{agent_id}/skills/import", status_code=status.HTTP_200_OK)
async def import_skill_to_agent(
    agent_id: str, name: str = Form(...), file: UploadFile = File(...),
    system_prompt: str | None = Form(None),
):
    """
    CLI 唯一支援本地內容安裝的合法路徑是「HTTP(S) URL 指向一份 SKILL.md」，沒有本機資料夾安裝指令。
    因此把上傳檔案暫存在本代理自己的 /static 底下，讓 hermes CLI 透過 HTTP 回頭抓取後安裝，全程走官方指令。
    v1 僅支援單一 SKILL.md,不支援多檔案/附件技能包。
    """
    # 🐛 0717 修正：跟今晚「複製」踩到的同一個坑——agent 剛建立、從沒聊過天時，
    # profile 目錄根本不存在，原本這裡直接 404。改成比照 clone-from 的修法，
    # 用 ensure_hermes_profile_exists 順手補建立（用真正的 system_prompt，沒有就退回通用預設）。
    agent_dir = await ensure_hermes_profile_exists(agent_id, system_prompt or f"你是 {agent_id}，一位專業助理。")

    upload_id = uuid.uuid4().hex
    upload_dir = os.path.join(STATIC_UPLOAD_DIR, upload_id)
    os.makedirs(upload_dir, exist_ok=True)
    dest_path = os.path.join(upload_dir, "SKILL.md")
    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    public_url = f"http://lm_hermes_agent:8643/static/uploads/{upload_id}/SKILL.md"
    try:
        proc = await asyncio.create_subprocess_exec(
            "hermes", "skills", "install", public_url, "--name", name, "--yes",
            env=_agent_env(agent_id),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"hermes skills install 失敗: {stderr.decode('utf-8', errors='ignore').strip()}")

    return {"status": "success", "stdout": stdout.decode("utf-8", errors="ignore").strip()}


# ---------------------------------------------------------------------
# 9. 【安全掃描】hermes security audit(OSV.dev 供應鏈漏洞掃描)
# ---------------------------------------------------------------------
@app.get("/api/agent/{agent_id}/security-audit", status_code=status.HTTP_200_OK)
async def run_security_audit(agent_id: str):
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    if not os.path.isdir(agent_dir):
        raise HTTPException(status_code=404, detail=f"找不到 Agent: {agent_id}")

    try:
        proc = await asyncio.create_subprocess_exec(
            "hermes", "security", "audit", "--json",
            env=_agent_env(agent_id),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="hermes security audit 逾時(OSV.dev 掃描超過 60 秒)")

    raw_stdout = stdout.decode("utf-8", errors="ignore").strip()
    try:
        report = json.loads(raw_stdout)
    except json.JSONDecodeError:
        report = {"raw": raw_stdout or stderr.decode("utf-8", errors="ignore").strip()}

    return {"status": "success" if proc.returncode == 0 else "warning", "return_code": proc.returncode, "report": report}


# ---------------------------------------------------------------------
# 10. 【Skill 商城】走 hermes skills search --json / hermes skills install
# ---------------------------------------------------------------------
class SkillInstallPayload(BaseModel):
    identifier: str = Field(..., description="Skill 識別碼,例如 official/security/1password")
    name: str | None = Field(None, description="覆寫技能名稱(選填)")
    force: bool = Field(False, description="使用者已看過資安風險說明、仍決定安裝時傳 true，會加上 --force")
    system_prompt: str | None = Field(None, description="Agent 真正的 system_prompt，剛建立、profile 目錄還不存在時用來補初始化")


def _parse_skill_install_outcome(stdout: str) -> dict:
    """
    🛡️【實測發現】hermes skills install 就算被自己的資安掃描擋下來，行程本身還是正常結束
    （returncode 0），單看「有沒有丟例外」永遠只會回傳 success。一定要看 stdout 內容才知道
    到底是「真的裝好了」還是「被擋下來了」。
    """
    if "Installed:" in stdout and "BLOCKED" not in stdout:
        return {"outcome": "installed", "security_report": None}

    if "BLOCKED" in stdout or "Installation blocked" in stdout:
        # 擷取「Running security scan...」到結尾那一段，就是 hermes 自己講的實際風險內容，
        # 原封不動秀給使用者看，不用我們自己重新編一套說法
        scan_start = stdout.find("Running security scan")
        report = stdout[scan_start:].strip() if scan_start >= 0 else stdout.strip()
        return {"outcome": "blocked", "security_report": report}

    return {"outcome": "unknown", "security_report": stdout.strip()}


@app.get("/api/agent/{agent_id}/skills/search")
async def search_skills_hub(agent_id: str, query: str, source: str = "all", limit: int = 24, system_prompt: str | None = None):
    """
    用 hermes 官方技能市集(88000+ 個技能)搜尋,直接吃 --json 輸出,不自己解析文字表格。
    """
    # 🐛 0717 修正：跟 import_skill_to_agent 同一個坑，剛建立的 agent 還沒 profile 目錄，
    # 順手補建立，不要一律 404。
    agent_dir = await ensure_hermes_profile_exists(agent_id, system_prompt or f"你是 {agent_id}，一位專業助理。")
    if not query.strip():
        raise HTTPException(status_code=400, detail="搜尋關鍵字不能為空")

    proc = await asyncio.create_subprocess_exec(
        "hermes", "skills", "search", query, "--json", "--limit", str(limit), "--source", source,
        env=_agent_env(agent_id),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"hermes skills search 失敗: {stderr.decode('utf-8', errors='ignore').strip()}")

    try:
        results = json.loads(stdout.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError:
        results = []

    return {"status": "success", "query": query, "results": results}


@app.post("/api/agent/{agent_id}/skills/install-from-hub", status_code=status.HTTP_200_OK)
async def install_skill_from_hub(agent_id: str, payload: SkillInstallPayload):
    """從官方 Skill 市集直接安裝(identifier 來自 search 結果),完全走 hermes skills install。"""
    # 🐛 0717 修正：跟 import_skill_to_agent 同一個坑，剛建立的 agent 還沒 profile 目錄，
    # 順手補建立，不要一律 404——這正是建立 agent 彈窗勾選「基礎技能」會踩到的情境。
    agent_dir = await ensure_hermes_profile_exists(agent_id, payload.system_prompt or f"你是 {agent_id}，一位專業助理。")

    install_args = ["hermes", "skills", "install", payload.identifier, "--yes"]
    if payload.name:
        install_args += ["--name", payload.name]
    if payload.force:
        install_args.append("--force")

    proc = await asyncio.create_subprocess_exec(
        *install_args, env=_agent_env(agent_id),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"hermes skills install 失敗: {stderr.decode('utf-8', errors='ignore').strip()}")

    stdout_text = stdout.decode("utf-8", errors="ignore").strip()
    outcome = _parse_skill_install_outcome(stdout_text)
    return {"status": "success", "stdout": stdout_text, **outcome}


# =====================================================================
# 🗂️ 12. Skill 待審核清單：當 Agent 的 config.yaml 把 skills.write_approval 打開後，
# Hermes 自己在 skill_manage（建立/編輯/修改/刪除技能檔案）時就不會直接落盤，
# 而是暫存一筆 JSON 紀錄在 <HERMES_HOME>/pending/skills/<id>.json，等使用者審核。
#
# 🛡️【已對照 hermes 原始碼確認】沒有對應的 `hermes skills pending` CLI 子指令——
# 這套審核 UX 原本只存在於互動聊天裡的 /skills pending、/skills approve、/skills reject
# 斜線指令（hermes_cli/write_approval_commands.py）。這裡改成直接 import 並呼叫
# hermes 自己內部的 tools.write_approval / tools.skill_manager_tool 函式，
# 邏輯跟斜線指令內部呼叫的完全一樣，只是換一個入口。
#
# 🛡️ 每個請求用 hermes 官方提供的 contextvars 機制（set_hermes_home_override）
# 暫時把 HERMES_HOME 切到這個 Agent 的目錄，處理完立刻還原——這是官方文件註明
# 「deliberately does not mutate os.environ」的安全作法，避免同一個 process 裡
# 多個 Agent 的請求並發時互相污染彼此的 HERMES_HOME。
# =====================================================================
def _run_scoped_to_agent(agent_dir: str, fn):
    """在 contextvars 範圍內執行 fn()，暫時把 HERMES_HOME 切到指定 Agent"""
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    token = set_hermes_home_override(agent_dir)
    try:
        return fn()
    finally:
        reset_hermes_home_override(token)


@app.get("/api/agent/{agent_id}/skills/pending", status_code=status.HTTP_200_OK)
async def list_pending_skill_writes(agent_id: str):
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    if not os.path.isdir(agent_dir):
        raise HTTPException(status_code=404, detail=f"找不到 Agent: {agent_id}")

    def _run():
        from tools.write_approval import list_pending
        return list_pending("skills")

    records = await asyncio.to_thread(_run_scoped_to_agent, agent_dir, _run)
    return {"status": "success", "pending": records}


@app.post("/api/agent/{agent_id}/skills/pending/{pending_id}/approve", status_code=status.HTTP_200_OK)
async def approve_pending_skill_write(agent_id: str, pending_id: str):
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    if not os.path.isdir(agent_dir):
        raise HTTPException(status_code=404, detail=f"找不到 Agent: {agent_id}")

    def _run():
        from tools.write_approval import get_pending, discard_pending
        from tools.skill_manager_tool import apply_skill_pending

        record = get_pending("skills", pending_id)
        if record is None:
            return {"found": False}

        # 🛡️ 完全比照 hermes 自己 /skills approve 的邏輯：套用成功才移除待審核紀錄，
        # 失敗的話留著，讓使用者知道發生什麼事、可以再試一次
        apply_result = json.loads(apply_skill_pending(record.get("payload", {})))
        applied_ok = bool(apply_result.get("success"))
        if applied_ok:
            discard_pending("skills", pending_id)
        return {"found": True, "applied": applied_ok, "detail": apply_result}

    outcome = await asyncio.to_thread(_run_scoped_to_agent, agent_dir, _run)
    if not outcome["found"]:
        raise HTTPException(status_code=404, detail=f"找不到待審核紀錄: {pending_id}")
    return {"status": "success", **outcome}


@app.post("/api/agent/{agent_id}/skills/pending/{pending_id}/reject", status_code=status.HTTP_200_OK)
async def reject_pending_skill_write(agent_id: str, pending_id: str):
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    if not os.path.isdir(agent_dir):
        raise HTTPException(status_code=404, detail=f"找不到 Agent: {agent_id}")

    def _run():
        from tools.write_approval import discard_pending
        return discard_pending("skills", pending_id)

    removed = await asyncio.to_thread(_run_scoped_to_agent, agent_dir, _run)
    if not removed:
        raise HTTPException(status_code=404, detail=f"找不到待審核紀錄: {pending_id}")
    return {"status": "success", "removed": True}


# =====================================================================
# 🔌 13. MCP 商店：母版目錄查詢 + 每個 agent 自己的 mcp.json 讀寫
# 真相來源只有實體檔案（母版 hermes-agent/mcp.json + 每個 agent 自己的
# $HERMES_HOME/mcp.json），沒有另外存 Postgres，避免兩邊資料兜不起來。
# =====================================================================
class McpSelectionPayload(BaseModel):
    selection: str | None = Field(None, description='null(移除) / "resident"(常駐) / "optional_installed"(選配已安裝)')


class McpCredentialsPayload(BaseModel):
    credentials: dict[str, str] = Field(..., description="憑證欄位 key -> 使用者填的值，留空字串代表清除")


class AgentApprovalsPayload(BaseModel):
    mode: str | None = Field(None, description='"manual" / "smart" / "off"，對應 hermes 原生 approvals.mode')
    memory_write_approval: bool | None = Field(None, description="寫入 MEMORY.md/USER.md 前要不要先問")
    skills_write_approval: bool | None = Field(None, description="安裝/修改技能前要不要先問")


@app.get("/api/mcp/catalog", status_code=status.HTTP_200_OK)
async def get_mcp_master_catalog():
    """母版目錄：管理員後台維護的全平台可用 MCP 清單，不含任何密碼實際值"""
    catalog = await asyncio.to_thread(mcp_services.load_master_catalog)
    return {"status": "success", "mcpServers": catalog}


@app.get("/api/skills/catalog", status_code=status.HTTP_200_OK)
async def get_skills_master_catalog():
    """管理員精選的技能起手式清單，建立 agent 時可以直接勾選安裝"""
    catalog = await asyncio.to_thread(skills_catalog.load_master_catalog)
    return {"status": "success", "skills": catalog}


@app.get("/api/agent/{agent_id}/mcp", status_code=status.HTTP_200_OK)
async def get_agent_mcp_state(agent_id: str):
    """這個 agent 目前擁有哪些 MCP（常駐/選配/未選）、憑證有沒有填——布林值，不回傳實際密碼"""
    servers = await asyncio.to_thread(mcp_services.get_agent_mcp_state, agent_id)
    return {"status": "success", "servers": servers}


@app.post("/api/agent/{agent_id}/mcp/{mcp_name}/selection", status_code=status.HTTP_200_OK)
async def set_agent_mcp_selection(agent_id: str, mcp_name: str, payload: McpSelectionPayload):
    """使用者在商店卡片點「設為常駐」/「加入(選配)」/「移除」"""
    try:
        entry = await asyncio.to_thread(mcp_services.set_agent_mcp_selection, agent_id, mcp_name, payload.selection)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "entry": entry}


@app.post("/api/agent/{agent_id}/mcp/{mcp_name}/credentials", status_code=status.HTTP_200_OK)
async def set_agent_mcp_credentials(agent_id: str, mcp_name: str, payload: McpCredentialsPayload):
    """使用者在商店卡片填寫的 API Key/帳密：實際值只落地到該 agent 的 .env，這裡不回傳明碼"""
    try:
        entry = await asyncio.to_thread(mcp_services.set_agent_mcp_credentials, agent_id, mcp_name, payload.credentials)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "success", "entry": entry}


@app.get("/api/agent/{agent_id}/approvals", status_code=status.HTTP_200_OK)
async def get_agent_approvals(agent_id: str):
    """這個 agent 目前的三個 approval 開關（mode/memory/skills），沒設定過就回傳預設值"""
    settings = await asyncio.to_thread(approval_settings.get_agent_approval_settings, agent_id)
    return {"status": "success", "settings": settings}


@app.post("/api/agent/{agent_id}/approvals", status_code=status.HTTP_200_OK)
async def set_agent_approvals(agent_id: str, payload: AgentApprovalsPayload):
    """更新這個 agent 的 approval 設定，只更新有傳的欄位；下一輪對話開始前 config.yaml 就會用新值重寫"""
    try:
        settings = await asyncio.to_thread(
            approval_settings.set_agent_approval_settings, agent_id, payload.model_dump()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "settings": settings}


# =====================================================================
# 🛠️ 14. 管理員後台：不做帳密登入系統，只用一組固定 token（環境變數 ADMIN_TOKEN）
# 做最低限度防護。管理員在這裡編輯的是「母版」hermes-agent/mcp.json，
# 不會直接動到任何一個 agent 自己的 mcp.json/config.yaml。
# =====================================================================
class McpCatalogEntryPayload(BaseModel):
    name: str = Field(..., description="MCP 名稱，同時也是 mcp_servers 的 key")
    displayName: str = Field(..., description="商店卡片上顯示的名稱")
    description: str = Field("", description="商店卡片上顯示的說明")
    kind: str = Field("url", description='"url"(streamable-http/sse) 或 "stdio"(本機指令)')
    transport: str | None = Field(None, description="kind=url 時的傳輸協定，例如 streamable-http/sse")
    url: str | None = Field(None, description="kind=url 時的連線網址")
    command: str | None = Field(None, description="kind=stdio 時的執行指令，例如 npx")
    args: list[str] = Field(default_factory=list, description="kind=stdio 時的指令參數")
    credentialFields: list[dict] = Field(default_factory=list, description='[{"key","label","type","required"}]')


def _verify_admin_token(x_admin_token: str | None):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="管理員 token 錯誤或缺少 X-Admin-Token 標頭")


@app.get("/api/admin/mcp/catalog", status_code=status.HTTP_200_OK)
async def admin_get_mcp_catalog(x_admin_token: str | None = Header(None)):
    _verify_admin_token(x_admin_token)
    catalog = await asyncio.to_thread(mcp_services.load_master_catalog)
    return {"status": "success", "mcpServers": catalog}


@app.post("/api/admin/mcp/catalog", status_code=status.HTTP_200_OK)
async def admin_upsert_mcp_catalog_entry(payload: McpCatalogEntryPayload, x_admin_token: str | None = Header(None)):
    _verify_admin_token(x_admin_token)
    entry = payload.model_dump(exclude={"name"}, exclude_none=True)
    result = await asyncio.to_thread(mcp_services.upsert_master_catalog_entry, payload.name, entry)
    return {"status": "success", "entry": result}


@app.delete("/api/admin/mcp/catalog/{name}", status_code=status.HTTP_200_OK)
async def admin_delete_mcp_catalog_entry(name: str, x_admin_token: str | None = Header(None)):
    _verify_admin_token(x_admin_token)
    removed = await asyncio.to_thread(mcp_services.delete_master_catalog_entry, name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"母版裡沒有這個 MCP: {name}")
    return {"status": "success", "removed": True}


# 🆕 0717：Skill 版本的精選清單管理，跟 MCP 母版同一套 token 防護，欄位少很多
# （不需要 kind/url/command/credentialFields，因為一律走 hermes skills install <identifier>）
class SkillCatalogEntryPayload(BaseModel):
    key: str = Field(..., description="識別碼，同時也是精選清單的 key")
    identifier: str = Field(..., description="hermes 技能市集的真實 identifier，例如 official/finance/excel-author")
    displayName: str = Field(..., description="商店卡片上顯示的名稱")
    description: str = Field("", description="商店卡片上顯示的說明")


@app.get("/api/admin/skills/catalog", status_code=status.HTTP_200_OK)
async def admin_get_skills_catalog(x_admin_token: str | None = Header(None)):
    _verify_admin_token(x_admin_token)
    catalog = await asyncio.to_thread(skills_catalog.load_master_catalog)
    return {"status": "success", "skills": catalog}


@app.post("/api/admin/skills/catalog", status_code=status.HTTP_200_OK)
async def admin_upsert_skills_catalog_entry(payload: SkillCatalogEntryPayload, x_admin_token: str | None = Header(None)):
    _verify_admin_token(x_admin_token)
    entry = payload.model_dump(exclude={"key"})
    result = await asyncio.to_thread(skills_catalog.upsert_master_catalog_entry, payload.key, entry)
    return {"status": "success", "entry": result}


@app.delete("/api/admin/skills/catalog/{key}", status_code=status.HTTP_200_OK)
async def admin_delete_skills_catalog_entry(key: str, x_admin_token: str | None = Header(None)):
    _verify_admin_token(x_admin_token)
    removed = await asyncio.to_thread(skills_catalog.delete_master_catalog_entry, key)
    if not removed:
        raise HTTPException(status_code=404, detail=f"精選清單裡沒有這個技能: {key}")
    return {"status": "success", "removed": True}


_ADMIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<title>MCP 母版管理後台</title>
<style>
  body { font-family: -apple-system, "Microsoft JhengHei", sans-serif; background: #f8fcff; color: #0c4a6e; padding: 24px; max-width: 900px; margin: 0 auto; }
  h1 { font-size: 20px; }
  .token-bar { display: flex; gap: 8px; margin-bottom: 20px; }
  input, textarea, select { border: 1px solid #bae6fd; border-radius: 8px; padding: 6px 10px; font-size: 13px; }
  input[type=text], textarea { width: 100%; box-sizing: border-box; }
  button { background: #0ea5e9; color: white; border: none; border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px; }
  button.danger { background: #dc2626; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  th, td { border: 1px solid #e0f2fe; padding: 8px; font-size: 12px; text-align: left; vertical-align: top; }
  th { background: #f0f9ff; }
  form { background: white; border: 1px solid #e0f2fe; border-radius: 12px; padding: 16px; margin-top: 20px; display: grid; gap: 10px; }
  form label { font-size: 12px; font-weight: 700; display: block; margin-bottom: 2px; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  #msg { font-size: 12px; margin-top: 8px; }
</style>
</head>
<body>
<h1>🗂️ MCP 母版管理後台</h1>
<p style="font-size:12px;color:#64748b">這裡編輯的是全平台共用的母版目錄，改完使用者下次進 MCP 商店就會看到最新內容。</p>

<div class="token-bar">
  <input type="text" id="token" placeholder="管理員 Token" style="flex:1" />
  <button onclick="saveToken()">儲存 Token</button>
  <button onclick="loadCatalog()">重新整理清單</button>
</div>

<table id="catalogTable">
  <thead><tr><th>名稱</th><th>顯示名稱</th><th>種類</th><th>連線資訊</th><th>憑證欄位</th><th></th></tr></thead>
  <tbody></tbody>
</table>

<h1 style="margin-top:40px">🎯 Skill 精選清單管理</h1>
<p style="font-size:12px;color:#64748b">建立新 agent 時可以直接勾選安裝的技能起手式。技能有沒有生效 hermes 自己純掃資料夾判斷，
這裡的清單只是「哪些技能值得推薦給剛建立的新 agent」，不影響其他已經裝過的技能。</p>

<button onclick="loadSkillCatalog()">重新整理技能清單</button>
<table id="skillCatalogTable">
  <thead><tr><th>Key</th><th>顯示名稱</th><th>Identifier</th><th>說明</th><th></th></tr></thead>
  <tbody></tbody>
</table>

<form onsubmit="return submitSkillEntry(event)">
  <h3 style="margin:0">新增 / 編輯一筆精選技能</h3>
  <div class="row">
    <div><label>Key（新增後建議不要再改）</label><input type="text" id="sf_key" required /></div>
    <div><label>顯示名稱</label><input type="text" id="sf_displayName" required /></div>
  </div>
  <div><label>Identifier（來自 hermes skills search --json 的真實結果，不要憑空亂填）</label>
    <input type="text" id="sf_identifier" placeholder="official/finance/excel-author" required /></div>
  <div><label>說明</label><textarea id="sf_description" rows="2"></textarea></div>
  <button type="submit">💾 儲存這筆技能</button>
  <div id="skillMsg" style="font-size:12px;margin-top:8px"></div>
</form>

<form onsubmit="return submitEntry(event)">
  <h3 style="margin:0">新增 / 編輯一筆 MCP</h3>
  <div class="row">
    <div><label>名稱（key，新增後建議不要再改）</label><input type="text" id="f_name" required /></div>
    <div><label>顯示名稱</label><input type="text" id="f_displayName" required /></div>
  </div>
  <div><label>說明</label><textarea id="f_description" rows="2"></textarea></div>
  <div class="row">
    <div><label>種類</label>
      <select id="f_kind" onchange="toggleKindFields()">
        <option value="url">url（streamable-http / sse）</option>
        <option value="stdio">stdio（本機指令，如 npx）</option>
      </select>
    </div>
    <div id="f_transport_wrap"><label>transport</label><input type="text" id="f_transport" placeholder="streamable-http 或 sse" /></div>
  </div>
  <div id="url_fields">
    <label>URL</label><input type="text" id="f_url" placeholder="http://..." />
  </div>
  <div id="stdio_fields" style="display:none">
    <div class="row">
      <div><label>指令</label><input type="text" id="f_command" placeholder="npx" /></div>
      <div><label>參數（逗號分隔）</label><input type="text" id="f_args" placeholder="-y,@scope/pkg-name" /></div>
    </div>
  </div>
  <div>
    <label>憑證欄位（每行一個，格式：key,顯示名稱,text或password,是否必填true/false）</label>
    <textarea id="f_credentialFields" rows="3" placeholder="USER,帳號,text,true&#10;PASSWORD,密碼,password,true"></textarea>
  </div>
  <button type="submit">💾 儲存這筆 MCP</button>
  <div id="msg"></div>
</form>

<script>
function getToken() { return localStorage.getItem('mcp_admin_token') || ''; }
function saveToken() { localStorage.setItem('mcp_admin_token', document.getElementById('token').value.trim()); loadCatalog(); loadSkillCatalog(); }

function toggleKindFields() {
  const isStdio = document.getElementById('f_kind').value === 'stdio';
  document.getElementById('url_fields').style.display = isStdio ? 'none' : 'block';
  document.getElementById('f_transport_wrap').style.display = isStdio ? 'none' : 'block';
  document.getElementById('stdio_fields').style.display = isStdio ? 'block' : 'none';
}

function parseCredentialFields(text) {
  return text.split('\\n').map(l => l.trim()).filter(Boolean).map(line => {
    const [key, label, type, required] = line.split(',').map(s => (s || '').trim());
    return { key, label: label || key, type: type || 'text', required: required === 'true' };
  });
}

async function loadCatalog() {
  const res = await fetch('/api/admin/mcp/catalog', { headers: { 'X-Admin-Token': getToken() } });
  const tbody = document.querySelector('#catalogTable tbody');
  tbody.innerHTML = '';
  if (!res.ok) {
    document.getElementById('msg').textContent = 'Token 錯誤或尚未設定（' + res.status + '）';
    return;
  }
  const data = await res.json();
  for (const [name, entry] of Object.entries(data.mcpServers || {})) {
    const tr = document.createElement('tr');
    const connInfo = entry.kind === 'stdio' ? (entry.command + ' ' + (entry.args || []).join(' ')) : entry.url;
    const credText = (entry.credentialFields || []).map(f => f.key).join(', ') || '（無需憑證）';
    tr.innerHTML = `<td>${name}</td><td>${entry.displayName || ''}</td><td>${entry.kind}</td>
      <td style="word-break:break-all">${connInfo || ''}</td><td>${credText}</td>
      <td><button class="danger" onclick="deleteEntry('${name}')">刪除</button></td>`;
    tbody.appendChild(tr);
  }
}

async function deleteEntry(name) {
  if (!confirm('確定要從母版移除「' + name + '」嗎？既有 agent 已經裝過的不會被移除，只是商店不再顯示。')) return;
  const res = await fetch('/api/admin/mcp/catalog/' + encodeURIComponent(name), {
    method: 'DELETE', headers: { 'X-Admin-Token': getToken() }
  });
  document.getElementById('msg').textContent = res.ok ? '已刪除' : '刪除失敗';
  loadCatalog();
}

async function submitEntry(e) {
  e.preventDefault();
  const kind = document.getElementById('f_kind').value;
  const payload = {
    name: document.getElementById('f_name').value.trim(),
    displayName: document.getElementById('f_displayName').value.trim(),
    description: document.getElementById('f_description').value.trim(),
    kind,
    credentialFields: parseCredentialFields(document.getElementById('f_credentialFields').value)
  };
  if (kind === 'stdio') {
    payload.command = document.getElementById('f_command').value.trim();
    payload.args = document.getElementById('f_args').value.split(',').map(s => s.trim()).filter(Boolean);
  } else {
    payload.transport = document.getElementById('f_transport').value.trim();
    payload.url = document.getElementById('f_url').value.trim();
  }
  const res = await fetch('/api/admin/mcp/catalog', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Admin-Token': getToken() },
    body: JSON.stringify(payload)
  });
  document.getElementById('msg').textContent = res.ok ? '✅ 已儲存' : '❌ 儲存失敗（' + res.status + '）';
  if (res.ok) loadCatalog();
  return false;
}

async function loadSkillCatalog() {
  const res = await fetch('/api/admin/skills/catalog', { headers: { 'X-Admin-Token': getToken() } });
  const tbody = document.querySelector('#skillCatalogTable tbody');
  tbody.innerHTML = '';
  if (!res.ok) {
    document.getElementById('skillMsg').textContent = 'Token 錯誤或尚未設定（' + res.status + '）';
    return;
  }
  const data = await res.json();
  for (const [key, entry] of Object.entries(data.skills || {})) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${key}</td><td>${entry.displayName || ''}</td>
      <td style="word-break:break-all">${entry.identifier || ''}</td><td>${entry.description || ''}</td>
      <td><button class="danger" onclick="deleteSkillEntry('${key}')">刪除</button></td>`;
    tbody.appendChild(tr);
  }
}

async function deleteSkillEntry(key) {
  if (!confirm('確定要從精選清單移除「' + key + '」嗎？既有 agent 已經裝過的不會被移除，只是建立新 agent 時不再推薦。')) return;
  const res = await fetch('/api/admin/skills/catalog/' + encodeURIComponent(key), {
    method: 'DELETE', headers: { 'X-Admin-Token': getToken() }
  });
  document.getElementById('skillMsg').textContent = res.ok ? '已刪除' : '刪除失敗';
  loadSkillCatalog();
}

async function submitSkillEntry(e) {
  e.preventDefault();
  const payload = {
    key: document.getElementById('sf_key').value.trim(),
    displayName: document.getElementById('sf_displayName').value.trim(),
    identifier: document.getElementById('sf_identifier').value.trim(),
    description: document.getElementById('sf_description').value.trim()
  };
  const res = await fetch('/api/admin/skills/catalog', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Admin-Token': getToken() },
    body: JSON.stringify(payload)
  });
  document.getElementById('skillMsg').textContent = res.ok ? '✅ 已儲存' : '❌ 儲存失敗（' + res.status + '）';
  if (res.ok) loadSkillCatalog();
  return false;
}

document.getElementById('token').value = getToken();
loadCatalog();
loadSkillCatalog();
</script>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return HTMLResponse(content=_ADMIN_PAGE_HTML)
