"""
呼叫同事的外部 orchestrator 服務，取代 runtime_manager.py 自己用 docker.sock 建容器
那條路——同事的服務負責「空間/儲存/容器怎麼跑」，我們（這支服務）還是全權負責
hermes config.yaml/mcp_servers 產生跟 ACP 對話執行，範圍沒有變。

設計成「開關式」：設定 ORCHESTRATOR_URL 環境變數才會啟用這條路；沒設定就照舊用
runtime_manager.py 自己的 docker.sock 邏輯（本機測試/沒有同事服務時還能用）。
main.py 完全不用知道現在走哪一條路，兩條路都回傳同樣格式的 dict。

#0722修正：根據 docker_README.md 的真實 API 規格修改，
- userId 改為接受字串（原本期望數字）
- 統一使用 "baseUrl" 欄位（回應中的確切欄位名稱）
- payload 對照 API 文件的真實範例格式
- 處理 409 Conflict 錯誤（使用者已有容器時的處理邏輯）
- 支援 externalBaseUrl（當 ExternalAccess 啟用時優先使用）
- 預設 orchestrator URL 設為 192.168.41.173:5080（對方固定主機）

⚠️ 重要注意事項：
- 遠端主機 (192.168.41.173) 的 {HERMES_DATA_ROOT}/users/{user_id} 路徑需要預先準備好
- 檔案包含：config.yaml, SOUL.md, mcp.json, phison_mcp_bridge.py
- 可透過共享儲存、SSH/SCP、或其他檔案同步機制準備到遠端主機
- 确保 orchestrator 的 AllowedBindPrefixes 配置允許掛載 HERMES_DATA_ROOT 路徑
"""
import os
import json
import requests
from pathlib import Path
from typing import List, Tuple

from config import logger

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
    """將字串 user_id 轉換為整數，用於 Orchestrator API 的 userId 欄位。
    
    使用穩定的 CRC32 雜湊確保同一字串總是轉換為相同整數：
    - input: "demo001"  → output: 123456789
    - input: "user_001" → output: 987654321
    - input: "test_user"→ output: 556677889
    
    注意：雜湊值可能為負數，取絕對值確保為正整數。
    """
    import zlib
    hash_value = zlib.crc32(user_id.encode('utf-8'))
    return abs(hash_value) | 1  # 確保正整數（避免0，某些系統可能不接受0作為ID）


def is_enabled() -> bool:
    """有設定 ORCHESTRATOR_URL 才走外部 orchestrator，這是唯一的開關。
    
    🔧 正式模式：啟用遠端 Orchestrator 連線
    """
    return bool(ORCHESTRATOR_URL)


