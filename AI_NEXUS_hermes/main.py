"""
AI_NEXUS_hermes：從 hermes-agent 拆出來的「hermes config + hermes 操作 + docker ensure」
核心，給其他團隊（各自的前端/後端）串接用。範圍（跟使用者確認過）：

- ✅ 這支服務負責：hermes config.yaml/mcp_servers 產生、ACP 對話執行、每個帳號一個
  容器的 ensure/建立邏輯（runtime_manager.py）。
- ❌ 不負責：容器實際存在哪台機器、docker.sock/volume 怎麼掛進來——那是部署這支服務
  的人決定的基礎設施，不是這支程式碼管的。
- ❌ 不負責：前端、後端、資料庫。

跟正式 hermes-agent 一模一樣的兩段式呼叫模式（已在正式系統驗證過，不是新設計）：
  1. 對接的後端呼叫一次 POST /api/session/ensure {user_id}
     → 這支服務（此時扮演「入口」角色）ensure/建立該使用者專屬的容器、
       呼叫該容器自己的 /api/agent/prepare 把 config.yaml 等檔案先寫好，
       回傳該容器的 base_url。
  2. 之後每一輪對話，對接的後端直接打 base_url 的 /api/agent/chat/stream，
     不再經過步驟 1 打的那個入口——所有容器跑的是同一份程式碼，只是這次被
     直接定址到，扮演「這個使用者專屬的 runtime」角色。
"""
import os
import json
import asyncio

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import requests
import uvicorn

from config import logger, ChatRequest, PROFILES_BASE_DIR
import services
import acp_client
import mcp_services
import runtime_manager
import orchestrator_client

TAGS_METADATA = [
    {
        "name": "① 建立/Ensure（入口角色，需要 docker.sock）",
        "description": "使用者登入後呼叫一次：check/建立該使用者專屬的 hermes 容器，"
                       "並把設定檔案先寫好。之後不用再打這裡，直接用回傳的 base_url。",
    },
    {
        "name": "② 聊天 Chat（每個使用者的 runtime 角色）",
        "description": "實際對話跟提前準備設定檔。正式串接時，別人的前端/後端是直接打"
                       "「①」回傳的 base_url 底下的這些端點，不會再經過「①」。",
    },
    {
        "name": "③ MCP 專家路由設定",
        "description": "管理這個 agent 有哪些 MCP 工具可用（例如 phison-ainexus 動態專家路由），"
                       "設為 resident 才會真的出現在 config.yaml 給 hermes 用。",
    },
    {
        "name": "④ 使用者管理 User CRUD（入口角色，需要 docker.sock）",
        "description": "查詢/刪除使用者專屬容器。Create 就是「①」的 /api/session/ensure"
                       "（這裡額外提供 REST 風格的 POST /api/users 當別名，效果一樣）。",
    },
    {
        "name": "系統",
        "description": "健康檢查、服務資訊，不屬於業務邏輯。",
    },
]

app = FastAPI(
    title="AI_NEXUS Hermes Core",
    version="1.0.0",
    description="hermes config 產生 + ACP 對話執行 + 一帳號一容器 ensure 邏輯。"
                 "端點依「① 建立→② 聊天→③ MCP 設定」的順序分類，照順序測就對了。",
    openapi_tags=TAGS_METADATA,
    # 📍 Swagger UI 外觀在這裡調：預設全部收合（不然一開頁面落落長很醜）、
    # 加搜尋框、程式碼區塊用深色語法高亮，都是 Swagger 內建支援，不用額外裝套件。
    swagger_ui_parameters={
        "docExpansion": "none",
        "defaultModelsExpandDepth": -1,
        "displayRequestDuration": True,
        "filter": True,
        "syntaxHighlight.theme": "obsidian",
        "tryItOutEnabled": True,
    },
)

room_locks: dict[str, asyncio.Lock] = {}


@app.get("/", tags=["系統"], summary="服務資訊")
async def root():
    return {"service": "AI_NEXUS Hermes Core", "status": "running", "profiles_base_dir": PROFILES_BASE_DIR}


