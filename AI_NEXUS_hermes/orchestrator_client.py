"""
呼叫同事的外部 orchestrator 服務，取代 runtime_manager.py 自己用 docker.sock 建容器
那條路——同事的服務負責「空間/儲存/容器怎麼跑」。

⚠️ 跟本機 docker.sock 模式（runtime_manager.py）不一樣的地方：本機模式建出來的
容器跑的是我們自己這份 ai-nexus-hermes wrapper（main.py 在容器裡面），可以直接
走 ACP+CLI。但 main.py 不會被烤進對方 docker 管理端的 image，遠端這條路建出來的
容器跑的是原生 hermes-agent（`HERMES_IMAGE`），沒有 main.py，ACP 是 stdio 協定，
沒辦法跨主機——所以遠端這條路是靠 hermes-agent 原生的 gateway（api_server 平台，
`API_SERVER_ENABLED=true`）用 HTTP 把聊天橋接過去，main.py 留在我們自己這邊，
呼叫 {base_url}/v1/chat/completions，不是本機模式的 ACP。

設計成「開關式」：設定 ORCHESTRATOR_URL 環境變數才會啟用這條路；沒設定就照舊用
runtime_manager.py 自己的 docker.sock 邏輯（本機測試/沒有同事服務時還能用）。
main.py 只需要知道 base_url/external_base_url 這幾個欄位，不用管
底層是走 ACP 還是 Gateway HTTP。

修正：根據客戶需求調整的資料類型和格式規格，
- userId 直接使用整數格式（使用者傳入 "2" -> userId: 2）
- 簡化 user_id 轉換邏輯，移除 CRC32 哈希，直接採用 int(str) 轉換
- API_SERVER_KEY 改用空字串，與需求範例保持一致
- volumes 路徑使用原始 user_id: /home/phison/ainexus/agent-data/{user_id}
- 移除複雜的密鑰存儲和驗證邏輯
- 預設 orchestrator URL 為 http://192.168.41.173:5080

⚠️ 重要注意事項：
- 遠端主機 (192.168.41.173) 的 /home/phison/ainexus/agent-data/{user_id} 路徑需要預先準備好
- 檔案包含：config.yaml, SOUL.md, mcp.json, phison_mcp_bridge.py
- 确保 orchestrator 的 AllowedBindPrefixes 配置允許掛載 /home/phison/ainexus/agent-data 路徑
"""
import os
import json
import requests
from pathlib import Path
from typing import List, Tuple

from config import logger, PHISON_LLM_KEY, TARGET_BASE_URL, TARGET_MODEL

# #0722修正：Orchestrator 服務的固定主機 URL（根據實際部署環境設定）
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://192.168.41.173:5080").rstrip("/")
ORCHESTRATOR_TIMEOUT_SECONDS = int(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "120"))

# #0722修正：External Access Proxy 的設定（根據 docker_README.md）
ORCHESTRATOR_EXTERNAL_API_KEY = os.getenv("ORCHESTRATOR_EXTERNAL_API_KEY", "change-me")
ORCHESTRATOR_PUBLIC_BASE_URL = os.getenv("ORCHESTRATOR_PUBLIC_BASE_URL", "http://192.168.41.173:5080")

# #0722修正：主機上的 hermes 資料根目錄路徑
# - 根據 docker_README.md，外部 orchestrator 掛載到容器的標準路徑是 /data
# - 外部 orchestrator 需要將此路徑 {主機}/users/{user_id} 掛到容器的 /data
# - hermes 會在 /data 下找 profiles/{profile_id}/config.yaml 和 mcp.json
# - 修改預設路徑為遠端 Orchestrator 允許的路徑：/home/phison/ainexus/agent-data
HERMES_DATA_ROOT = os.getenv("HERMES_DATA_ROOT", "/home/phison/ainexus/agent-data")

HERMES_IMAGE = os.getenv("HERMES_IMAGE", "nousresearch/hermes-agent:latest")


def _convert_user_id(user_id: str) -> int:
    """將字串 user_id 直接轉換為整數，用於 Orchestrator API 的 userId 欄位。
    
    直接轉換為整數，不進行哈希或其他處理：
    - input: "1"  → output: 1
    - input: "2"  → output: 2
    - input: "100" → output: 100
    """
    try:
        return int(user_id)
    except ValueError:
        raise ValueError(f"無法將 user_id '{user_id}' 轉換為整數")