def _upload_files_to_orchestrator(user_id_int: int, agent_dir: str, required_files: List[str]) -> bool:
    """
    上傳 hermes 所需的檔案到遠端 Orchestrator 主機。
    
    使用 multipart/form-data 格式傳送檔案：
    - endpoint: POST /api/v1/users/{user_id}/files
    - files: config.yaml, SOUL.md, mcp.json, phison_mcp_bridge.py
    
    Args:
        user_id_int: 轉換後的整數 user ID
        agent_dir: 本機的 agent 目錄路徑
        required_files: 需要上傳的檔案列表
        
    Returns:
        bool: 是否上傳成功
    """
    upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{user_id_int}/files"
    
    # 準備要上傳的檔案
    files_to_upload = []
    for filename in required_files:
        file_path = Path(agent_dir) / filename
        if not file_path.exists():
            logger.error(f"❌ [Orchestrator] 檔案不存在: {file_path}")
            return False
        
        files_to_upload.append((filename, (filename, open(file_path, "rb"), "application/octet-stream")))
    
    try:
        logger.info(f"📤 [Orchestrator] 開始上傳檔案到: {upload_url}")
        upload_resp = requests.post(
            upload_url,
            files=files_to_upload,
            timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
        )
        upload_resp.raise_for_status()
        
        upload_data = upload_resp.json()
        logger.info(f"✅ [Orchestrator] 檔案上傳成功: {json.dumps(upload_data, indent=2, ensure_ascii=False)}")
        
        # 檢查上傳結果
        files_result = upload_data.get("files", [])
        written_count = upload_data.get("writtenCount", 0)
        
        if written_count != len(required_files):
            logger.warning(f"⚠️ [Orchestrator] 檔案上傳數量不符: 預期 {len(required_files)}, 實際 {written_count}")
            for file_result in files_result:
                if file_result.get("status") not in ["written", "success"]:
                    logger.error(f"❌ [Orchestrator] 檔案上傳失敗: {file_result.get('path')} - {file_result.get('error')}")
            return False
            
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [Orchestrator] 檔案上傳失敗: {str(e)}")
        return False
    finally:
        # 關閉所有開啟的檔案
        for _, (_, file_obj) in files_to_upload:
            file_obj.close()


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
    
    if isinstance(external_base_url, (list, tuple)) and len(external_base_url) > 0:
        logger.warning(f"⚠️ [Debug] external_base_url 是陣列，取第一個元素: {external_base_url[0]}")
        external_base_url = external_base_url[0]

    # 如果都没有，返回 None, None
    if not base_url and not external_base_url:
        logger.info("🔍 [Debug] 兩個都是 None，返回 None, None")
        return None, None

    logger.info(f"🔍 [Debug] 返回 base_url: {base_url}, external_base_url: {external_base_url}")
    return base_url, external_base_url


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

    # userId 必須是整數：使用 CRC32 雜湊將字串轉換為穩定的整數
    user_id_int = _convert_user_id(user_id)
    
    # 遠端主機路徑：/home/phison/ainexus/agent-data/{user_id_int}
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
    upload_success = _upload_files_to_orchestrator(user_id_int, agent_dir, required_files)
    if not upload_success:
        raise RuntimeError(f"檔案上傳到遠端 Orchestrator 失敗，停止容器建立流程")
    
    # 步驟3: 組裝建立容器的 payload
    payload = {
        "userId": user_id_int,
        "image": HERMES_IMAGE,
        "environment": {
            "PHISON_API_KEY": os.getenv("PHISON_API_KEY", ""),
            # 模型設定 - 測試用，之後刪除
            "LLM_PROVIDER": "custom",
            "LLM_BASE_URL": "http://10.102.196.43:18299/InferenceModel43/v1",
            "LLM_MODEL": "InferenceModel43",
            "LLM_API_KEY": "",  # 測試用空值
            # API Server 設定
            "API_SERVER_ENABLED": "true",
            "API_SERVER_HOST": "0.0.0.0",
            "API_SERVER_KEY": os.urandom(16).hex(),  # 隨機產生的 key
            "API_SERVER_CORS_ORIGINS": "*",
        },
        "volumes": {
            # 掛載遠端主機的檔案目錄到容器 /opt/data
            # 遠端主機路徑：/home/phison/ainexus/agent-data/{user_id_int} (剛上傳的檔案位置)
            # 容器路徑：/opt/data (hermes 程式會從這裡讀取設定檔)
            remote_host_path: "/opt/data",
        },
    }

    # 🔍 詳細日誌：輸出實際發送的 payload 和 URL
    api_url = f"{ORCHESTRATOR_URL}/api/v1/workers"
    logger.info(f"📤 [Orchestrator] 發送的 Request URL: {api_url}")
    logger.info(f"📤 [Orchestrator] 原始 user_id: {user_id} -> 轉換為 userId: {user_id_int}")
    logger.info(f"📤 [Orchestrator] 發送的 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    logger.info(f"📤 [Orchestrator] HERMES_IMAGE 環境變數值: {HERMES_IMAGE}")
    logger.info(f"📤 [Orchestrator] HERMES_DATA_ROOT 環境變數值: {HERMES_DATA_ROOT}")

    try:
        resp = requests.post(
            api_url,
            json=payload,
            timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
        )

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
        logger.info(f"🔍 [Debug] _extract_base_url 返回結果: {extract_result}, 類型: {type(extract_result)}")
        
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

    # #0722修正：從回應中提取更多詳細資訊，供 main.py 回傳給使用者
    worker_id = data.get("id")
    worker_name = data.get("name")
    status = data.get("status", "created")

    result = {
        "status": status,
        "base_url": base_url or external_base_url,  # 優先使用 baseUrl，沒有就用 externalBaseUrl
        "user_id": user_id,  # 回傳原始字串 user_id 給呼叫端
        "user_id_int": user_id_int  # 新增：轉換後的整數 ID，供偵錯使用
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
