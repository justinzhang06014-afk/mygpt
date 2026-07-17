import os
import re
import json
import logging
from datetime import datetime
from config import PROFILES_BASE_DIR

logger = logging.getLogger("hermes-proxy.mcp")

# 母版：跟這支檔案放在同一層 hermes-agent/mcp.json，由管理員後台編輯
MASTER_CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp.json")


def _agent_dir(agent_id: str) -> str:
    return os.path.join(PROFILES_BASE_DIR, agent_id)


def _agent_mcp_json_path(agent_id: str) -> str:
    return os.path.join(_agent_dir(agent_id), "mcp.json")


def _agent_env_path(agent_id: str) -> str:
    return os.path.join(_agent_dir(agent_id), ".env")


def load_master_catalog() -> dict:
    """讀取管理員維護的母版目錄，回傳 {mcp_name: entry} 結構"""
    if not os.path.exists(MASTER_CATALOG_PATH):
        return {}
    try:
        with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("mcpServers", {})
    except Exception as e:
        logger.error(f"❌ 讀取母版 mcp.json 失敗: {str(e)}")
        return {}


def save_master_catalog(catalog: dict) -> None:
    """管理員後台新增/編輯一筆母版條目時呼叫，整份覆寫回 mcp.json"""
    with open(MASTER_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump({"mcpServers": catalog}, f, indent=2, ensure_ascii=False)


def upsert_master_catalog_entry(name: str, entry: dict) -> dict:
    """管理員後台新增或編輯一筆母版條目（用名稱當 key，存在就整筆覆蓋，不存在就新增）"""
    catalog = load_master_catalog()
    catalog[name] = entry
    save_master_catalog(catalog)
    logger.info(f"🗂️ [管理員後台] 母版新增/更新了 MCP: {name}")
    return catalog[name]


def delete_master_catalog_entry(name: str) -> bool:
    """管理員後台從母版移除一筆條目；既有 agent 已經選過的 selection 不受影響，只是不會再出現在商店"""
    catalog = load_master_catalog()
    if name not in catalog:
        return False
    del catalog[name]
    save_master_catalog(catalog)
    logger.info(f"🗑️ [管理員後台] 母版移除了 MCP: {name}")
    return True


def get_agent_mcp_state(agent_id: str) -> dict:
    """
    讀取（不存在就用母版建立）這個 agent 自己的 $HERMES_HOME/mcp.json。
    每次讀取都會用母版「補新」——管理員後台新增的條目，既有 agent 也會自動看到（selection 預設 null），
    但不會動到使用者既有的 selection / credentialsConfigured 狀態。
    """
    master = load_master_catalog()
    path = _agent_mcp_json_path(agent_id)

    existing_servers = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing_servers = (json.load(f) or {}).get("servers", {})
        except Exception as e:
            logger.error(f"❌ 讀取 Agent [{agent_id}] 的 mcp.json 失敗，視為空白重建: {str(e)}")
            existing_servers = {}

    merged = {}
    for name, master_entry in master.items():
        prior = existing_servers.get(name, {})
        merged[name] = {
            **master_entry,
            "selection": prior.get("selection"),  # null | "resident" | "optional_installed"
            "credentialsConfigured": prior.get("credentialsConfigured", {}),
        }

    _write_agent_mcp_state(agent_id, merged)
    return merged


def _write_agent_mcp_state(agent_id: str, servers: dict) -> None:
    agent_dir = _agent_dir(agent_id)
    os.makedirs(agent_dir, exist_ok=True)
    path = _agent_mcp_json_path(agent_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"servers": servers, "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}, f, indent=2, ensure_ascii=False)


def set_agent_mcp_selection(agent_id: str, mcp_name: str, selection: str | None) -> dict:
    """selection 必須是 None（移除）、"resident"（常駐）或 "optional_installed"（選配已安裝）"""
    if selection not in (None, "resident", "optional_installed"):
        raise ValueError(f"不合法的 selection 值: {selection}")

    servers = get_agent_mcp_state(agent_id)
    if mcp_name not in servers:
        raise KeyError(f"母版裡沒有這個 MCP: {mcp_name}")

    servers[mcp_name]["selection"] = selection
    _write_agent_mcp_state(agent_id, servers)
    logger.info(f"🔌 [MCP] Agent [{agent_id}] 把 {mcp_name} 設為 {selection}")
    return servers[mcp_name]


def _env_var_name(mcp_name: str, field_key: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9]", "_", mcp_name).upper()
    safe_key = re.sub(r"[^A-Za-z0-9]", "_", field_key).upper()
    return f"MCP_{safe_name}_{safe_key}"


def set_agent_mcp_credentials(agent_id: str, mcp_name: str, credentials: dict[str, str]) -> dict:
    """
    使用者在商店卡片填的憑證值：實際值只寫進 $HERMES_HOME/.env，
    mcp.json 裡只記 credentialsConfigured 的布林值，不留明碼。
    """
    servers = get_agent_mcp_state(agent_id)
    if mcp_name not in servers:
        raise KeyError(f"母版裡沒有這個 MCP: {mcp_name}")

    env_path = _agent_env_path(agent_id)
    existing_env = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    existing_env[k.strip()] = v.strip()

    configured = servers[mcp_name].get("credentialsConfigured", {})
    for field_key, value in credentials.items():
        var_name = _env_var_name(mcp_name, field_key)
        if value:
            existing_env[var_name] = value
            configured[field_key] = True
        else:
            existing_env.pop(var_name, None)
            configured[field_key] = False

    os.makedirs(_agent_dir(agent_id), exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in existing_env.items():
            f.write(f"{k}={v}\n")

    servers[mcp_name]["credentialsConfigured"] = configured
    _write_agent_mcp_state(agent_id, servers)
    logger.info(f"🔑 [MCP] Agent [{agent_id}] 更新了 {mcp_name} 的憑證欄位: {list(credentials.keys())}")
    return servers[mcp_name]


def build_hermes_mcp_servers_block(agent_id: str) -> dict:
    """
    給 services.py 的 _write_isolated_config() 呼叫：把這個 agent 目前 selection 不是 null 的
    項目，轉成 hermes 原生 config.yaml 的 mcp_servers 格式（已實測驗證過的格式）。
    """
    servers = get_agent_mcp_state(agent_id)
    mcp_servers_block = {}

    for name, entry in servers.items():
        if entry.get("selection") not in ("resident", "optional_installed"):
            continue

        credential_fields = entry.get("credentialFields", [])
        env_refs = {f["key"]: f"${{{_env_var_name(name, f['key'])}}}" for f in credential_fields}

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
