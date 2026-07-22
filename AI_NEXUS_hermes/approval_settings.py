"""
每個 agent 自己的 approval 設定（跟 mcp_services.py 的 mcp.json 同一套模式：
存成 agent 自己目錄下的一個小 JSON 檔案，真相來源是實體檔案，不另外存 Postgres）。

對應 hermes 自己原生的三個開關（已對照 hermes_cli/config.py 原始碼核對過，不是猜的）：
- approvals.mode：manual（預設，什麼危險動作都問）/ smart（LLM 自動判斷低風險放行）/ off（不問）
- memory.write_approval：寫入 MEMORY.md/USER.md 前要不要先問
- skills.write_approval：安裝/修改技能前要不要先問
"""
import os
import json
import logging
from config import PROFILES_BASE_DIR

logger = logging.getLogger("hermes-proxy.approvals")

VALID_MODES = ("manual", "smart", "off")

DEFAULT_SETTINGS = {
    "mode": "manual",
    "memory_write_approval": False,
    "skills_write_approval": False,
}


def _agent_dir(agent_id: str) -> str:
    return os.path.join(PROFILES_BASE_DIR, agent_id)


def _settings_path(agent_id: str) -> str:
    return os.path.join(_agent_dir(agent_id), "approvals.json")


def get_agent_approval_settings(agent_id: str) -> dict:
    """讀取這個 agent 的 approval 設定，檔案不存在或欄位不全就用預設值補齊。"""
    path = _settings_path(agent_id)
    if not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)

    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except Exception as e:
        logger.error(f"❌ 讀取 Agent [{agent_id}] 的 approvals.json 失敗，視為預設值: {str(e)}")
        return dict(DEFAULT_SETTINGS)

    return {**DEFAULT_SETTINGS, **saved}


def set_agent_approval_settings(agent_id: str, updates: dict) -> dict:
    """只更新有傳進來的欄位，沒傳的欄位維持原值（或預設值）。"""
    if "mode" in updates and updates["mode"] is not None and updates["mode"] not in VALID_MODES:
        raise ValueError(f"不合法的 mode 值: {updates['mode']}，合法值: {VALID_MODES}")

    current = get_agent_approval_settings(agent_id)
    for key in ("mode", "memory_write_approval", "skills_write_approval"):
        if key in updates and updates[key] is not None:
            current[key] = updates[key]

    agent_dir = _agent_dir(agent_id)
    os.makedirs(agent_dir, exist_ok=True)
    with open(_settings_path(agent_id), "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)

    logger.info(f"🛡️ [Approvals] Agent [{agent_id}] 設定更新為: {current}")
    return current