def is_enabled() -> bool:
    """有設定 ORCHESTRATOR_URL 才走外部 orchestrator，這是唯一的開關。
    
    🔧 正式模式：啟用遠端 Orchestrator 連線
    """
    return bool(ORCHESTRATOR_URL)


def _upload_files_to_orchestrator(user_id: str, agent_dir: str, required_files: List[str]) -> bool:
    """
    上傳 hermes 所需的檔案到遠端 Orchestrator 主機。
    
    使用 multipart/form-data 格式傳送檔案：
    - endpoint: POST /api/v1/users/{user_id_int}/files
    - files: 表單欄位固定為 "files"，支援多檔案上傳
    """
    user_id_int = _convert_user_id(user_id)
    
    # 🎯 關鍵修正 1：補上符合規格的 /files 後綴
    upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id_int}/files"
    
    files_to_upload = []
    opened_files = []  # 用來追蹤手動開啟的檔案物件，以便在 finally 區塊安全關閉
    
    try:
        for filename in required_files:
            file_path = Path(agent_dir) / filename
            if not file_path.exists():
                logger.error(f"❌ [Orchestrator] 檔案不存在: {file_path}")
                return False
            
            # 開啟檔案並記錄到清單
            f = open(file_path, "rb")
            opened_files.append(f)
            
            # 🎯 關鍵修正 2：第一個參數改為固定字串 "files"，對應後端的多檔案接收欄位
            files_to_upload.append(("files", (filename, f, "application/octet-stream")))
        
        logger.info(f"📤 [Orchestrator] 開始上傳檔案到: {upload_url}")
        logger.info(f"📤 [Orchestrator] 準備上傳的檔案: {required_files}")
        logger.info(f"📤 [Orchestrator] agent_dir 實際路徑: {agent_dir}")
        
        upload_resp = requests.post(
            upload_url,
            files=files_to_upload,
            timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
        )
        
        # 記錄詳細回應
        logger.info(f"📤 [Orchestrator] 回應狀態碼: {upload_resp.status_code}")
        logger.info(f"📤 [Orchestrator] 回應內容: {upload_resp.text}") 
        
        upload_resp.raise_for_status()
        
        upload_data = upload_resp.json()
        logger.info(f"✅ [Orchestrator] 檔案上傳成功: {json.dumps(upload_data, indent=2, ensure_ascii=False)}")

        # 🎯 關鍵修正 3：對照你提供的 API 回傳規格，逐筆驗證 files 陣列中的 status
        files_result = upload_data.get("files", [])
        
        # 後端常見的成功狀態為 written 或 success，若有其他成功字串可自行加入比對
        failed_files = [f for f in files_result if f.get("status") not in ("written", "success")]
        
        if failed_files:
            for file_result in failed_files:
                logger.error(f"❌ [Orchestrator] 檔案上傳失敗: {file_result.get('path')} - {file_result.get('error')}")
            return False

        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [Orchestrator] 檔案上傳失敗: {str(e)}")
        return False
        
    finally:
        # 🎯 關鍵修正 4：安全關閉所有開啟的檔案，絕不引發額外的 TypeError
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass


def _extract_base_url(data: dict):
    """
    #0722修正：根據 docker_README.md 的 API 回應格式，優先使用 externalBaseUrl（如果存在），
    其次使用 baseUrl。同時回傳 externalBaseUrl 給 main.py 使用。

    Returns:
        (base_url, external_base_url) 元組
    """
    logger.info(f"🔍 [Debug] _extract_base_url 輸入 data: {data}")
    
    # 確保 data 是字典格式
    if not isinstance(data, dict):
        logger.error(f"❌ [Debug] data 不是字典格式: {type(data)}")
        return None, None
    
    # 提取 externalBaseUrl（當 ExternalAccess 啟用時對外暴露的 URL）
    external_base_url = data.get("externalBaseUrl")
    
    # 提取 baseUrl（同一 Docker 內部網路的 URL）
    base_url = data.get("baseUrl")
    
    # 嘗試其他可能的欄位名稱（兼容不同版本的 API）
    if not base_url:
        base_url = data.get("baseUrlInternal") or data.get("internalUrl") or data.get("url")
    if not external_base_url:
        external_base_url = data.get("externalUrl") or data.get("publicUrl")
    
    logger.info(f"🔍 [Debug] 提取的值 - base_url: {base_url} (類型: {type(base_url)}), external_base_url: {external_base_url} (類型: {type(external_base_url)})")

    # 處理可能的列表/陣列情況（取第一個元素）
    if isinstance(base_url, (list, tuple)) and len(base_url) > 0:
        logger.warning(f"⚠️ [Debug] base_url 是陣列，取第一個元素: {base_url[0]}")
        base_url = base_url[0]
    else:
        # 確保 base_url 是字串或 None
        base_url = str(base_url) if base_url is not None else None
    
    if isinstance(external_base_url, (list, tuple)) and len(external_base_url) > 0:
        logger.warning(f"⚠️ [Debug] external_base_url 是陣列，取第一個元素: {external_base_url[0]}")
        external_base_url = external_base_url[0]
    else:
        # 確保 external_base_url 是字串或 None
        external_base_url = str(external_base_url) if external_base_url is not None else None

    # 如果都没有，返回 None, None
    if not base_url and not external_base_url:
        logger.info("🔍 [Debug] 兩個都是 None，返回 None, None")
        return None, None

    logger.info(f"🔍 [Debug] 返回 base_url: {base_url}, external_base_url: {external_base_url}")
    return base_url, external_base_url