@app.get("/health", tags=["系統"], summary="健康檢查")
async def health():
    """
    檔案系統寫入失敗一律回 503（這是硬依賴，任何角色都需要）。docker.sock/orchestrator
    只在「這個實例被當作 ensure 入口用」時才需要，所以連不到只降級成 warning，不讓
    整支服務被判定不健康——純粹當「這個使用者專屬 runtime」的實例本來就不需要。
    """
    result = {"status": "healthy", "profiles_base_dir": PROFILES_BASE_DIR}
    try:
        os.makedirs(PROFILES_BASE_DIR, exist_ok=True)
        probe = os.path.join(PROFILES_BASE_DIR, ".health_probe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"無法寫入 PROFILES_BASE_DIR: {str(e)}")

    if orchestrator_client.is_enabled():
        result["container_backend"] = f"orchestrator ({orchestrator_client.ORCHESTRATOR_URL})"
    else:
        try:
            client = runtime_manager._get_docker_client()
            client.ping()
            result["container_backend"] = "docker.sock (connected)"
        except Exception as e:
            result["container_backend"] = f"docker.sock (unavailable: {str(e)})"

    return result


def _translate_acp_event_to_sse(event) -> str | None:
    """跟 hermes-agent/main.py 的 _translate_acp_event_to_sse 同一套邏輯（已驗證格式）。"""
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
        return None

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
    return None


class PrepareAgentPayload(BaseModel):
    agent_id: str = Field("agent_default", description="測試先給預設值，正式串接請自行指定")
    system_prompt: str | None = Field(None, description="留空用系統預設的通用助理人設")
    model: str | None = None
    llm_api_key: str | None = Field(None, description="這個使用者自己的模型 API key，留空用系統預設共用 key")

    model_config = {
        "json_schema_extra": {
            "example": {"agent_id": "agent_default", "system_prompt": None, "model": None, "llm_api_key": None}
        }
    }


@app.post("/api/agent/prepare", tags=["② 聊天 Chat"], summary="提前寫好 config.yaml/SOUL.md（不用等第一句聊天）")
async def prepare_agent(payload: PrepareAgentPayload):
    """
    在「這個容器」本地把 config.yaml/SOUL.md/mcp_servers 先寫好，不用等第一句聊天
    才觸發——/api/session/ensure 建好容器後會呼叫這支端點，也可以單獨呼叫來重寫設定
    （例如換了 approvals/mcp 選擇後想立刻生效，不用等下一輪對話自然觸發）。
    """
    agent_dir = await services.ensure_hermes_profile_exists(
        payload.agent_id, payload.system_prompt, model=payload.model, llm_api_key=payload.llm_api_key
    )
    return {"status": "success", "agent_id": payload.agent_id, "agent_dir": agent_dir}


class EnsureSessionPayload(BaseModel):
    user_id: str = Field(..., description="外部系統的使用者 ID（模擬登入後拿到的那個 ID）")
    system_prompt: str | None = Field(None, description="留空用系統預設的通用助理人設")
    model: str | None = None
    llm_api_key: str | None = Field(None, description="這個使用者自己的模型 API key，留空用系統預設共用 key")
    phison_token: str | None = Field(
        None,
        description="有提供的話，順便幫這個使用者把 phison-ainexus 設好憑證。"
                     "這個 token 會過期/浮動，之後每輪聊天也可以用 ChatRequest.phison_token 帶新的覆寫，不用只能在這裡設一次。",
    )

    model_config = {
        "json_schema_extra": {
            "example": {"user_id": "demo001", "system_prompt": None, "model": None, "llm_api_key": None, "phison_token": None}
        }
    }


async def _ensure_session_impl(payload: EnsureSessionPayload) -> dict:
    """實際邏輯抽出來，讓 /api/session/ensure 和 /api/users（Create）共用同一套，不重複寫。"""
    agent_id = f"user_{payload.user_id}"  # 1 帳號 1 hermes 的預設對應；multi-agent 之後要拓展，換成接受多個 agent_id 即可

    try:
        runtime = await asyncio.to_thread(runtime_manager.ensure_user_runtime, payload.user_id)
    except Exception as e:
        logger.error(f"❌ [Session Ensure] 使用者 {payload.user_id} 的容器 ensure 失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"容器 ensure 失敗: {str(e)}")

    base_url = runtime["base_url"]

    try:
        prep_resp = requests.post(
            f"{base_url}/api/agent/prepare",
            json={
                "agent_id": agent_id, "system_prompt": payload.system_prompt,
                "model": payload.model, "llm_api_key": payload.llm_api_key,
            },
            timeout=15,
        )
        prep_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"容器已建立但設定檔寫入失敗: {str(e)}")

    try:
        requests.post(
            f"{base_url}/api/agent/{agent_id}/mcp/phison-ainexus/selection",
            json={"selection": "resident"}, timeout=10,
        )
        if payload.phison_token:
            requests.post(
                f"{base_url}/api/agent/{agent_id}/mcp/phison-ainexus/credentials",
                json={"credentials": {"PHISON_TOKEN": payload.phison_token}}, timeout=10,
            )
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ [Session Ensure] 預設 MCP 設定失敗（不影響基本聊天）: {str(e)}")

    response = {
        "status": runtime["status"],
        "user_id": payload.user_id,
        "agent_id": agent_id,
        "base_url": base_url,
        "chat_endpoint": f"{base_url}/api/agent/chat/stream",
    }
    if "swagger_url" in runtime:
        response["swagger_url"] = runtime["swagger_url"]
    return response


@app.post("/api/session/ensure", tags=["① 建立/Ensure（入口角色，需要 docker.sock）"], summary="登入後呼叫一次：ensure 容器 + 提前寫好設定")
async def ensure_session(payload: EnsureSessionPayload):
    """
    使用者登入後、開始第一句對話前呼叫一次。做三件事：
      1. ensure 這個 user_id 專屬的容器存在（不存在就建立，冪等，重複呼叫不重建）
      2. 呼叫該容器自己的 /api/agent/prepare，把 config.yaml 等檔案先寫好
      3. 預設把 phison-ainexus（AINexus 專家路由）設成 resident——不用多 agent，
         先給一個固定 default，行為對齊「幫我看出勤」這類問題會自動走專家路由。

    回傳的 base_url 是給對接後端之後直接打 /api/agent/chat/stream 用的，
    不用再回頭呼叫這支 ensure 端點。
    """
    return await _ensure_session_impl(payload)


# =====================================================================
# 使用者 CRUD：讓你能控制使用者的建立/查詢/刪除，不用每次都繞去看 docker ps。
# Create 直接復用 _ensure_session_impl；這裡新增的是 Read（列表/單筆）跟 Delete。
# =====================================================================

@app.get("/api/users", tags=["④ 使用者管理 User CRUD（入口角色，需要 docker.sock）"], summary="列出所有使用者（Read）")
async def list_users():
    users = await asyncio.to_thread(runtime_manager.list_user_runtimes)
    return {"status": "success", "count": len(users), "users": users}


@app.get("/api/users/{user_id}", tags=["④ 使用者管理 User CRUD（入口角色，需要 docker.sock）"], summary="查詢單一使用者狀態（Read）")
async def get_user(user_id: str):
    info = await asyncio.to_thread(runtime_manager.get_user_runtime, user_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"找不到使用者 {user_id}")
    return {"status": "success", **info}


@app.post("/api/users", tags=["④ 使用者管理 User CRUD（入口角色，需要 docker.sock）"], summary="建立使用者（Create，等同 /api/session/ensure）")
async def create_user(payload: EnsureSessionPayload):
    return await _ensure_session_impl(payload)


@app.delete("/api/users/{user_id}", tags=["④ 使用者管理 User CRUD（入口角色，需要 docker.sock）"], summary="刪除使用者（Delete，停止並移除容器）")
async def delete_user(user_id: str, wipe_data: bool = False):
    """
    預設只刪容器，不刪資料（wipe_data=false）——這樣之後同一個 user_id 再 ensure 一次，
    設定/記憶都還在，只是重開一個新容器。要連資料夾一起刪乾淨才把 wipe_data 設 true。
    """
    deleted = await asyncio.to_thread(runtime_manager.delete_user_runtime, user_id, wipe_data)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"找不到使用者 {user_id}")
    return {"status": "success", "user_id": user_id, "wiped_data": wipe_data}


