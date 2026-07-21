"""
🧪 測試用「全部匯入」版本：跟 mcp_services.py 用同一套母版/憑證機制，唯一差異是
build_hermes_mcp_servers_block_all() 完全不看 per-agent 的 selection 狀態——
母版（含 mcp.json + response.json 轉換出來的 Agentic Hub 專家）裡的每一筆，
無條件全部塞進 config.yaml 的 mcp_servers，跟使用者有沒有在商店裡選過完全無關。

刻意設計成獨立檔案，不修改 mcp_services.py 原本的 build_hermes_mcp_servers_block()
（那個函式的 selection 篩選邏輯完全沒有被動到）——要測試「全部匯入」的效果，
就在 services.py 的 _write_isolated_config() 裡把：

    import mcp_services
    ...
    mcp_servers_block = mcp_services.build_hermes_mcp_servers_block(agent_id)

暫時換成：

    import mcp_services_all
    ...
    mcp_servers_block = mcp_services_all.build_hermes_mcp_servers_block_all(agent_id)

測試完想換回原本行為，把這兩行改回 mcp_services 的呼叫即可，mcp_services.py
本身從頭到尾都沒被改過。
"""
import logging
import mcp_services
import expert_catalog

logger = logging.getLogger("hermes-proxy.mcp_all")


def load_combined_catalog() -> dict:
    """母版 mcp.json + response.json 專家清單合併（純記憶體合併，不寫回任一來源檔案）"""
    return {**mcp_services.load_master_catalog(), **expert_catalog.load_expert_entries()}


def build_hermes_mcp_servers_block_all(agent_id: str) -> dict:
    """
    測試用：完全略過 per-agent 的 selection 狀態，母版（含專家）裡的每一筆都無條件納入。
    憑證欄位處理邏輯跟 mcp_services.build_hermes_mcp_servers_block() 完全一樣
    （credentialFields -> ${MCP_<NAME>_<KEY>} 環境變數引用，實際值仍然只落在 agent 自己的
    .env，這裡不變動），差別只在於不看 selection。

    ⚠️ 注意：這會把「需要憑證但使用者從沒填過」的 MCP（例如母版裡的 email）也一併塞進
    config.yaml，屆時對應的環境變數是空的——正式採用前要先實測 hermes 對「憑證缺失的
    MCP server」是整組啟動失敗、還是只有那個 server 連不上、其他照常運作。
    """
    catalog = load_combined_catalog()
    mcp_servers_block = {}

    for name, entry in catalog.items():
        credential_fields = entry.get("credentialFields", [])
        env_refs = {
            f["key"]: f"${{{mcp_services._env_var_name(name, f['key'])}}}"
            for f in credential_fields
        }

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

    logger.info(f"🔌 [MCP 全部匯入-測試] Agent [{agent_id}] 匯入了 {len(mcp_servers_block)} 個 MCP（不看 selection）")
    return mcp_servers_block