def get_stored_api_key(agent_dir: str) -> str | None:
    """API_SERVER_KEY 使用空字串，不需要存儲，直接返回空字串"""
    return ""


def find_user_worker(user_id: str) -> dict | None:
    """
    查詢遠端 Orchestrator 上這個 user_id 是否已經有 worker（不篩狀態，有紀錄就回傳）。
    用於每輪聊天前的「容器還在不在」檢查，避免每輪都重打
    POST /api/v1/workers 觸發 409 才知道已存在。

    Returns:
        worker dict（含 status/baseUrl/externalBaseUrl 等）或 None（找不到/查詢失敗）
    """
    if not is_enabled():
        return None

    user_id_int = _convert_user_id(user_id)
    try:
        resp = requests.get(f"{ORCHESTRATOR_URL}/api/v1/workers", timeout=ORCHESTRATOR_TIMEOUT_SECONDS)
        resp.raise_for_status()
        workers = resp.json()
        if not isinstance(workers, list):
            return None
        for worker in workers:
            if isinstance(worker, dict) and worker.get("userId") == user_id_int:
                return worker
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ [Orchestrator] 查詢使用者 {user_id} 的容器狀態失敗: {str(e)}")
        return None


def sync_env_token(user_id: str, agent_dir: str) -> bool:
    """
    只重傳 .env（裝 PHISON_TOKEN 的檔案），不動 config.yaml/SOUL.md/mcp.json。

    根據 hermes-agent 原生 gateway 的實作：長駐的 gateway process 每一輪
    對話都會重新讀一次 HERMES_HOME/.env 撿最新憑證，config.yaml 的 mcp_servers.env
    用 ${MCP_PHISON_AINEXUS_PHISON_TOKEN} 引用它——所以不用重建/重啟容器，
    只要把新的 .env 覆蓋到遠端掛載的目錄，下一輪對話 gateway 自己就會撿到新 token。

    非致命：失敗只記警告、回傳 False，呼叫端不應該因為這個中斷聊天。
    """
    if not is_enabled():
        return False

    env_path = Path(agent_dir) / ".env"
    if not env_path.exists():
        return False

    user_id_int = _convert_user_id(user_id)
    upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id_int}"
    try:
        logger.info(f"🔄 [Orchestrator] 開始同步 .env 到: {upload_url}")
        with open(env_path, "rb") as f:
            resp = requests.post(
                upload_url,
                files=[(".env", (".env", f, "application/octet-stream"))],
                timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
            )
        
        logger.info(f"🔄 [Orchestrator] .env 同步回應狀態碼: {resp.status_code}")
        logger.info(f"🔄 [Orchestrator] .env 同步回應內容: {resp.text}")
        
        resp.raise_for_status()
        logger.info(f"🔄 [Orchestrator] 已同步最新 .env（token）給使用者 {user_id} 的容器")
        return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ [Orchestrator] 同步 .env token 失敗（使用者 {user_id}）: {str(e)}")
        return False