@app.post("/api/agent/chat/stream", tags=["② 聊天 Chat"], summary="核心對話端點（實際跟 hermes 聊天）")
async def agent_chat_stream(payload: ChatRequest):
    # user_id 有帶就用它換算出跟 /api/session/ensure 一致的 agent_id，不用自己組字串。
    agent_id = payload.effective_agent_id()

    # phison_token 是浮動/會過期的東西，設計成每輪都可以帶新的覆寫（不是只能在
    # /api/session/ensure 那次設定），這裡先寫進 .env，下面 ensure_hermes_profile_exists
    # 重寫 config.yaml 時引用的 ${MCP_...} 變數名稱不變，實際值就是這裡寫進去的最新值。
    if payload.phison_token:
        await services.set_phison_token(agent_id, payload.phison_token)

    agent_dir = await services.ensure_hermes_profile_exists(
        agent_id, payload.system_prompt, model=payload.model, llm_api_key=payload.llm_api_key
    )

    current_env = os.environ.copy()
    current_env.update({
        "HERMES_HOME": agent_dir,
        "PYTHONUNBUFFERED": "1",
        "HERMES_MEMORY_PLUGIN_PATH": "built-in",
        "HERMES_BUILTIN_PLUGIN_FORCE": "true",
        "HERMES_MEMORY_PROVIDER": "built-in",
        "OPENAI_API_KEY": payload.llm_api_key or os.getenv("PHISON_API_KEY", ""),
        "HERMES_API_KEY": payload.llm_api_key or os.getenv("PHISON_API_KEY", ""),
        "OPENAI_BASE_URL": os.getenv("LLM_BASE_URL", "https://ainexus.phison.com/api/external/v1"),
        "HERMES_BASE_URL": os.getenv("LLM_BASE_URL", "https://ainexus.phison.com/api/external/v1"),
        "HERMES_MODEL_BASE_URL": os.getenv("LLM_BASE_URL", "https://ainexus.phison.com/api/external/v1"),
        # LLM_PROVIDER=native 測試模式（今晚用 Claude 代替 Phison）才需要這個 key，
        # 沒設定 ANTHROPIC_API_KEY 就不會加，不影響走 Phison custom 端點的正式路徑
        **({"ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"]} if os.getenv("ANTHROPIC_API_KEY") else {}),
    })

    room_str = str(payload.room_id).strip()
    if room_str not in room_locks:
        room_locks[room_str] = asyncio.Lock()

    raw_session = await services.load_native_session_id(agent_dir, room_str)
    resume_session_id = None
    if raw_session:
        cleaned = raw_session.strip()
        if cleaned and cleaned.lower() != "none":
            resume_session_id = cleaned

    if not resume_session_id and room_locks[room_str].locked():
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Hermes 正在思考中，請稍候。")

    async def acp_stream_generator():
        async with room_locks[room_str]:
            try:
                async for event in acp_client.run_acp_turn(agent_dir, room_str, payload.message, current_env, resume_session_id):
                    if isinstance(event, dict) and event.get("__acp_turn_complete__"):
                        await services.save_native_session_id(agent_dir, room_str, event["session_id"])
                        continue
                    sse_chunk = _translate_acp_event_to_sse(event)
                    if sse_chunk:
                        yield sse_chunk
            except Exception as e:
                logger.error(f"❌ ACP 串流進程發生異常: {str(e)}")
                yield f"\n⚠️ 系統暫時無法連線到 AI 模型，請稍後再試一次。\n"

    return StreamingResponse(acp_stream_generator(), media_type="text/plain")


