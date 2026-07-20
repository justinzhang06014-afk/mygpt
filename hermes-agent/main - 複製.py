import os
import re
import json
import logging
import asyncio
import yaml  # 💡 補齊缺失的 yaml 套件，避免寫入 config 錯誤
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# =====================================================================
# 初始化高防禦性企業級日誌系統
# =====================================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("hermes-proxy")

# 官方全域配置根目錄（預設為 ~/.hermes）
GLOBAL_HERMES_DIR = os.path.expanduser("~/.hermes")
# 優化環境變數讀取邏輯，避免重複賦值與覆蓋
PROFILES_BASE_DIR = os.getenv("PROFILES_BASE_DIR", os.path.expanduser("~/.hermes/profiles"))

app = FastAPI(
    title="Hermes Native Multi-Agent Proxy", 
    version="3.0.0",
    description="高防禦性、純異步非阻塞、相容 Hermes 官方記憶落地架構的後端代理"
)

class ChatRequest(BaseModel):
    agent_id: str = Field(..., description="唯一的 Agent ID (對應官方 Profile 名稱)")
    room_id: str = Field(..., description="聊天房間 ID (對應官方 Session ID)")
    system_prompt: str = Field(..., description="Agent 的系統提示詞 (SOUL)")
    message: str = Field(..., description="用戶輸入的原始訊息")