def ensure_user_runtime_synced(user_id: str, agent_dir: str) -> dict | None:
    """
    每輪聊天前呼叫：容器不存在就建立（沿用 ensure_user_runtime 的完整流程），
    容器已存在就只補傳最新 .env token，不重跑整個建立流程。

    Returns:
        worker/runtime 資訊 dict，查詢或建立都失敗時回傳 None（呼叫端應該把這當
        「這輪先不管遠端同步，本地照舊回答」，不應該讓聊天整個中斷）。
    """
    if not is_enabled():
        return None

    existing = find_user_worker(user_id)
    if existing:
        sync_env_token(user_id, agent_dir)
        # 統一輸出格式跟 ensure_user_runtime() 一致（base_url/worker_id 這種
        # snake_case 命名），呼叫端不用管這輪是「新建」還是「既有」兩種不同欄位長相。
        extract_result = _extract_base_url(existing)
        
        base_url = None
        external_base_url = None
        
        if isinstance(extract_result, (list, tuple)) and len(extract_result) >= 2:
            base_url, external_base_url = extract_result[0], extract_result[1]
        elif isinstance(extract_result, (list, tuple)) and len(extract_result) == 1:
            base_url = extract_result[0]
            external_base_url = None
        elif isinstance(extract_result, (list, tuple)) and len(extract_result) == 0:
            base_url = None
            external_base_url = None
        
        normalized = {
            "status": existing.get("status", "running"),
            "base_url": base_url or external_base_url,
            "user_id": user_id,
            "user_id_int": _convert_user_id(user_id),
            "api_server_key": "",  # 使用空字串
        }
        if existing.get("id"):
            normalized["worker_id"] = existing["id"]
        if external_base_url:
            normalized["external_base_url"] = external_base_url
        return normalized

    try:
        return ensure_user_runtime(user_id, agent_dir)
    except Exception as e:
        logger.warning(f"⚠️ [Orchestrator] 聊天前確認容器失敗（使用者 {user_id}）: {str(e)}")
        return None


