"""
AI_NEXUS Hermes Worker Initializer

依照 hermes-agent 架構初始化 hermes 容器
提供 API 服務接收建立 hermes 的請求
"""
import os
import socket
import json
import yaml
import shutil
import logging
import uuid
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import re
import hashlib
from docker.errors import NotFound

# FastAPI
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

# Docker SDK
import docker

# 建立 FastAPI 應用
app = FastAPI(title="AI_NEXUS Hermes Worker Provisioner", version="2.0.0")

# =============================================
# 設定
# =============================================

# 未來部署的主機
FUTURE_HOST = "http://192.168.41.173:5080"
FUTURE_API_ENDPOINT = f"{FUTURE_HOST}/api/v1/workers"

# 目前本地端測試
LOCAL_API_ENDPOINT = "http://localhost:8643"

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent
DATA_ROOT = PROJECT_ROOT / "data"
PROFILES_ROOT = DATA_ROOT / "profiles"

# Hermes 相關設定
HERMES_IMAGE = "nousresearch/hermes-agent:latest"
PROFILES_BASE_DIR = str(PROFILES_ROOT)
GLOBAL_HERMES_DIR = DATA_ROOT / "hermes_global"

# MCP 配置檔路徑
MASTER_MCP_JSON = PROJECT_ROOT / "mcp.json"
RESPONSE_JSON = PROJECT_ROOT / "response.json"
SKILLS_CATALOG_JSON = PROJECT_ROOT / "skills_catalog.json"

# 日誌設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hermes_initializer")

# =============================================
# 目錄初始化
# =============================================

def setup_directories():
    """建立必要的目錄結構"""
    directories = [
        DATA_ROOT,
        PROFILES_ROOT,
        GLOBAL_HERMES_DIR,
        DATA_ROOT / "uploads",
        DATA_ROOT / "static" / "uploads",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"建立目錄: {directory}")

def copy_hermes_config_files():
    """複製 hermes-agent 的配置檔案"""
    source_dir = Path(__file__).parent.parent / "hermes-agent"
    
    config_files = [
        ("mcp.json", MASTER_MCP_JSON),
        ("response.json", RESPONSE_JSON),
        ("skills_catalog.json", SKILLS_CATALOG_JSON),
    ]
    
    for source_name, dest_path in config_files:
        source_file = source_dir / source_name
        if source_file.exists():
            shutil.copy2(source_file, dest_path)
            logger.info(f"複製配置檔: {source_name} -> {dest_path}")
        else:
            logger.warning(f"找不到配置檔: {source_file}")

# =============================================
# Profile 初始化模組（參考 hermes-agent）
# =============================================

def generate_agent_id() -> str:
    """產生 agent ID"""
    return f"agent_{uuid.uuid4().hex[:12]}"

