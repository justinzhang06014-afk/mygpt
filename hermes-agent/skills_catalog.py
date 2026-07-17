"""
Skill 版本的「母版商店」，架構直接比照 mcp_services.py 的母版部分，但簡化很多：

跟 MCP 不一樣，skill 有沒有生效不靠 config.yaml 登記，純粹靠 hermes 自己掃描
profiles/<agent_id>/skills/ 資料夾（已對照 agent/prompt_builder.py 的 mtime/size
manifest 快取機制核對過）。所以這裡完全不需要「每個 agent 自己的選配狀態檔」，
母版本身就是唯一要存的東西——管理員精選幾個 hermes 官方技能市集(88000+ 個)裡的
identifier，agent 建立時使用者勾選了誰，就直接呼叫 main.py 已經存在的
`hermes skills install <identifier> --yes` 裝進那個 agent 的 skills/ 資料夾。
"""
import os
import json
import logging

logger = logging.getLogger("hermes-proxy.skills_catalog")

# 母版：跟 mcp.json 放同一層，一樣是 hermes-agent/skills_catalog.json
MASTER_CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills_catalog.json")


def load_master_catalog() -> dict:
    """讀取管理員維護的精選技能清單，回傳 {key: entry}"""
    if not os.path.exists(MASTER_CATALOG_PATH):
        return {}
    try:
        with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("skills", {})
    except Exception as e:
        logger.error(f"❌ 讀取母版 skills_catalog.json 失敗: {str(e)}")
        return {}


def save_master_catalog(catalog: dict) -> None:
    with open(MASTER_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump({"skills": catalog}, f, indent=2, ensure_ascii=False)


def upsert_master_catalog_entry(key: str, entry: dict) -> dict:
    """管理員後台新增或編輯一筆精選技能（用 key 當識別，存在就整筆覆蓋，不存在就新增）"""
    catalog = load_master_catalog()
    catalog[key] = entry
    save_master_catalog(catalog)
    logger.info(f"🗂️ [管理員後台] 精選技能清單新增/更新: {key}")
    return catalog[key]


def delete_master_catalog_entry(key: str) -> bool:
    catalog = load_master_catalog()
    if key not in catalog:
        return False
    del catalog[key]
    save_master_catalog(catalog)
    logger.info(f"🗑️ [管理員後台] 精選技能清單移除: {key}")
    return True
