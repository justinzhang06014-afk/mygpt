import os
import re
import json
import yaml
import asyncio
from datetime import datetime
from config import logger, PROFILES_BASE_DIR
import mcp_services
import approval_settings

PHISON_LLM_KEY = os.getenv("PHISON_API_KEY", "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249")

def _sync_load_session(mapping_path: str, room_id: str) -> str:
    if not os.path.exists(mapping_path): 
        return None
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            val = data.get(str(room_id))
            
            # 🛡️ 核心防禦：如果找不到，或是存到了字串的 "None"，一律回傳乾淨的 Python None
            if val is None or str(val).strip() == "None":
                return None
                
            return str(val)
    except Exception: 
        return None


def _sync_save_session(mapping_path: str, room_id: str, native_id: str):
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
    return await asyncio.to_thread(_sync_load_session, os.path.join(agent_dir, "session_mapping.json"), room_id)

async def save_native_session_id(agent_dir: str, room_id: str, native_id: str):
    await asyncio.to_thread(_sync_save_session, os.path.join(agent_dir, "session_mapping.json"), room_id, native_id)

async def _fetch_native_sessions_set(current_env: dict) -> set:
    try:
        proc = await asyncio.create_subprocess_exec(
            "hermes", "sessions", "list", env=current_env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            return set(re.compile(r"\d{8}_\d{6}_\w+|\b[a-f0-9-]{36}\b").findall(stdout.decode("utf-8")))
    except Exception: pass
    return set()

def parse_physical_memory_to_json(agent_dir: str, agent_id: str, room_id: str, native_id: str) -> dict:
    """【高防禦性解析核心】讀取物理 memory.md，將其結構化為大禮包 JSON 格式"""
    memory_file_path = os.path.join(agent_dir, "memories", "memory.md")
    facts = []
    categories = set(["未分類事實"])
    
    # 預設大禮包骨架
    result = {
      "status": "success",
      "meta": {
        "agent_id": agent_id,
        "room_id": room_id,
        "native_session_id": native_id or "Unknown",
        "last_sync_time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brain_saturation_percentage": 0,
        "max_allowed_facts": 20,
        "current_facts_count": 0
      },
      "categories": [],
      "memories": []
    }

    if not os.path.exists(memory_file_path):
        result["categories"] = list(categories)
        return result

    try:
        with open(memory_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        idx = 1
        for line in lines:
            clean_line = line.strip().lstrip("- ").lstrip("* ").strip()
            if not clean_line or clean_line.startswith("#"): 
                continue
            
            # 簡單規則引擎：依據關鍵字動態歸類（可後續拓展）
            category = "未分類事實"
            if any(k in clean_line.lower() for k in ["docker", "python", "fastapi", "code", "套件", "後端"]):
                category = "技術棧與開發環境"
            elif any(k in clean_line.lower() for k in ["習慣", "討厭", "喜歡", "偏好", "希望"]):
                category = "工作偏好與習慣"
            elif any(k in clean_line.lower() for k in ["專案", "伺服器", "內網", "業務", "端點"]):
                category = "核心業務事実"
                
            categories.add(category)
            facts.append({
                "id": f"mem_fact_{str(idx).zfill(3)}",
                "category": category,
                "text": clean_line,
                "confidence_score": 0.95,
                "auto_captured": True,
                "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            })
            idx += 1
            
        result["memories"] = facts
        result["categories"] = list(categories)
        result["meta"]["current_facts_count"] = len(facts)
        result["meta"]["brain_saturation_percentage"] = int((len(facts) / 20) * 100)
        
    except Exception as e:
        logger.error(f"❌ 解析物理 memory.md 失敗: {str(e)}")
        
    return result

async def ensure_hermes_profile_exists(
    agent_id: str,
    system_prompt: str,
    clone_from: str | None = None,
    source_system_prompt: str | None = None,
) -> str:
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    init_env = os.environ.copy()
    init_env["HERMES_HOME"] = agent_dir
    init_env["OPENAI_API_KEY"] = PHISON_LLM_KEY
    init_env["HERMES_API_KEY"] = PHISON_LLM_KEY

    # 🛡️【已用 docker exec 實測核對】不可用 `hermes profile show` 的 returncode 判斷是否已存在：
    # hermes CLI 一啟動就會在 HERMES_HOME 底下側效應建立 logs/ 資料夾,導致 `profile show` 對任何
    # (包含從未建立過的) agent_id 一律回傳成功。改用最單純的實體資料夾存在判斷,可靠且不必呼叫 CLI。
    already_provisioned = os.path.isdir(agent_dir)

    if not already_provisioned:
        if clone_from:
            source_dir = os.path.join(PROFILES_BASE_DIR, clone_from)
            if not os.path.isdir(source_dir):
                # 🐛 0716 修正：Agent 建立當下只會寫進 Postgres，hermes 自己的 profile 目錄要等
                # 第一次真的對話才會被建立（見下面 else 分支）。如果使用者建立 agent 後從沒聊過
                # 天就直接按「複製」，來源目錄不存在，--clone-from 一定失敗。改成：先幫來源 agent
                # 補做一次一般初始化（用它自己真正的 system_prompt，不是隨便塞預設值），
                # 讓「複製」不用強迫使用者先手動開場聊一句話。
                logger.warning(f"[真Clone] 來源 Agent '{clone_from}' 尚未初始化，先幫它補建立 profile 再繼續複製")
                await ensure_hermes_profile_exists(clone_from, source_system_prompt or f"你是 {clone_from}，一位專業助理。")
                if not os.path.isdir(source_dir):
                    raise RuntimeError(f"來源 Agent '{clone_from}' 補建立失敗，無法作為複製範本")

            # 🛡️ 【已用 docker exec 實測核對】--clone-from 若把 HERMES_HOME 指向目標自己的路徑會自我污染：
            # hermes CLI 啟動時會先在 HERMES_HOME 底下建立 logs/ 側效應資料夾，導致 create 的「已存在」檢查誤判。
            # 解法：HERMES_HOME 指向與目標同層、但檔名不同的共用暫存資料夾，讓 hermes 依 dirname(HERMES_HOME) 解析 profiles 根目錄。
            clone_env = init_env.copy()
            clone_env["HERMES_HOME"] = os.path.join(PROFILES_BASE_DIR, "_cli_scratch")
            create_args = [
                "hermes", "profile", "create", agent_id,
                "--clone-from", clone_from, "--clone-all",
                "--description", f"Cloned from {clone_from}"
            ]
            create_proc = await asyncio.create_subprocess_exec(
                *create_args, env=clone_env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, create_stderr = await create_proc.communicate()
            if create_proc.returncode != 0:
                raise RuntimeError(f"hermes profile create --clone-from 失敗: {create_stderr.decode('utf-8', errors='ignore').strip()}")
        else:
            create_args = ["hermes", "profile", "create", agent_id, "--description", f"Automated Agent {agent_id}"]
            create_proc = await asyncio.create_subprocess_exec(
                *create_args, env=init_env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await create_proc.communicate()

    def _write_isolated_config():
        os.makedirs(agent_dir, exist_ok=True)
        # 🆕 0716：這個 agent 自己選過的 approval 設定（沒選過就是預設值：manual/False/False，
        # 跟改動前的行為完全一致，不影響既有 agent）。
        agent_approvals = approval_settings.get_agent_approval_settings(agent_id)
        # 🧪 0716：LLM_PROVIDER=native 時走 hermes 原生 provider（例如 anthropic），
        # 不塞 base_url/api_key（那兩個 key 是「custom 端點」專用，原生 provider 靠
        # ANTHROPIC_API_KEY 這類環境變數，寫進 config.yaml 反而是多餘/會被忽略的欄位）。
        # 沒設定 LLM_PROVIDER 就完全照舊，正式環境行為不變。
        if os.getenv("LLM_PROVIDER") == "native":
            model_config = {
                "provider": os.getenv("LLM_NATIVE_PROVIDER", "auto"),
                "default": os.getenv("LLM_MODEL", "anthropic/claude-haiku-4-5-20251001"),
            }
        else:
            model_config = {
                "provider": "custom",
                "base_url": os.getenv("LLM_BASE_URL", "https://ainexus.phison.com/api/external/v1"),
                "api_key": os.getenv("LLM_API_KEY", PHISON_LLM_KEY),
                "default": os.getenv("LLM_MODEL", "Qwen/Qwen3.6-35B-A3B-FP8")
            }

        config_data = {
            "model": model_config,
            # 🛡️【已對照 hermes 原始碼 hermes_cli/config.py 的真實 memory schema 核對】
            # provider 留空字串 = 純內建 MEMORY.md/USER.md 模式。之前寫死 "built-in" 是錯的：
            # hermes 會把它當成一個外部記憶體 provider 名稱去找，找不到就顯示「Plugin: NOT installed」。
            # 🐛 0717 修正：上一行原本寫「nudge_interval 不是真實存在的設定鍵、已移除」是錯的判斷。
            # 直接查了 agent_init.py:1330-1338 的原始碼，nudge_interval 貨真價實會被讀取
            # （mem_config.get("nudge_interval", 10)），控制「每幾輪使用者對話，hermes 自己
            # 主動提醒/檢查要不要更新記憶」。而且這個計數器就算我們每輪都換一個全新 subprocess
            # 也不會壞掉：agent/turn_context.py 會用「目前對話歷史的使用者輪數 % nudge_interval」
            # 重新算回計數器，不是只存在單一 process 的記憶體裡，配我們的 resume_session 機制沒問題。
            # 這裡明確寫成 10（跟 hermes 自己沒設定時的預設值一致，先不改變既有行為，
            # 之後如果要讓使用者自訂這個數字，再比照 approval_settings.py 加一個欄位）。
            "memory": {
                "memory_enabled": True,
                "user_profile_enabled": True,
                "nudge_interval": 10,
                # 🎛️【核准開關 1/2】要不要讓 memory.md/user.md 寫入前彈窗詢問使用者。
                # 目前先關閉(False)。底層機制已經修好、隨時可以打開：approve-write 的 event
                # key 對不上、approve_event 沒 clear() 導致連續核准失效兩個 bug 都已修正。
                # 要開的話改成 True 即可，不用動其他任何程式碼。
                "write_approval": agent_approvals["memory_write_approval"],
                "provider": ""
            },
            # 🆕 0716：一般危險指令/寫檔的核准模式，對照 hermes_cli/config.py 的真實 schema：
            # manual（預設，全部都問）/ smart（LLM 自動判斷低風險放行）/ off（完全不問）。
            # 之前這裡完全沒寫這個區塊，等於一直吃 hermes 內建預設值 manual，行為不變。
            "approvals": {
                "mode": agent_approvals["mode"]
            },
            # 🛠️ 0716 改回 Local 本端執行：SSH 回連宿主機這條路對 1000 人多機器的目標不適用
            # （討論結論見對話紀錄），而且原本這組設定 key 名稱本身就不是 hermes 真正的 schema
            # （真正的 key 是 ssh_host/ssh_user/ssh_key，且只支援金鑰驗證不支援密碼），
            # 不會真的生效，只會讓 hermes 每次啟動都嘗試連線失敗。改回 local 最穩定。
            "terminal": {
                "backend": "local",
                "cwd": "/workspace",
                "timeout": 180,
                "persistent_shell": True
            },

            # 📂 4. 【新加入】手動啟用全套程式碼修改工具 未來刪除
            "tools": {
                "enabled": [
                    "file_read",
                    "file_write",
                    "file_edit",
                    "patch_code_file",
                    "view_code_item",
                    "grep_search",
                    "bash"
                ]
            },

            # 🎛️【核准開關 2/2】要不要讓技能安裝/修改先卡在待審核佇列，等使用者按核准才真的套用。
            # 目前先關閉(False)。main.py 裡 /skills/pending 的 list/approve/reject 三支 API
            # 已經寫好、隨時可用，要開的話改成 True 即可，不用動其他任何程式碼。
            "skills": {
                "write_approval": agent_approvals["skills_write_approval"]
            },
            
            "context":{
                "enabled": True  # 確保上下文注入開啟
            }

        }

        # 🔌 6.【新加入】MCP 商店：把這個 agent 自己 $HERMES_HOME/mcp.json 裡標記
        # resident/optional_installed 的項目，轉成 hermes 原生 mcp_servers 區塊。
        # 憑證實際值不在這裡處理——mcp_services.set_agent_mcp_credentials() 會直接寫 .env，
        # 這裡只負責把 ${ENV_VAR} 引用寫進 config.yaml，跟 hermes 自己 `mcp add` 產生的格式一致。
        mcp_servers_block = mcp_services.build_hermes_mcp_servers_block(agent_id)
        if mcp_servers_block:
            config_data["mcp_servers"] = mcp_servers_block

        with open(os.path.join(agent_dir, "config.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f, default_flow_style=False)
            
    await asyncio.to_thread(_write_isolated_config)

    soul_path = os.path.join(agent_dir, "SOUL.md")
    extended_soul_prompt = f"""{system_prompt}
=====================================================================
【🧠 記憶體自主運行與大腦統整沉澱最高核心條款】
1. 自主記憶捕捉：你在後台擁有全自動的長期記憶大腦（MEMORY.md）。安靜執行，不要向用戶宣告「我已經記下來了」。
2. 記憶定期沉澱與濃縮：保持 MEMORY.md 內的事實條目不超過 15-20 條。一旦超過，刪除過期雜訊，只留下沉澱後的金字塔精華。
3. 你每次開始對話前都會先讀取你自己的memory.md
=====================================================================
"""
    def _write_soul():
        with open(soul_path, "w", encoding="utf-8") as f: f.write(extended_soul_prompt)
    await asyncio.to_thread(_write_soul)
    return agent_dir