def load_master_catalog() -> dict:
    """讀取母版 mcp.json"""
    if not os.path.exists(MASTER_MCP_JSON):
        return {}
    try:
        with open(MASTER_MCP_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mcpServers", {})
    except Exception as e:
        logger.error(f"讀取母版 mcp.json 失敗: {str(e)}")
        return {}

def load_expert_entries() -> dict:
    """讀取 response.json 並轉換成 MCP 格式（參考 expert_catalog.py）"""
    if not os.path.exists(RESPONSE_JSON):
        return {}
    
    try:
        with open(RESPONSE_JSON, "r", encoding="utf-8") as f:
            raw_list = json.load(f)
    except Exception as e:
        logger.error(f"讀取 response.json 失敗: {str(e)}")
        return {}
    
    entries = {}
    prefix = "expert_"
    
    for item in raw_list:
        share_code = item.get("shareCode", "")
        mcp_link = item.get("mcpLink")
        name = item.get("name", "")
        if not mcp_link:
            continue
        
        short_hash = hashlib.md5(share_code.encode("utf-8")).hexdigest()[:8]
        slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() or "unnamed"
        key = f"{prefix}{slug}_{short_hash}"
        
        entries[key] = {
            "displayName": name,
            "description": item.get("description", ""),
            "kind": "url",
            "transport": "streamable-http",
            "url": mcp_link,
            "credentialFields": [],
            "source": "agentic_hub",
        }
    
    return entries

def write_agent_mcp_state(agent_id: str, servers: dict):
    """寫入 agent 的 mcp.json"""
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    os.makedirs(agent_dir, exist_ok=True)
    path = os.path.join(agent_dir, "mcp.json")
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "servers": servers,
            "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"寫入 {agent_id} 的 mcp.json，共 {len(servers)} 個伺服器")

def get_agent_mcp_state(agent_id: str) -> dict:
    """取得並初始化 agent 的 MCP 狀態"""
    master = {**load_master_catalog(), **load_expert_entries()}
    path = os.path.join(PROFILES_BASE_DIR, agent_id, "mcp.json")
    
    existing_servers = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing_servers = (json.load(f) or {}).get("servers", {})
        except Exception as e:
            logger.warning(f"讀取 Agent [{agent_id}] 的 mcp.json 失敗: {str(e)}")
    
    merged = {}
    for name, master_entry in master.items():
        prior = existing_servers.get(name, {})
        merged[name] = {
            **master_entry,
            "selection": prior.get("selection"),
            "credentialsConfigured": prior.get("credentialsConfigured", {}),
        }
    
    write_agent_mcp_state(agent_id, merged)
    return merged

def write_isolated_config(
    agent_id: str,
    system_prompt: str,
    agent_dir: str,
    model_config: dict,
    mcp_selections: Optional[Dict[str, str]] = None,
    approval_settings: Optional[Dict[str, Any]] = None
):
    """
    寫入 agent 的 config.yaml
    依照 hermes-agent/services.py::ensure_hermes_profile_exists 的邏輯
    """
    os.makedirs(agent_dir, exist_ok=True)
    
    # Approval 設定（優先使用參數，否則使用檔案或預設值）
    if approval_settings:
        agent_approvals = approval_settings
    else:
        approval_settings_file = os.path.join(DATA_ROOT, "approval_settings.json")
        if os.path.exists(approval_settings_file):
            with open(approval_settings_file, "r", encoding="utf-8") as f:
                agent_approvals = json.load(f)
        else:
            agent_approvals = {
                "mode": "manual",
                "memory_write_approval": False,
                "skills_write_approval": False,
            }
    
    # 建構 MCP servers 區塊
    agent_mcp_state = get_agent_mcp_state(agent_id)
    
    # 如果有指定 MCP 選擇，更新 agent_mcp_state
    if mcp_selections:
        for server_name, selection in mcp_selections.items():
            if server_name in agent_mcp_state:
                agent_mcp_state[server_name]["selection"] = selection
    
    mcp_servers_block = build_hermes_mcp_servers_block(agent_mcp_state)
    
    config_data = {
        "model": model_config,
        "memory": {
            "memory_enabled": True,
            "user_profile_enabled": True,
            "nudge_interval": 10,
            "write_approval": agent_approvals.get("memory_write_approval", False),
            "provider": ""
        },
        "approvals": {
            "mode": agent_approvals.get("mode", "manual")
        },
        "terminal": {
            "backend": "local",
            "cwd": "/workspace",
            "timeout": 180,
            "persistent_shell": True
        },
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
        "skills": {
            "write_approval": agent_approvals.get("skills_write_approval", False)
        },
        "context": {
            "enabled": True
        }
    }
    
    if mcp_servers_block:
        config_data["mcp_servers"] = mcp_servers_block
    
    config_path = os.path.join(agent_dir, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f, default_flow_style=False)
    
    logger.info(f"寫入 {agent_id} 的 config.yaml")

def build_hermes_mcp_servers_block(mcp_state: dict) -> dict:
    """
    建構 hermes 原生的 mcp_servers 區塊
    參考 mcp_services.py::build_hermes_mcp_servers_block
    """
    mcp_servers_block = {}
    
    for name, entry in mcp_state.items():
        if entry.get("selection") not in ("resident", "optional_installed"):
            continue
        
        credential_fields = entry.get("credentialFields", [])
        env_refs = {}
        for f in credential_fields:
            safe_name = re.sub(r"[^A-Za-z0-9]", "_", name).upper()
            safe_key = re.sub(r"[^A-Za-z0-9]", "_", f["key"]).upper()
            env_var_name = f"MCP_{safe_name}_{safe_key}"
            env_refs[f["key"]] = f"${{{env_var_name}}}"
        
        if entry.get("kind") == "stdio":
            block = {
                "command": entry.get("command"),
                "args": entry.get("args", []),
                "enabled": True,
            }
            if env_refs:
                block["env"] = env_refs
        else:
            block = {
                "url": entry.get("url"),
                "enabled": True,
            }
            if env_refs:
                block["headers"] = env_refs
        
        mcp_servers_block[name] = block
    
    return mcp_servers_block

def generate_default_skills_selection() -> dict:
    """
    參考 skills_catalog.json 產生預設技能選擇
    """
    if not os.path.exists(SKILLS_CATALOG_JSON):
        return {}
    
    try:
        with open(SKILLS_CATALOG_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("skills", {})
    except Exception as e:
        logger.error(f"讀取 skills_catalog.json 失敗: {str(e)}")
        return {}

def write_soul_file(agent_dir: str, system_prompt: str):
    """
    寫入 SOUL.md
    參考 services.py::_write_soul
    """
    soul_path = os.path.join(agent_dir, "SOUL.md")
    extended_soul_prompt = f"""{system_prompt}
=====================================================================
【🧠 記憶體自主運行與大腦統整沉澱最高核心條款】
1. 自主記憶捕捉：你在後台擁有全自動的長期記憶大腦（MEMORY.md）。安靜執行，不要向用戶宣告「我已經記下來了」。
2. 記憶定期沉澱與濃縮：保持 MEMORY.md 內的事實條目不超過 15-20 條。一旦超過，刪除過期雜訊，只留下沉澱後的金字塔精華。
3. 你每次開始對話前都會先讀取你自己的memory.md
=====================================================================
"""
    with open(soul_path, "w", encoding="utf-8") as f:
        f.write(extended_soul_prompt)
    
    logger.info(f"寫入 SOUL.md")

def initialize_hermes_profile(
    agent_id: str,
    system_prompt: str,
    model_config: dict,
    mcp_selections: Optional[Dict[str, str]] = None,
    approval_settings: Optional[Dict[str, Any]] = None
) -> str:
    """
    初始化 hermes profile
    參考 services.py::ensure_hermes_profile_exists
    """
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    
    # 建立目錄
    os.makedirs(agent_dir, exist_ok=True)
    
    # 建立必要子目錄
    subdirs = ["memories", "pending/skills", "logs"]
    for subdir in subdirs:
        full_path = os.path.join(agent_dir, subdir)
        os.makedirs(full_path, exist_ok=True)
    
    # 寫入配置檔
    write_isolated_config(
        agent_id=agent_id,
        system_prompt=system_prompt,
        agent_dir=agent_dir,
        model_config=model_config,
        mcp_selections=mcp_selections,
        approval_settings=approval_settings
    )
    
    # 寫入 SOUL.md
    write_soul_file(agent_dir, system_prompt)
    
    # 初始化 MCP 狀態（這會在 write_isolated_config 中自動呼叫）
    get_agent_mcp_state(agent_id)
    
    # 如果有指定 MCP 選擇，更新 mcp.json
    if mcp_selections:
        mcp_state = get_agent_mcp_state(agent_id)
        for server_name, selection in mcp_selections.items():
            if server_name in mcp_state:
                mcp_state[server_name]["selection"] = selection
                logger.info(f"設定 {server_name} 為 {selection}")
        write_agent_mcp_state(agent_id, mcp_state)
    
    # 如果有指定 approval 設定，寫入 approvals.json
    if approval_settings:
        approval_file = os.path.join(agent_dir, "approvals.json")
        with open(approval_file, "w", encoding="utf-8") as f:
            json.dump(approval_settings, f, indent=2, ensure_ascii=False)
        logger.info(f"寫入 {agent_id} 的 approval 設定")
    
    logger.info(f"✅ 初始化完成: {agent_id}")
    return agent_dir

# =============================================
# Docker 容器管理
# =============================================

def create_hermes_container(
    user_id: int = 1,
    port: int = 8643,
    env_vars: Optional[Dict[str, str]] = None,
    use_local: bool = True
) -> Optional[docker.models.containers.Container]:
    """
    建立 hermes 容器
    
    Args:
        user_id: 使用者 ID
        port: 對外提供服務的 port
        env_vars: 額外的環境變數
        use_local: 是否使用本地端測試
    
    Returns:
        Docker 容器物件
    """
    client = docker.from_env()
    
    # 建立容器配置
    container_name = f"hermes-worker-{user_id}"
    
    # 環境變數
    default_env = {
        "PROFILES_BASE_DIR": "/opt/data/profiles",
        "HERMES_BASE_URL": "https://ainexus.phison.com/api/external/v1",
        "HERMES_MODEL_BASE_URL": "https://ainexus.phison.com/api/external/v1",
    }
    
    if env_vars:
        default_env.update(env_vars)
    
    # Volume 掛載
    volumes = {
        str(DATA_ROOT): {
            "bind": "/opt/data",
            "mode": "rw"
        }
    }
    
    # Port 對應
    ports = {
        "8643/tcp": port
    }
    
    # 檢查是否已存在同名容器
    try:
        existing_container = client.containers.get(container_name)
        logger.warning(f"容器 {container_name} 已存在，移除舊容器")
        existing_container.remove(force=True)
    except docker.errors.NotFound:
        pass
    
    # 建立容器
    try:
        logger.info(f"建立容器: {container_name}")
        container = client.containers.run(
            HERMES_IMAGE,
            name=container_name,
            environment=default_env,
            volumes=volumes,
            ports=ports,
            detach=True,
            restart_policy={"Name": "unless-stopped"}
        )
        
        logger.info(f"✅ 容器建立成功: {container_name}")
        logger.info(f"服務地址: http://localhost:{port}")
        
        return container
    
    except Exception as e:
        logger.error(f"❌ 容器建立失敗: {str(e)}")
        return None

# =============================================
# 資料模型
# =============================================

class CreateWorkerRequest(BaseModel):
    """建立 Worker 的請求模型"""
    userId: int = Field(..., description="使用者 ID")
    system_prompt: str = Field(..., description="Agent 的系統提示詞")
    agent_id: Optional[str] = Field(None, description="Agent ID (若不提供則自動生成)")
    model_config: Optional[dict] = Field(None, description="模型配置")
    mcp_selections: Optional[Dict[str, str]] = Field(None, description="MCP 伺服器選擇 {server_name: selection}")
    approval_settings: Optional[Dict[str, Any]] = Field(None, description="核准設定")

class WorkerResponse(BaseModel):
    """Worker 建立回應模型"""
    status: str = Field(..., description="建立狀態")
    worker_id: str = Field(..., description="Worker ID (容器名稱)")
    agent_id: str = Field(..., description="Agent ID")
    api_url: str = Field(..., description="Hermes API 網址")
    message: str = Field(..., description="訊息")

# =============================================
# Runtime Provisioner (參考 runtime_manager.py)
# =============================================

DOCKER_SOCK_URL = "unix://var/run/docker.sock"
READINESS_TIMEOUT_SECONDS = 30

def _get_docker_client() -> docker.DockerClient:
    """取得 Docker 客戶端"""
    return docker.DockerClient(base_url=DOCKER_SOCK_URL)

def _get_self_container(client: docker.DockerClient):
    """取得自身容器"""
    try:
        return client.containers.get(socket.gethostname())
    except NotFound:
        # 如果不在容器內執行，則返回 None
        return None

def _wait_until_ready(container_name: str, port: int = 8643, timeout_seconds: int = READINESS_TIMEOUT_SECONDS) -> bool:
    """等待容器就緒"""
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    
    while time.monotonic() < deadline:
        try:
            # 嘗試連線到容器服務
            with socket.create_connection((container_name, port), timeout=1.5):
                return True
        except OSError as e:
            last_error = e
            time.sleep(0.5)
    
    logger.error(f"容器 {container_name} 在 {timeout_seconds} 秒內未就緒: {last_error}")
    return False

def ensure_worker_runtime(user_id: int, agent_id: str, system_prompt: str, 
                         model_config: Optional[dict] = None,
                         mcp_selections: Optional[Dict[str, str]] = None,
                         approval_settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    確保使用者專屬的 Hermes Runtime 容器存在
    
    參考 runtime_manager.py::ensure_user_runtime 的邏輯
    """
    container_name = f"hermes-worker-{user_id}"
    client = _get_docker_client()
    
    # 檢查是否已存在並運作中的容器
    try:
        existing = client.containers.get(container_name)
        if existing.status != "running":
            logger.info(f"🔄 [Runtime Provisioner] 使用者 {user_id} 的 Worker 已存在但未啟動，重新啟動中...")
            existing.start()
        
        # 等待容器就緒
        if _wait_until_ready(container_name):
            api_url = f"http://{container_name}:8643"
            logger.info(f"✅ [Runtime Provisioner] Worker 已就緒: {api_url}")
            return {
                "worker_id": container_name,
                "agent_id": agent_id,
                "api_url": api_url,
                "status": "existing"
            }
    except NotFound:
        pass
    
    # 建立新容器
    logger.info(f"🚀 [Runtime Provisioner] 使用者 {user_id} 尚無專屬 Worker，開始建立新容器...")
    
    # 初始化 Hermes Profile
    if not model_config:
        model_config = {
            "provider": "custom",
            "base_url": "https://ainexus.phison.com/api/external/v1",
            "api_key": os.getenv("PHISON_API_KEY", "YOUR_API_KEY_HERE"),
            "default": "Qwen/Qwen3.6-35B-A3B-FP8"
        }
    
    agent_dir = initialize_hermes_profile(
        agent_id=agent_id,
        system_prompt=system_prompt,
        model_config=model_config,
        mcp_selections=mcp_selections,
        approval_settings=approval_settings
    )
    
    # 建立容器 (參考 runtime_manager.py 的邏輯)
    try:
        self_container = _get_self_container(client)
        
        # 如果在容器內執行，複製容器設定
        if self_container:
            networks = list(self_container.attrs.get("NetworkSettings", {}).get("Networks", {}).keys())
            environment = _build_child_environment(self_container.container)
            
            # 建立容器
            container = client.containers.run(
                HERMES_IMAGE,
                name=container_name,
                environment=environment,
                volumes={
                    str(DATA_ROOT): {"bind": "/opt/data", "mode": "rw"}
                },
                network=networks[0] if networks else None,
                detach=True,
                restart_policy={"Name": "unless-stopped"}
            )
            
            # 連接額外的網路
            for extra_network in networks[1:]:
                try:
                    client.networks.get(extra_network).connect(container)
                except Exception as e:
                    logger.warning(f"無法連接到網路 {extra_network}: {str(e)}")
        
        else:
            # 在本地執行，直接使用預設設定
            default_env = {
                "PROFILES_BASE_DIR": "/opt/data/profiles",
                "HERMES_BASE_URL": "https://ainexus.phison.com/api/external/v1",
                "HERMES_MODEL_BASE_URL": "https://ainexus.phison.com/api/external/v1",
                "HERMES_API_KEY": os.getenv("PHISON_API_KEY", "YOUR_API_KEY_HERE"),
                "OPENAI_API_KEY": os.getenv("PHISON_API_KEY", "YOUR_API_KEY_HERE"),
            }
            
            container = client.containers.run(
                HERMES_IMAGE,
                name=container_name,
                environment=default_env,
                volumes={
                    str(DATA_ROOT): {"bind": "/opt/data", "mode": "rw"}
                },
                ports={"8643/tcp": 8643},
                detach=True,
                restart_policy={"Name": "unless-stopped"}
            )
        
        # 等待容器就緒
        if _wait_until_ready(container_name):
            api_url = f"http://{container_name}:8643"
            logger.info(f"✅ [Runtime Provisioner] 已為使用者 {user_id} 建立內部通道: {api_url}")
            
            return {
                "worker_id": container_name,
                "agent_id": agent_id,
                "api_url": api_url,
                "status": "created",
                "agent_dir": agent_dir
            }
        else:
            # 容器建立但未就緒，移除並回傳錯誤
            container.remove(force=True)
            raise RuntimeError(f"容器建立成功但未在 {READINESS_TIMEOUT_SECONDS} 秒內就緒")
    
    except Exception as e:
        logger.error(f"❌ 建立容器失敗: {str(e)}")
        raise

def _build_child_environment(self_container) -> dict:
    """從父容器建構環境變數"""
    env_list = self_container.attrs.get("Config", {}).get("Env", [])
    env = {}
    for entry in env_list:
        if "=" in entry:
            key, _, value = entry.partition("=")
            env[key] = value
    return env

# =============================================
# API 端點
# =============================================

@app.get("/")
async def root():
    """根端點"""
    return {
        "service": "AI_NEXUS Hermes Worker Provisioner",
        "version": "2.0.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    """健康檢查端點"""
    try:
        client = _get_docker_client()
        client.ping()
        return {"status": "healthy", "docker": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"服務不健康: {str(e)}")

@app.post("/api/worker/create", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
async def create_worker(request: CreateWorkerRequest):
    """
    建立新的 Hermes Worker
    
    Args:
        request: CreateWorkerRequest 物件
    
    Returns:
        WorkerResponse 物件
    """
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"收到建立 Worker 請求")
        logger.info(f"{'='*60}")
        logger.info(f"User ID: {request.userId}")
        logger.info(f"System Prompt: {request.system_prompt[:100]}...")
        logger.info(f"Agent ID: {request.agent_id or '自動生成'}")
        
        # 確保目錄結構存在
        setup_directories()
        
        # 複製配置檔案
        copy_hermes_config_files()
        
        # 生成 Agent ID (如果未提供)
        agent_id = request.agent_id or generate_agent_id()
        
        # 建立 Worker Runtime
        result = ensure_worker_runtime(
            user_id=request.userId,
            agent_id=agent_id,
            system_prompt=request.system_prompt,
            model_config=request.model_config,
            mcp_selections=request.mcp_selections,
            approval_settings=request.approval_settings
        )
        
        logger.info(f"✅ Worker 建立完成")
        logger.info(f"Worker ID: {result['worker_id']}")
        logger.info(f"Agent ID: {result['agent_id']}")
        logger.info(f"API URL: {result['api_url']}")
        logger.info(f"{'='*60}\n")
        
        return WorkerResponse(
            status="success",
            worker_id=result["worker_id"],
            agent_id=result["agent_id"],
            api_url=result["api_url"],
            message=f"Worker 建立成功，API 網址: {result['api_url']}"
        )
    
    except Exception as e:
        logger.error(f"❌ 建立 Worker 失敗: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"建立 Worker 失敗: {str(e)}"
        )

@app.get("/api/worker/{worker_id}/status")
async def get_worker_status(worker_id: str):
    """
    查詢 Worker 狀態
    
    Args:
        worker_id: Worker ID (容器名稱)
    
    Returns:
        Worker 狀態資訊
    """
    try:
        client = _get_docker_client()
        container = client.containers.get(worker_id)
        
        container.reload()
        status = container.status
        
        # 檢查容器是否就緒
        is_ready = _wait_until_ready(worker_id, timeout_seconds=1)
        
        return {
            "worker_id": worker_id,
            "status": status,
            "is_ready": is_ready,
            "api_url": f"http://{worker_id}:8643"
        }
    
    except NotFound:
        raise HTTPException(status_code=404, detail=f"找不到 Worker: {worker_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查詢失敗: {str(e)}")

@app.delete("/api/worker/{worker_id}")
async def delete_worker(worker_id: str):
    """
    刪除 Worker
    
    Args:
        worker_id: Worker ID (容器名稱)
    
    Returns:
        刪除結果
    """
    try:
        client = _get_docker_client()
        container = client.containers.get(worker_id)
        
        container.remove(force=True)
        logger.info(f"🗑️ [Runtime Provisioner] 已刪除 Worker: {worker_id}")
        
        return {
            "status": "success",
            "message": f"Worker {worker_id} 已刪除"
        }
    
    except NotFound:
        raise HTTPException(status_code=404, detail=f"找不到 Worker: {worker_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")

# =============================================
# 主程式
# =============================================

def main():
    """啟動 Provisioner 服務"""
    logger.info("=" * 60)
    logger.info("AI_NEXUS Hermes Worker Provisioner")
    logger.info("=" * 60)
    
    # 初始化設定
    setup_directories()
    copy_hermes_config_files()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )

if __name__ == "__main__":
    main()