@app.post("/api/agent/approve-write", tags=["② 聊天 Chat"], summary="核准 hermes 觸發的危險操作請求")
async def approve_write(room_id: str, option_id: str):
    ok = acp_client.submit_permission_decision(room_id, option_id)
    if not ok:
        raise HTTPException(status_code=404, detail="沒有正在等待核准的請求")
    return {"status": "success"}


# =====================================================================
# MCP 商店最小端點：跟 hermes-agent/main.py 的 /api/agent/{id}/mcp/* 同一套邏輯，
# 沒有這幾支端點就沒有任何方式能把 phison-ainexus（或任何 MCP）設成 resident。
# =====================================================================

class McpSelectionPayload(BaseModel):
    selection: str | None = Field(None, description='null（移除）/ "resident" / "optional_installed"')


class McpCredentialsPayload(BaseModel):
    credentials: dict[str, str] = Field(..., description="{field_key: value}，例如 {'PHISON_TOKEN': '...'}")


@app.get("/api/mcp/catalog", tags=["③ MCP 專家路由設定"], summary="母版 MCP 目錄（所有可用的工具清單）")
async def get_mcp_master_catalog():
    catalog = await asyncio.to_thread(mcp_services.load_master_catalog)
    return {"status": "success", "mcpServers": catalog}


@app.get("/api/agent/{agent_id}/mcp", tags=["③ MCP 專家路由設定"], summary="這個 agent 目前的 MCP 選擇狀態")
async def get_agent_mcp_state(agent_id: str):
    servers = await asyncio.to_thread(mcp_services.get_agent_mcp_state, agent_id)
    return {"status": "success", "servers": servers}


@app.post("/api/agent/{agent_id}/mcp/{mcp_name}/selection", tags=["③ MCP 專家路由設定"], summary="設為 resident/optional/移除")
async def set_agent_mcp_selection(agent_id: str, mcp_name: str, payload: McpSelectionPayload):
    try:
        entry = await asyncio.to_thread(mcp_services.set_agent_mcp_selection, agent_id, mcp_name, payload.selection)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "entry": entry}


@app.post("/api/agent/{agent_id}/mcp/{mcp_name}/credentials", tags=["③ MCP 專家路由設定"], summary="填入憑證（如 PHISON_TOKEN）")
async def set_agent_mcp_credentials(agent_id: str, mcp_name: str, payload: McpCredentialsPayload):
    try:
        entry = await asyncio.to_thread(mcp_services.set_agent_mcp_credentials, agent_id, mcp_name, payload.credentials)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "success", "entry": entry}


def main():
    uvicorn.run(app, host="0.0.0.0", port=8643, log_level="info")


if __name__ == "__main__":
    main()