def ensure_user_runtime(user_id: str, agent_dir: str) -> dict:
    """
    建立遠端 Orchestrator 使用者容器，包含檔案上傳和容器建立流程。
    
    完整流程：
    1. 在本地準備 hermes 檔案 (config.yaml, SOUL.md, mcp.json, phison_mcp_bridge.py) - 由 main.py 完成
    2. 將檔案上傳到遠端 Orchestrator 主機
    3. POST 建立容器，掛載遠端主機檔案目錄到容器 /data
    
    Args:
        user_id: 使用者 ID (字串格式，會轉換為整數)
        agent_dir: 本地 agent 目錄路徑 (已準備好所有檔案)
        
    Returns:
        dict: 包含 container 資訊 {"status": "created", "base_url": "...", ...}
    """
    if not is_enabled():
        raise RuntimeError("ORCHESTRATOR_URL 未設定，不應該呼叫這個函式（main.py 應該先檢查 is_enabled()）")

    # userId 直接轉為整數
    user_id_int = _convert_user_id(user_id)
    
    # 遠端主機路徑：使用整數格式的 user_id
    remote_host_path = f"/home/phison/ainexus/agent-data/{user_id_int}"
    required_files = ["config.yaml", "SOUL.md", "mcp.json", "phison_mcp_bridge.py"]
    
    # 步驟1: 檢查本地檔案是否存在
    logger.info(f"🔍 [Orchestrator] 準備上傳檔案，本地路徑: {agent_dir}")
    missing_files = []
    for filename in required_files:
        file_path = Path(agent_dir) / filename
        if not file_path.exists():
            missing_files.append(filename)
    
    if missing_files:
        raise RuntimeError(f"缺少必要檔案: {', '.join(missing_files)}，本地路徑: {agent_dir}")
    
    logger.info(f"✅ [Orchestrator] 本地檔案檢查通過")

    # 步驟2: 上傳檔案到遠端 Orchestrator
    upload_success = _upload_files_to_orchestrator(user_id, agent_dir, required_files)
    if not upload_success:
        raise RuntimeError(f"檔案上傳到遠端 Orchestrator 失敗，停止容器建立流程")

    # .env（PHISON_TOKEN 等憑證）是選填的：ensure 當下不一定有帶 phison_token，
    # 沒有就沒有這個檔案，不當必要檔案處理。但如果本地已經寫好了（帶了 phison_token），
    # 一定要在容器「第一次啟動」之前就上傳——長駐的 gateway 只在開機那一刻讀一次
    # PHISON_TOKEN 去啟動 MCP 子行程，晚一步上傳，容器都已經開機了也沒用（見
    # sync_env_token 的說明）。
    if (Path(agent_dir) / ".env").exists():
        sync_env_token(user_id, agent_dir)
    
    # 步驟3: 組裝建立容器的 payload
    # API_SERVER_KEY 使用空字串，與需求範例保持一致
    api_server_key = ""
    payload = {
        "userId": user_id_int,
        "image": HERMES_IMAGE,
        "name": f"agent-worker-{user_id_int}", 
        "environment": {
            "PHISON_API_KEY": os.getenv("PHISON_API_KEY", PHISON_LLM_KEY),
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "custom"),
            "LLM_BASE_URL": os.getenv("LLM_BASE_URL", TARGET_BASE_URL),
            "LLM_MODEL": os.getenv("LLM_MODEL", TARGET_MODEL),
            "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
            "API_SERVER_ENABLED": "true",
            "API_SERVER_HOST": "0.0.0.0",
            "API_SERVER_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJqdXN0aW5femhhbmciLCJqdGkiOiIyNjlmZTY2MS05Mzk1LTQ1ZDYtOGMxMC01YzRiZTkxNzc1MjgiLCJpZCI6IjEyMDkwIiwiZXhwIjoxNzg0Nzk4OTgzLCJpc3MiOiJ5b3VyX2lzc3VlciIsImF1ZCI6InlvdXJfaXNzdWVyIn0.auPGqWzdJzSS0EXMNL9CV4ZlGzgdgxvGaaS5fDpH0uk",
            "API_SERVER_CORS_ORIGINS": "*",
        },
        "volumes": {
            remote_host_path: "/opt/data",
        },
    }

    # 如此顯示的做事：輸出實際發送的 payload 和 URL
    api_url = f"{ORCHESTRATOR_URL}/api/v1/workers"
    logger.info(f"📤 [Orchestrator] 發送的 Request URL: {api_url}")
    logger.info(f"📤 [Orchestrator] 使用者 user_id: {user_id} -> userId: {user_id_int}")
    logger.info(f"📤 [Orchestrator] 發送的 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    logger.info(f"📤 [Orchestrator] HERMES_IMAGE 環境變數值: {HERMES_IMAGE}")
    logger.info(f"📤 [Orchestrator] HERMES_DATA_ROOT 環境變數值: {HERMES_DATA_ROOT}")

    try:
        resp = requests.post(
            api_url,
            json=payload,
            timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
        )

        # 409 代表打到既有容器
        was_freshly_created = resp.status_code != 409

        # #0722修正：處理 409 Conflict 狀態，表示使用者已有容器存在
        if resp.status_code == 409:
            try:
                error_data = resp.json()
                existing_id = error_data.get("existingWorkerId")
                if existing_id:
                    logger.info(f"ℹ️  [Orchestrator] 使用者 {user_id} 已有容器 ID: {existing_id}，取得現有容器資訊")
                    # 取得現有容器的詳細資訊
                    get_resp = requests.get(
                        f"{ORCHESTRATOR_URL}/api/v1/workers/{existing_id}",
                        timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
                    )
                    get_resp.raise_for_status()
                    data = get_resp.json()
                else:
                    # 如果沒有 existingWorkerId，可能是 create 還在 pending 狀態
                    logger.warning(f"⚠️  [Orchestrator] 使用者 {user_id} 的容器建立仍在進行中: {error_data.get('error')}")
                    raise RuntimeError(f"Orchestrator 回報Conflict但無現有容器ID: {error_data}")
            except Exception as e:
                logger.error(f"❌ [Orchestrator] 處理 409 Conflict 錯誤時發生例外: {str(e)}")
                raise RuntimeError(f"處理 409 Conflict 失敗: {str(e)}")
        else:
            # 非 409 狀態，正常處理
            resp.raise_for_status()
            
            # 檢查回應格式 - 處理可能的字符串回應
            try:
                content_type = resp.headers.get('Content-Type', '')
                if 'application/json' in content_type or resp.text.startswith('{'):
                    data = resp.json()
                else:
                    # 如果不是 JSON 格式，嘗試將字符串轉為 worker ID
                    response_text = resp.text.strip()
                    logger.warning(f"⚠️ [Orchestrator] POST 返回非 JSON 格式: {response_text}")
                    try:
                        worker_id = int(response_text)
                        # 假設返回的是 worker ID，需要用 GET 取得完整資料
                        get_resp = requests.get(
                            f"{ORCHESTRATOR_URL}/api/v1/workers/{worker_id}",
                            timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
                        )
                        get_resp.raise_for_status()
                        data = get_resp.json()
                    except (ValueError, requests.exceptions.RequestException) as e:
                        logger.error(f"❌ [Orchestrator] 無法解析回應: {response_text}, 錯誤: {str(e)}")
                        raise RuntimeError(f"Orchestrator 回應格式異常: {response_text}")
            except Exception as e:
                logger.error(f"❌ [Orchestrator] 解析回應失敗: {str(e)}")
                raise RuntimeError(f"解析 Orchestrator 回應失敗: {str(e)}")
                
            logger.info(f"🔍 [Debug] Orchestrator 返回的完整 data: {json.dumps(data, indent=2, ensure_ascii=False)}")

    except requests.exceptions.RequestException as e:
        # 🔍 詳細錯誤處理：試圖獲取對方的錯誤訊息
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_json = e.response.json()
                error_detail = f"{str(e)} | 相應內容: {json.dumps(error_json, ensure_ascii=False)}"
            except:
                error_detail = f"{str(e)} | Status: {e.response.status_code} | Response: {e.response.text[:200]}"

        logger.error(f"❌ [Orchestrator] 呼叫 {ORCHESTRATOR_URL} 建立使用者 {user_id} 的 Runtime 失敗: {error_detail}")
        raise RuntimeError(f"呼叫 orchestrator 失敗: {error_detail}")

    try:
        extract_result = _extract_base_url(data)
        
        base_url = None
        external_base_url = None
        
        if isinstance(extract_result, (list, tuple)) and len(extract_result) >= 2:
            base_url, external_base_url = extract_result[0], extract_result[1]
            logger.info(f"✅ [Debug] 成功解包: base_url={base_url}, external_base_url={external_base_url}")
        elif isinstance(extract_result, (list, tuple)) and len(extract_result) == 1:
            base_url, external_base_url = extract_result[0], None
            logger.warning(f"⚠️  [Debug] 解包長度1: base_url={base_url}, external_base_url=None")
        elif isinstance(extract_result, (list, tuple)) and len(extract_result) == 0:
            base_url, external_base_url = None, None
            logger.warning(f"⚠️  [Debug] 解包長度0: base_url=None, external_base_url=None")
        else:
            logger.error(f"❌ [Debug] _extract_base_url 返回格式錯誤: {extract_result}, 類型: {type(extract_result)}")
            raise RuntimeError(f"_extract_base_url 返回錯誤格式: {type(extract_result)}")
            
    except Exception as e:
        logger.error(f"❌ [Orchestrator] 解包錯誤: {str(e)}, data: {data}, extract_result: {extract_result}")
        raise RuntimeError(f"解包錯誤: {str(e)}")
    
    if not base_url and not external_base_url:
        raise RuntimeError(f"Orchestrator 回應沒有可辨識的位址欄位（baseUrl 或 externalBaseUrl）: {data}")

    # 從回應中提取詳細資訊，供 main.py 回傳給使用者
    worker_id = data.get("id")
    worker_name = data.get("name")
    status = data.get("status", "created")

    result = {
        "status": status,
        "base_url": base_url or external_base_url,
        "user_id": user_id,
        "user_id_int": user_id_int,
        "api_server_key": "",  # 使用空字串
    }

    # 如果有 worker_id，加入回應（locally created 或 existing 都有 id）
    if worker_id:
        result["worker_id"] = worker_id
        logger.info(f"✅ [Orchestrator] 使用者 {user_id} 的 Runtime: {status} -> {base_url} (Worker ID: {worker_id})")

        # 額外回傳 externalBaseUrl 給呼叫端使用
        if external_base_url:
            result["external_base_url"] = external_base_url
            logger.info(f"🌐 [Orchestrator] 對方提供外部訪問 URL: {external_base_url}")

        # 生成容器內部用 Swagger URL（在同 Docker network 內可訪問）
        container_name = worker_name or f"agent-worker-{worker_id}"
        base_host = (base_url or external_base_url).split(":")[0]  # http://agent-worker-xxx
        if base_host.startswith("http://agent"):
            result["swagger_url"] = f"http://{container_name}:8643/docs"
        else:
            result["swagger_url"] = f"{base_url}/docs"

    return result