# =====================================================================
# Profile 與全域記憶插件自動防禦自癒核心 (第一部分)
# =====================================================================
async def ensure_hermes_profile_exists(agent_id: str, system_prompt: str) -> str:
    """判斷 Agent 是否創立，並在聊天啟動前，強行確保全域記憶體插件經由 Python 安裝完成"""
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    
    init_env = os.environ.copy()
    init_env["HERMES_HOME"] = agent_dir
    
    PHISON_LLM_KEY = os.getenv("PHISON_API_KEY", "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249")
    init_env["OPENAI_API_KEY"] = PHISON_LLM_KEY
    init_env["HERMES_API_KEY"] = PHISON_LLM_KEY

        # 🔥【二進位解耦終極修正】不再依賴 Python find_spec，改用官方二進位工具原地安全修復
        # 🔥【解除環境污染終極修正】剝離 HERMES_HOME，強行逼迫官方 CLI 寫入全域 ~/.hermes/plugins/
    async def _cli_plugin_install():
        from pathlib import Path
        
        global_plugins_dir = Path.home() / ".hermes" / "plugins"
        target_builtin_dir = global_plugins_dir / "builtin"
        
        # 🛡️ 最高原則綠燈放行
        if target_builtin_dir.exists() and (target_builtin_dir / "plugin.yaml").exists():
            logger.info("💚 [Plugin Verified] 全域 built-in 記憶體插件已確認存在，綠燈放行。")
            return
        
        logger.warning("⚠️ [Plugin Missing] 偵測到全域 built-in 記憶體核心缺失！啟動官方二進位原生安裝管線...")
        
        # 💡 關鍵修正：建立一個完全沒有 HERMES_HOME 的乾淨環境變數，確保它裝到全域
        global_env = os.environ.copy()
        global_env["OPENAI_API_KEY"] = PHISON_LLM_KEY
        global_env["HERMES_API_KEY"] = PHISON_LLM_KEY
        if "HERMES_HOME" in global_env:
            del global_env["HERMES_HOME"]
        
        # 🟢 第一防線
        install_proc = await asyncio.create_subprocess_exec(
            "hermes", "plugins", "install", "built-in", env=global_env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await install_proc.communicate()
        
        if install_proc.returncode == 0:
            logger.info(f"✅ [Plugin Repaired] built-in 記憶體插件已透過官方 CLI 工具安全部署完成：{target_builtin_dir}")
        else:
            # 🟡 第二防線
            logger.info(f"🔄 [Plugin Retry] 標準安裝失敗，切換至備用 setup 指令...")
            setup_proc = await asyncio.create_subprocess_exec(
                "hermes", "memory", "setup", "built-in", env=global_env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await setup_proc.communicate()
            
            if setup_proc.returncode == 0:
                logger.info(f"✅ [Plugin Repaired] built-in 記憶體插件已透過官方 setup 指令安全部署完成。")
            else:
                logger.error(f"❌ [Plugin Fatal] 官方二進位管線修復全部失敗。錯誤訊息: {stderr.decode('utf-8')}")

    # 呼叫脫離污染的安裝程序
    await _cli_plugin_install()


    # 1. 異步檢查 Profile 是否存在
    check_proc = await asyncio.create_subprocess_exec(
        "hermes", "profile", "show", agent_id, env=init_env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await check_proc.wait()
    
    # 2. 如果 Agent Profile 不存在，才執行官方創立命令
    if check_proc.returncode != 0:
        logger.info(f"🆕 檢測到新 Agent: {agent_id}，正在建立官方隔離 Profile...")
        create_proc = await asyncio.create_subprocess_exec(
            "hermes", "profile", "create", agent_id, "--description", f"Automated Agent {agent_id}",
            env=init_env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await create_proc.communicate()

    # 3. 每次進入皆安全隔離寫入 config.yaml
    def _write_isolated_config():
        os.makedirs(agent_dir, exist_ok=True)
        config_data = {
            "model": {
                "provider": "custom",
                "base_url": "https://ainexus.phison.com/api/external/v1",
                "api_key": PHISON_LLM_KEY,
                "default": os.getenv("LLM_MODEL", "Qwen/Qwen3.6-27B")
            },
            "memory": {
                "memory_enabled": True,
                "provider": "built-in",
                "user_profile_enabled": True,
                "write_approval": False,
                "auto_write": True,
                "nudge_interval": 1,
                "flush_min_turns": 1
            }
        }
        config_path = os.path.join(agent_dir, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f, default_flow_style=False)
            
    await asyncio.to_thread(_write_isolated_config)
    logger.info("💾 [Config Shield] 已成功部署滿血版內網 Embedding 記憶插件配置。")

    # 4. 異步寫入靈魂人設 (SOUL.md)
        # 4. 🔥【終極人設固化防線】融合自主記憶條款與自動統整沉澱演算法，寫入 SOUL.md
    soul_path = os.path.join(agent_dir, "SOUL.md")
    
    # 💡 誠如我們所說：直接將大腦沉澱機制固化在人設最底層，強制約束大模型行為
    extended_soul_prompt = f"""{system_prompt}

=====================================================================
【🧠 記憶體自主運行與大腦統整沉澱最高核心條款】
1. 自主記憶捕捉：你在後台擁有全自動的長期記憶大腦（MEMORY.md / USER.md）。在每輪對話中，只要用戶提及任何「個人事實、技術偏好、工作習慣、討厭或喜歡的事物」，你必須在背後「主動且神不知鬼不覺地」調用記憶工具（add/replace）將其儲存，絕對不要等待用戶命令。回答時，請默默執行，不要向用戶宣告「我已經記下來了」。

2. 記憶定期沉澱與濃縮（避免字數爆量）：
   - 你的長期記憶體以「高密度、精煉、不重複」為最高維護原則。
   - 當你要加入新Facts時，如果發現與過去已存在的舊記憶高度相關，禁止盲目追加新行！你必須主動調用工具的「replace」或「remove」动作，將舊事實與新進展「融合濃縮」成一條更精煉、更全面的陳述（例如：將「用戶在測試代碼」與「用戶部署了FastAPI」融合成「用戶成功將FastAPI代理部署上線並進行了全面調試」）。
   - 隨時保持 MEMORY.md 內的事實條目不超過 15-20 條。一旦超過，必須在後台發起大腦整合（Consolidation），刪除過期雜訊，只留下沉澱後的金字塔精華。
3. 你每次開始對話前都會先讀取你自己的memory.md
=====================================================================
"""

    def _write_soul():
        with open(soul_path, "w", encoding="utf-8") as f:
            f.write(extended_soul_prompt)
            
    await asyncio.to_thread(_write_soul)
    logger.info(f"🧬 [Soul Shield] 記憶自適應沉澱條款已成功固化至 Agent [{agent_id}] 的靈魂人設中。")
    
    return agent_dir





# =====================================================================
# 4. Session 映射管理（無阻塞執行緒池化）層
# =====================================================================
def _sync_load_session(mapping_path: str, room_id: str) -> str:
    """【內部私有同步函數】精確讀取本地對照表，僅供 ThreadPool 調用"""
    if not os.path.exists(mapping_path): return None
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            return str(json.load(f).get(str(room_id)))
    except Exception: return None

def _sync_save_session(mapping_path: str, room_id: str, native_id: str):
    """【內部私有同步函數】精確寫入本地對照表，僅供 ThreadPool 調用"""
    mapping = {}
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f: mapping = json.load(f)
        except Exception: mapping = {}
    mapping[str(room_id)] = str(native_id)
    try:
        os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
        with open(mapping_path, "w", encoding="utf-8") as f: json.dump(mapping, f, indent=4)
        logger.info(f"💾 [Mapping Link] 成功綁定外部房間 {room_id} -> Hermes 原生對話 ID: {native_id}")
    except Exception as e: logger.error(f"❌ 寫入 Session 映射表失敗: {str(e)}")

async def load_native_session_id(agent_dir: str, room_id: str) -> str:
    """從特定 Agent 目錄下的 JSON 異步查找歷史原生 Session ID"""
    return await asyncio.to_thread(_sync_load_session, os.path.join(agent_dir, "session_mapping.json"), room_id)

async def save_native_session_id(agent_dir: str, room_id: str, native_id: str):
    """將外部房間 ID 與 Hermes 原生 Session ID 異步強行綁定"""
    await asyncio.to_thread(_sync_save_session, os.path.join(agent_dir, "session_mapping.json"), room_id, native_id)

async def _fetch_native_sessions_set(current_env: dict) -> set:
    """非阻塞異步獲取當前隔離環境下的所有真實官方 Session ID 集合"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "hermes", "sessions", "list", env=current_env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            return set(re.compile(r"\d{8}_\d{6}_\w+").findall(stdout.decode("utf-8")))
    except Exception: pass
    return set()


# =====================================================================
# 全域冷啟動防護鎖字典（防禦前端逾時自動重試、雙發請求爆發）
# =====================================================================
room_locks = {}

# =====================================================================
# 5. 終極極速串流路由（環境變數雙重夾擊與 Hindsight 激活）
# =====================================================================
# =====================================================================
# 核心對話路由與控制流 API (第二部分)
# =====================================================================
room_locks = {}

@app.post("/api/agent/chat/stream")
async def agent_chat_stream(payload: ChatRequest):
    """
    【核心完全體】正統 Hermes CLI 異步中轉路由
    修正縮排截斷，並校正 Base URL 與內網 config.yaml 記憶體插件相容
    """
    # 呼叫第一部分的自癒與 Profile 檢查核心
    agent_dir = await ensure_hermes_profile_exists(payload.agent_id, payload.system_prompt)
    
    current_env = os.environ.copy()
    current_env["HERMES_HOME"] = agent_dir
    current_env["PYTHONUNBUFFERED"] = "1"
    current_env["HERMES_MEMORY_PLUGIN_PATH"] = "built-in" 
    current_env["HERMES_BUILTIN_PLUGIN_FORCE"] = "true"
    current_env["HERMES_MEMORY_PROVIDER"] = "built-in"  # 強制鎖定記憶體供應商

    # 🛡️ 憑證安全防線：與 Profile 建立階段的金鑰及內網模型端點完全對齊
    PHISON_LLM_KEY = os.getenv("PHISON_API_KEY", "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249")
    target_base_url = "https://ainexus.phison.com/api/external/v1"
    
    current_env["OPENAI_API_KEY"] = PHISON_LLM_KEY
    current_env["HERMES_API_KEY"] = PHISON_LLM_KEY
    current_env["OPENAI_BASE_URL"] = target_base_url
    current_env["HERMES_BASE_URL"] = target_base_url
    current_env["HERMES_MODEL_BASE_URL"] = target_base_url
    
    PHISON_EMBED_KEY = "AINX-64E91FF7CA1DAB07FE6F8537C5D2DBD396B4BAC1B89C8F3EA1EBC33B2B3ACCEA"
    current_env["HINDSIGHT_API_KEY"] = PHISON_EMBED_KEY
    current_env["HINDSIGHT_LLM_API_KEY"] = PHISON_EMBED_KEY
    
    room_str = str(payload.room_id).strip()
    target_model = os.getenv("LLM_MODEL", "Qwen/Qwen3.6-27B")

    # 💡 修正 1：正確縮排此處的 Lock 與對話續接判斷
    if room_str not in room_locks:
        room_locks[room_str] = asyncio.Lock()

    # 讀取歷史 Session 狀態
    native_session_id = await load_native_session_id(agent_dir, room_str)
    
    # 🛡️ 髒資料防禦洗滌：100% 確保將可能殘留的方括號字元安全抹除，還原成純字串
    if native_session_id:
        native_session_id = native_session_id.replace("[", "").replace("]", "").replace("'", "").replace('"', "").strip()
        
    session_exists = native_session_id is not None and len(native_session_id) > 0
    
    # 建立完全符合官方 Usage 語法的指令組，強行指定供應商與模型
    if session_exists:
        logger.info(f"🔄 [Room 續接] Agent: {payload.agent_id} | 房間: {payload.room_id} -> 續接 ID: {native_session_id}")
        hermes_args = [
            "hermes", 
            "--provider", "custom", 
            "-m", target_model, 
            "chat", 
            "-p", payload.agent_id, 
            "--resume", native_session_id,  
            "-q", payload.message
        ]
        pre_sessions = set()
    else:
        # 冷啟動防護：若該房間已被前端其他超時重試請求佔用，則直接高防禦攔截
        if room_locks[room_str].locked():
            logger.warning(f"⚠️ [防禦攔截] 檢測到房間 {room_str} 正在進行冷啟動推理中，拒絕前端自動重試的無效併發！")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="Hermes 正在努力思考與調用工具中，請耐心等待首字出字，勿重複提交。"
            )
            
        logger.info(f"✨ [Room 冷啟動] Agent: {payload.agent_id} | 房間: {payload.room_id}")
        pre_sessions = await _fetch_native_sessions_set(current_env)
        hermes_args = [
            "hermes", 
            "--provider", "custom", 
            "-m", target_model, 
            "--pass-session-id",          
            "chat", 
            "-p", payload.agent_id, 
            "-q", payload.message
        ]

    # 建立高防禦性非阻塞串流產生器
    async def cli_stream_generator():
        # 在產生器內部強行上鎖，對話完全結束、差集與記憶處理完後才釋放
        async with room_locks[room_str]:
            try:
                process = await asyncio.create_subprocess_exec(
                    *hermes_args, env=current_env,
                    stdin=asyncio.subprocess.PIPE, 
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.PIPE
                )
                if process.stdin: 
                    process.stdin.close() 

                # 清洗終端機控制雜訊，放行所有真實對話文本與搜尋精華
                strip_patterns = [
                    re.compile(r"╭─ ⚕ Hermes ─+╮"), 
                    re.compile(r"╰─+╯"), 
                    re.compile(r"⚡ preparing web…"), 
                    re.compile(r"💻 preparing terminal…"), 
                    re.compile(r"⏳ Retrying in.*")
                ]

                while True:
                    line_bytes = await process.stdout.readline()
                    if not line_bytes: 
                        break
                    line = line_bytes.decode("utf-8")
                    
                    if line.strip().startswith("$ curl") or "Goodbye!" in line or "Session:" in line: 
                        continue
                        
                    cleaned_line = line
                    for pattern in strip_patterns: 
                        cleaned_line = pattern.sub("", cleaned_line)
                        
                    if cleaned_line.strip() or line == "\n": 
                        yield cleaned_line

                await process.wait()
                
                # 6. 精確 Session 差集擷取與狀態回寫
                if process.returncode == 0:
                    if not session_exists:
                        post_sessions = await _fetch_native_sessions_set(current_env)
                        new_sessions = post_sessions - pre_sessions
                        if new_sessions:
                            # 🛡️ 核心防禦：轉為 list 後，精確取出第 0 個元素（字串真身）
                            exact_native_id = list(new_sessions)[0] 
                            await save_native_session_id(agent_dir, room_str, exact_native_id)
                            logger.info(f"✅ 成功精確捕捉單一 Session ID 字串: {exact_native_id}")
                        else:
                            logger.warning(f"⚠️ [Session 丟失] 未觀測到新生成的 Session ID 差集")

                    # 7. 💡 背景非阻塞實時大腦驗收（拉到獨立的背景任務中執行，讓 HTTP 串流立刻完結斷開）
                    async def _async_observe_log():
                        await asyncio.sleep(0.5)  # 留給硬碟快取喘息時間
                        status_proc = await asyncio.create_subprocess_exec(
                            "hermes", "memory", "status", 
                            env=current_env, 
                            stdout=asyncio.subprocess.PIPE
                        )
                        s_stdout, _ = await status_proc.communicate()
                        logger.info(f"\n📊 [背景實時大腦驗收] 目前 Agent [{payload.agent_id}] 記憶體狀態:\n{s_stdout.decode('utf-8').strip()}")
                    
                    asyncio.create_task(_async_observe_log())

            except Exception as e:
                logger.error(f"❌ Hermes 管線崩潰: {str(e)}")
                yield f"[ERROR: Process Failed - {str(e)}]"
            finally:
                # 釋放全域鎖字典中對應的 Key，防止記憶體洩漏
                if not session_exists and room_str in room_locks:
                    try: del room_locks[room_str]
                    except KeyError: pass

    return StreamingResponse(cli_stream_generator(), media_type="text/plain")





# =====================================================================
# 6. 安全抹除路由 (DELETE) 與全代碼安全收尾
# =====================================================================
@app.delete("/api/agent/{agent_id}")
async def delete_native_agent(agent_id: str):
    """
    完全調用官方原生銷毀命令，安全落盤並自動抹除該 Agent 目錄下所有的房間映射（完全異步化）
    """
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    current_env = os.environ.copy()
    current_env["HERMES_HOME"] = agent_dir
    
    # 注入金鑰，確保安全刪除命令在非互動式環境中 100% 成功執行
    target_api_key = "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249"
    current_env["OPENAI_API_KEY"] = target_api_key
    current_env["HERMES_API_KEY"] = target_api_key

    try:
        # 1. 呼叫官方安全抹除命令（非阻塞異步執行）
        delete_proc = await asyncio.create_subprocess_exec(
            "hermes", "profile", "delete", agent_id, "--yes", 
            env=current_env, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await delete_proc.communicate()
        
        if delete_proc.returncode != 0: 
            raise HTTPException(status_code=500, detail=stderr.decode("utf-8"))
        
        # 2. 💡【連帶清理防線】因為我們在 agent_dir 中建立了專屬的 session_mapping.json，
        # 雖然官方 profile delete 會清除設定，但為了極致的防禦性，我們在執行緒池中主動將殘留的資料夾全面安全抹除
        def _cleanup_residual_files():
            if os.path.exists(agent_dir):
                import shutil
                try:
                    shutil.rmtree(agent_dir)
                    logger.info(f"🧹 已成功清理 Agent 本地殘留沙盒目錄：{agent_dir}")
                except Exception as e:
                    logger.warning(f"⚠️ 清理殘留目錄時發生非致命錯誤: {str(e)}")

        await asyncio.to_thread(_cleanup_residual_files)
        logger.info(f"💥 官方已抹除 Agent 記憶且映射對照表已連帶銷毀: {agent_id}")
        return {"status": "success", "message": f"Agent [{agent_id}] 銷毀成功與專屬房間對照表安全銷毀。"}
        
    except HTTPException:
        raise
    except Exception as e: 
        logger.error(f"❌ 刪除管線發生未知崩潰: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================================
# 7. 服務啟動宣告（生產環境防禦性宣告）
# =====================================================================
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Hermes Native Multi-Agent Proxy 異步防禦完全體已成功啟動。")
    logger.info(f"📁 當前隔離 Profile 根路徑鎖定為: {PROFILES_BASE_DIR}")


