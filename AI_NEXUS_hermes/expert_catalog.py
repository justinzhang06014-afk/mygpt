"""
Agentic Hub 專家匯入（response.json → MCP 目錄項目轉換）。

背景：response.json 是透過 AINexus 平台 API 匯出的「別人已經建好、發布分享的
Agentic Hub 專家」清單（每筆有 shareCode + mcpLink）。mcpLink 本質上就是一個可以
直接當 MCP url 用的 endpoint，跟 hermes-agent/mcp.json 母版裡 kind="url" 的條目
是同一種形狀，所以刻意不另外做一套匯入機制，只把它「轉換」成母版看得懂的格式。

刻意設計成 response.json 跟母版 hermes-agent/mcp.json 兩邊互不覆寫：這支模組只在
「讀取」的當下把兩邊在記憶體裡合併一次回傳，不會把轉換結果寫回 response.json 或
mcp.json 任何一個檔案。好處：response.json 之後要重新從 AINexus 匯出覆蓋，或母版
mcp.json 要手動調整，兩邊互不影響，不用跑遷移/合併腳本。
"""
import os
import re
import json
import hashlib
import logging

logger = logging.getLogger("hermes-proxy.expert_catalog")

# 跟 mcp_services.py 的母版放同一層，之後要重新從 AINexus 匯出覆蓋，直接蓋這支檔案即可
RESPONSE_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "response.json")

# 避免跟母版既有 key（如 "email"、"websearch"）撞名，所有專家一律加這個前綴
EXPERT_KEY_PREFIX = "expert_"


def _slugify(name: str) -> str:
    """把中文/符號名稱轉成安全的 key 片段（給 config.yaml 的 mcp_servers 當 key 用）"""
    ascii_only = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return ascii_only.lower() or "unnamed"


def load_expert_entries() -> dict:
    """
    讀取 response.json，轉成跟 mcp.json 母版一模一樣的 entry 格式：
    {key: {displayName, description, kind:"url", transport:"streamable-http", url, credentialFields:[]}}

    key 格式：expert_<名稱轉安全字串>_<shareCode 的短雜湊>，雜湊是為了避免兩個專家
    剛好同名時互相覆蓋（shareCode 本身含有 / + = 等符號，不適合直接拿來當 key）。
    """
    if not os.path.exists(RESPONSE_JSON_PATH):
        return {}

    try:
        with open(RESPONSE_JSON_PATH, "r", encoding="utf-8") as f:
            raw_list = json.load(f)
    except Exception as e:
        logger.error(f"❌ 讀取 response.json 失敗: {str(e)}")
        return {}

    entries = {}
    for item in raw_list:
        share_code = item.get("shareCode", "")
        mcp_link = item.get("mcpLink")
        name = item.get("name", "")
        if not mcp_link:
            continue

        short_hash = hashlib.md5(share_code.encode("utf-8")).hexdigest()[:8]
        key = f"{EXPERT_KEY_PREFIX}{_slugify(name)}_{short_hash}"

        entries[key] = {
            "displayName": name,
            "description": item.get("description", ""),
            "kind": "url",
            "transport": "streamable-http",
            "url": mcp_link,
            "credentialFields": [],  # Agentic Hub 專家的授權已經包在 mcpLink 的 shareCode 裡，不需要額外憑證
            "source": "agentic_hub",  # 純標記，方便之後商店 UI 想分開顯示「專家」跟一般 MCP 用，不影響 hermes 連線
        }

    return entries
